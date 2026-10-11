#!/usr/bin/env python3
"""Build one search-friendly page per covered stock: fmv/<ticker>/index.html.

Each page is the same app as fmv/index.html (opened on that stock) with its own <title>, description, canonical
URL, link-preview tags, structured data and a short visible summary. Also writes sitemap.xml and robots.txt.
Only public data is used (the 30-day public views), so the pages never contain anything plan-gated.

Run after changing fmv/index.html, and daily (see .github/workflows/seo.yml):
    python3 tools/seo_build.py
"""
import datetime, html, json, os, re, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://peardigitals.com"
API = "https://exzkanvrboytydrvwcwv.supabase.co/rest/v1"
KEY = "sb_publishable_i1mvt6QvDAsxIbOidUvCmg_XrVaizj4"   # public key, same one the page uses
# Friendly and legal names for the stocks we have pages for (all Nasdaq-listed).
NAMES = {
    "AAPL": ("Apple", "Apple Inc."), "AMZN": ("Amazon", "Amazon.com, Inc."), "GOOGL": ("Alphabet", "Alphabet Inc."),
    "META": ("Meta", "Meta Platforms, Inc."), "MSFT": ("Microsoft", "Microsoft Corporation"),
    "NVDA": ("NVIDIA", "NVIDIA Corporation"), "TSLA": ("Tesla", "Tesla, Inc."),
}
EXCHANGE = "NASDAQ"


def get(path):
    req = urllib.request.Request(API + path, headers={"apikey": KEY})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def money(x):
    return f"${x:,.0f}" if x >= 100 else f"${x:,.2f}"


def nice_date(iso):
    d = datetime.date.fromisoformat(iso)
    return d.strftime("%b %-d, %Y")


def replace_between(text, tag, new):
    pat = re.compile(rf"<!--{tag}-->.*?<!--/{tag}-->", re.S)
    assert pat.search(text), f"marker {tag} missing in fmv/index.html"
    return pat.sub(lambda _: f"<!--{tag}-->{new}<!--/{tag}-->", text, count=1)


def write_if_changed(path, content):
    old = open(path).read() if os.path.exists(path) else None
    if old != content:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w").write(content)
        return True
    return False


def main():
    template = open(os.path.join(ROOT, "fmv", "index.html")).read()
    vint = get("/vintages_free?select=ticker,date,bear,base,bull&order=date.desc&limit=500")
    px = get("/prices_free?select=symbol,date,c&order=date.desc&limit=500")
    latest, close = {}, {}
    for v in vint:
        latest.setdefault(v["ticker"], v)
    for p in px:
        close.setdefault(p["symbol"], p)
    tickers = sorted(t for t in latest if t in NAMES and t in close)
    links = " ".join(f'<a href="/fmv/{t.lower()}/">{html.escape(NAMES[t][0])} ({t})</a>' for t in tickers)
    changed = []

    for t in tickers:
        name, legal = NAMES[t]
        v, c = latest[t], close[t]
        bear, base, bull = v["bear"], v["base"], v["bull"]   # no prices in the static text (market-data display terms)
        url = f"{SITE}/fmv/{t.lower()}/"
        title = f"{name} ({t}) Fair Value: Bear, Base & Bull | Pear Digitals"
        desc = (f"{name} ({t}) fair value: {money(base)} base case, {money(bear)} bear, {money(bull)} bull "
                f"({nice_date(v['date'])}). Pear Digitals' fair market value analysis, re-rated after earnings.")
        jsonld = {
            "@context": "https://schema.org", "@type": "WebPage", "name": title, "url": url, "description": desc,
            "dateModified": v["date"],
            "about": {"@type": "Corporation", "name": legal, "tickerSymbol": f"{EXCHANGE}:{t}"},
            "publisher": {"@type": "Organization", "name": "Pear Digitals LLC", "url": SITE},
        }
        e = html.escape
        head = (f"\n<title>{e(title)}</title>\n"
                f'<meta name="description" content="{e(desc)}">\n'
                f'<link rel="canonical" href="{url}">\n'
                f'<meta property="og:type" content="website">\n<meta property="og:site_name" content="Pear Digitals">\n'
                f'<meta property="og:title" content="{e(title)}">\n<meta property="og:description" content="{e(desc)}">\n'
                f'<meta property="og:url" content="{url}">\n<meta name="twitter:card" content="summary">\n'
                f'<script type="application/ld+json">{json.dumps(jsonld)}</script>\n')
        summary = (f'<section class="seo"><h2>{e(name)} ({t}) fair value</h2>'
                   f"<p>Pear's fair value for {e(name)} is {money(base)} in the base case, with a bear case of {money(bear)} "
                   f"and a bull case of {money(bull)} (published {nice_date(v['date'])}).</p>"
                   f"<p>Fair values are re-rated automatically after earnings and other significant events. "
                   f"Estimates, not investment advice.</p><p>More fair values: {links}</p></section>")
        page = replace_between(template, "seo:head", head)
        page = replace_between(page, "seo:summary", summary)
        if write_if_changed(os.path.join(ROOT, "fmv", t.lower(), "index.html"), page):
            changed.append(f"fmv/{t.lower()}/")

    # Main page: a short intro with links to every stock page (helps search engines find them).
    intro = ('<section class="seo"><h2>Fair value analysis</h2><p>Pear Digitals publishes bear, base and bull fair '
             "values for the Magnificent 7, re-rated automatically after earnings and other significant events. "
             f"Estimates, not investment advice.</p><p>{links}</p></section>")
    if write_if_changed(os.path.join(ROOT, "fmv", "index.html"), replace_between(template, "seo:summary", intro)):
        changed.append("fmv/ (intro)")

    # lastmod only where we know a real date (the latest fair value), so the file only changes when data does.
    newest = max(latest[t]["date"] for t in tickers)
    urls = [(f"{SITE}/", None), (f"{SITE}/fmv/", newest)]
    urls += [(f"{SITE}/fmv/{t.lower()}/", latest[t]["date"]) for t in tickers]
    urls += [(f"{SITE}/fmv/privacy", None), (f"{SITE}/options-ledger/privacy.html", None)]
    sitemap = ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
               + "".join(f"  <url><loc>{u}</loc>" + (f"<lastmod>{d}</lastmod>" if d else "") + "</url>\n" for u, d in urls)
               + "</urlset>\n")
    if write_if_changed(os.path.join(ROOT, "sitemap.xml"), sitemap):
        changed.append("sitemap.xml")
    robots = f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n"
    if write_if_changed(os.path.join(ROOT, "robots.txt"), robots):
        changed.append("robots.txt")
    print(f"{len(tickers)} stock pages; changed: {', '.join(changed) or 'nothing'}")


if __name__ == "__main__":
    main()
