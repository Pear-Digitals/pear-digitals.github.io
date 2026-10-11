// Supabase Edge Function: finance chat limited to the Mag 7, grounded in fmv_docs.
// Secrets: GEMINI_API_KEY (required), GEMINI_MODEL, ALLOWED_ORIGINS (comma list, optional).
// Deploy with --no-verify-jwt (the page sends a publishable key, not a JWT); origin is checked below.

const MAG7 = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"];
const MODEL = Deno.env.get("GEMINI_MODEL") ?? "gemini-2.5-flash";
const ORIGINS = (Deno.env.get("ALLOWED_ORIGINS") ??
  "https://pear-digitals.github.io,https://peardigitals.com,https://www.peardigitals.com").split(",");
const MAX_MSGS = 12, MAX_CHARS = 2000, MAX_TOKENS = 1500;

const SYSTEM = `You are the Pear Digitals FMV assistant. You only discuss finance.

Scope:
- Stock analysis is limited to the Magnificent 7: ${MAG7.join(", ")}. If asked to analyze or give a view on any other company, say you only cover the Mag 7 and offer one of those instead.
- General finance education (terminology, valuation metrics such as P/E, EV/EBITDA, DCF, PEG, FCF yield, WACC, margin of safety, how bear/base/bull scenarios work) is fine for any asker, using generic examples or the Mag 7.
- Politely decline anything that is not finance.

Grounding:
- The FMV documents below are the only source for fair-value numbers, scenario assumptions and zones. Quote them, name the ticker and the document date, and never invent figures. If something isn't in the documents, say so.
- Explain the bear, base and bull cases: what drives each, the key assumptions, and what would move a stock between them.
- If asked to tweak a valuation input (growth, margin, multiple, discount rate, etc.), recompute the affected scenario from the document's own method, show the arithmetic and the before/after, and label it clearly as a hypothetical that does not change the published FMV.
- FMV only updates after major events or earnings, so the document date matters; mention it when the figures may be stale.
- You do not know live prices unless the user gives one. Educational content only, not personalized financial advice.

Style: concise, plain language, define jargon the first time you use it.`;

const cors = (origin: string | null) => ({
  "Access-Control-Allow-Origin": origin ?? "",
  "Access-Control-Allow-Headers": "content-type, authorization, apikey, x-client-info",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Vary": "Origin",
});

// FMV data changes rarely, so cache the combined docs in memory (Gemini also caches repeated prefixes implicitly).
let cache: { at: number; text: string } | null = null;
async function loadDocs(): Promise<string> {
  if (cache && Date.now() - cache.at < 30 * 60_000) return cache.text;
  const url = Deno.env.get("SUPABASE_URL")!, key = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  const r = await fetch(`${url}/rest/v1/fmv_docs?select=ticker,as_of,content&order=as_of.desc`, {
    headers: { apikey: key, authorization: `Bearer ${key}` },
  });
  if (!r.ok) throw new Error("docs " + r.status);
  const rows: { ticker: string; as_of: string; content: string }[] = await r.json();
  const latest = new Map<string, typeof rows[number]>();
  for (const row of rows) if (MAG7.includes(row.ticker) && !latest.has(row.ticker)) latest.set(row.ticker, row);
  const text = [...latest.values()]
    .map((d) => `<fmv_document ticker="${d.ticker}" date="${d.as_of}">\n${d.content}\n</fmv_document>`)
    .join("\n\n") || "(no FMV documents loaded)";
  cache = { at: Date.now(), text };
  return text;
}

Deno.serve(async (req) => {
  const origin = req.headers.get("origin");
  const allowed = origin && (ORIGINS.includes(origin) || /^http:\/\/localhost(:\d+)?$/.test(origin));
  const h = cors(allowed ? origin : null);
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: h });
  if (!allowed) return new Response("forbidden", { status: 403, headers: h });
  if (req.method !== "POST") return new Response("method not allowed", { status: 405, headers: h });

  let body: { messages?: { role: string; content: string }[]; ticker?: string };
  try { body = await req.json(); } catch { return new Response("bad json", { status: 400, headers: h }); }

  let msgs = (Array.isArray(body.messages) ? body.messages : [])
    .filter((m) => (m.role === "user" || m.role === "assistant") && typeof m.content === "string" && m.content.trim())
    .slice(-MAX_MSGS)
    .map((m) => ({ role: m.role, content: m.content.slice(0, MAX_CHARS) }));
  while (msgs.length && msgs[0].role !== "user") msgs.shift();
  if (!msgs.length || msgs[msgs.length - 1].role !== "user")
    return new Response("need a user message", { status: 400, headers: h });

  const ticker = MAG7.includes(String(body.ticker)) ? String(body.ticker) : null;
  let docs: string;
  try { docs = await loadDocs(); } catch { return new Response("data unavailable", { status: 502, headers: h }); }

  const system = [
    SYSTEM,
    `FMV documents:\n\n${docs}`,
    ...(ticker ? [`The user is currently viewing ${ticker} on the page.`] : []),
  ].join("\n\n");
  const upstream = await fetch(
    `https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:streamGenerateContent?alt=sse`,
    {
      method: "POST",
      headers: { "x-goog-api-key": Deno.env.get("GEMINI_API_KEY")!, "content-type": "application/json" },
      body: JSON.stringify({
        systemInstruction: { parts: [{ text: system }] },
        contents: msgs.map((m) => ({ role: m.role === "assistant" ? "model" : "user", parts: [{ text: m.content }] })),
        generationConfig: { maxOutputTokens: MAX_TOKENS },
      }),
    },
  );
  if (!upstream.ok || !upstream.body) return new Response("model error", { status: 502, headers: h });

  // Convert Gemini SSE into a plain text stream.
  const dec = new TextDecoder(), enc = new TextEncoder();
  let buf = "";
  const out = upstream.body.pipeThrough(new TransformStream<Uint8Array, Uint8Array>({
    transform(chunk, ctrl) {
      buf += dec.decode(chunk, { stream: true });
      const lines = buf.split("\n");
      buf = lines.pop() ?? "";
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        try {
          const e = JSON.parse(line.slice(6));
          const t = (e.candidates?.[0]?.content?.parts ?? []).map((p: { text?: string }) => p.text ?? "").join("");
          if (t) ctrl.enqueue(enc.encode(t));
        } catch { /* ignore partial/non-JSON lines */ }
      }
    },
  }));
  return new Response(out, { headers: { ...h, "content-type": "text/plain; charset=utf-8", "cache-control": "no-store" } });
});
