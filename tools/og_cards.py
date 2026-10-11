#!/usr/bin/env python3
"""Render the 1200x630 link-preview cards in assets/og/ with headless Chrome (run locally, commit the PNGs).

Cards carry no prices or fair values, so they never go stale and only need re-running if the design changes.
Usage: python3 tools/og_cards.py
"""
import html, os, subprocess, sys, tempfile, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "og")
CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
CARDS = {
    "fmv": ("Fair Market Value", "Magnificent 7"),
    "aapl": ("AAPL", "Apple"), "amzn": ("AMZN", "Amazon"), "googl": ("GOOGL", "Alphabet"), "meta": ("META", "Meta"),
    "msft": ("MSFT", "Microsoft"), "nvda": ("NVDA", "NVIDIA"), "tsla": ("TSLA", "Tesla"),
}

TEMPLATE = """<!DOCTYPE html><html><head><meta charset="utf-8"><style>
  html, body {{ margin:0; width:1200px; height:630px; overflow:hidden; background:#fff; color:#0f1f17;
    font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display","Segoe UI",Helvetica,Arial,sans-serif; }}
  .card {{ position:relative; box-sizing:border-box; width:1200px; height:630px; padding:72px 80px; }}
  .brand {{ font-size:34px; font-weight:700; letter-spacing:-.01em; }}
  .brand span {{ color:#14532d; }}
  h1 {{ font-size:{size}px; line-height:1; letter-spacing:-.04em; margin:84px 0 18px; font-weight:800; }}
  .sub {{ font-size:40px; color:#4a5650; }}
  .lines {{ position:absolute; left:80px; right:80px; bottom:72px; height:84px; }}
  .line {{ position:absolute; left:0; right:0; height:0; }}
  .bull {{ top:0; border-top:6px dotted #1a9e3a; }}
  .base {{ top:39px; border-top:6px dashed #d4a017; }}
  .bear {{ bottom:0; border-top:6px dotted #e5484d; }}
  .tags {{ position:absolute; right:80px; top:72px; font-size:28px; color:#4a5650; }}
</style></head><body><div class="card">
  <div class="brand"><span>Pear</span> Digitals</div>
  <div class="tags">Bear &middot; Base &middot; Bull</div>
  <h1>{title}</h1>
  <div class="sub">{sub}</div>
  <div class="lines"><div class="line bull"></div><div class="line base"></div><div class="line bear"></div></div>
</div></body></html>"""


def main():
    os.makedirs(OUT, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for slug, (title, name) in CARDS.items():
            sub = f"{name} fair value" if slug != "fmv" else "Bear, base &amp; bull fair values for the Magnificent 7"
            page = os.path.join(tmp, f"{slug}.html")
            with open(page, "w") as f:
                f.write(TEMPLATE.format(title=html.escape(title), sub=sub, size=150 if slug != "fmv" else 104))
            png = os.path.join(OUT, f"{slug}.png")
            if os.path.exists(png):
                os.remove(png)
            # Headless Chrome on macOS can linger after writing the screenshot, so wait for the file, then close it.
            proc = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                                     f"--user-data-dir={tmp}/prof-{slug}", "--window-size=1200,630",
                                     "--force-device-scale-factor=1", f"--screenshot={png}", f"file://{page}"],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(120):
                if os.path.exists(png) and os.path.getsize(png) > 0:
                    time.sleep(1)
                    break
                time.sleep(0.5)
            proc.kill()
            if not os.path.exists(png):
                sys.exit(f"Chrome did not write {png}")
            print("wrote", os.path.relpath(png, ROOT))


if __name__ == "__main__":
    sys.exit(main())
