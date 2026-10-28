// WebMCP: Pear's read-only tools for AI agents in the browser (document.modelContext, or navigator.modelContext in
// older Chrome builds). Does nothing where the browser has no WebMCP. The same data is public at /llms.txt.
(function () {
  var mc = (typeof document !== "undefined" && document.modelContext) || (typeof navigator !== "undefined" && navigator.modelContext);
  if (!mc || typeof mc.registerTool !== "function") return;
  var FN = "https://exzkanvrboytydrvwcwv.supabase.co/functions/v1";
  var REST = "https://exzkanvrboytydrvwcwv.supabase.co/rest/v1";
  var KEY = "sb_publishable_i1mvt6QvDAsxIbOidUvCmg_XrVaizj4";   // public key, same one the pages use
  var TICKER = { type: "string", description: "US stock ticker, e.g. AAPL", pattern: "^[A-Za-z]{1,5}([.-][A-Za-z])?$" };
  var text = function (t) { return { content: [{ type: "text", text: t }] }; };
  var ticker = function (a) { return String((a && a.ticker) || "").trim().toUpperCase(); };

  var tools = [{
    name: "get_earnings_release",
    description: "The latest earnings press release of a US-listed company (8-K Item 2.02 / 6-K Exhibit 99.1 from SEC EDGAR, " +
      "within about a minute of filing) as Markdown: an analysis from the filing alone (headline numbers, segments, margins, " +
      "KPIs, guidance), then the full release with its financial statements and the SEC link.",
    inputSchema: { type: "object", properties: { ticker: TICKER }, required: ["ticker"] },
    annotations: { readOnlyHint: true },
    execute: function (args) {
      return fetch(FN + "/fmv-earnings?format=md&ticker=" + encodeURIComponent(ticker(args)))
        .then(function (r) { return r.text().then(function (b) { return text(r.ok ? b : "No release: " + b); }); });
    },
  }, {
    name: "get_fair_value",
    description: "Pear Digitals' latest bear, base and bull fair value per share for a Magnificent 7 stock " +
      "(AAPL, AMZN, GOOGL, META, MSFT, NVDA, TSLA), with its date. Not investment advice.",
    inputSchema: { type: "object", properties: { ticker: TICKER }, required: ["ticker"] },
    annotations: { readOnlyHint: true },
    execute: function (args) {
      var t = ticker(args);
      return fetch(REST + "/vintages_free?select=ticker,date,bear,base,bull&order=date.desc&limit=1&ticker=eq." + encodeURIComponent(t),
        { headers: { apikey: KEY } }).then(function (r) { return r.json(); }).then(function (rows) {
        var v = rows && rows[0];
        return text(v ? JSON.stringify({ ticker: v.ticker, date: v.date, bear: v.bear, base: v.base, bull: v.bull,
          page: "https://peardigitals.com/fmv/" + t.toLowerCase() + "/" }) : "No public fair value for " + t + ".");
      });
    },
  }];
  tools.forEach(function (t) { try { mc.registerTool(t); } catch (e) { /* already registered, or an older API shape */ } });
})();
