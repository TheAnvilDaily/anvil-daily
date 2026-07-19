#!/usr/bin/env python3
"""
newsbot_anvil.py v3 — The Anvil Daily automated news aggregator
- OG image extraction
- Reliable index.html injection via BOT: markers
Run fix_index.py ONCE before first use to add markers to index.html
"""

import os, json, hashlib, logging, re, subprocess, time
from datetime import datetime, timezone
from pathlib import Path
from difflib import SequenceMatcher
from urllib.request import urlopen, Request
from urllib.error import URLError

import feedparser
import anthropic

REPO_ROOT        = Path(__file__).parent.parent
POSTS_DIR        = REPO_ROOT / "public" / "posts"
POSTED_IDS_FILE  = Path(__file__).parent / "posted_ids.json"
LOG_FILE         = Path(__file__).parent / "newsbot.log"
MAX_PER_SOURCE   = 3
SIMILARITY_LIMIT = 0.75

RSS_SOURCES = [
    {"name": "Fox News",           "url": "https://moxie.foxnews.com/google-publisher/politics.xml", "category": "Politics"},
    {"name": "NY Post",            "url": "https://nypost.com/feed/",                                "category": "Politics"},
    {"name": "Daily Wire",         "url": "https://www.dailywire.com/feeds/rss.xml",                 "category": "Politics"},
    {"name": "Washington Examiner","url": "https://www.washingtonexaminer.com/feed",                 "category": "Politics"},
    {"name": "National Review",    "url": "https://www.nationalreview.com/feed/",                    "category": "Politics"},
    {"name": "The Federalist",     "url": "https://thefederalist.com/feed/",                         "category": "Culture"},
    {"name": "Townhall",           "url": "https://townhall.com/api/syndication/rss/columnists",     "category": "Politics"},
    {"name": "Breitbart",          "url": "https://feeds.feedburner.com/breitbart",                  "category": "Politics"},
    {"name": "Washington Times",   "url": "https://www.washingtontimes.com/rss/headlines/news/politics/", "category": "Politics"},
    {"name": "RealClearPolitics",  "url": "https://www.realclearpolitics.com/index.xml",             "category": "Election"},
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

def load_ids():
    if POSTED_IDS_FILE.exists():
        try: return json.loads(POSTED_IDS_FILE.read_text())
        except: return {}
    return {}

def save_ids(ids):
    POSTED_IDS_FILE.write_text(json.dumps(ids, indent=2))

def uid(url): return hashlib.md5(url.encode()).hexdigest()[:12]

def similar(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio() > SIMILARITY_LIMIT

def slugify(text):
    text = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[\s_]+", "-", text)[:60].strip("-")

def get_og_image(url):
    try:
        req = Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; AnvilDailyBot/3.0)",
            "Accept": "text/html,application/xhtml+xml",
        })
        with urlopen(req, timeout=5) as resp:
            chunk = resp.read(51200).decode("utf-8", errors="ignore")
        for pattern in [
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
            r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',
        ]:
            m = re.search(pattern, chunk, re.I)
            if m:
                img = m.group(1).strip()
                if img.startswith("//"): img = "https:" + img
                if img.startswith("http"): return img
    except Exception as ex:
        log.debug(f"  OG fetch failed: {ex}")
    return None

def fetch(source):
    try:
        feed = feedparser.parse(source["url"], agent="AnvilDailyBot/3.0")
        out = []
        for e in feed.entries[:MAX_PER_SOURCE]:
            t = e.get("title","").strip()
            l = e.get("link","").strip()
            s = re.sub(r"<[^>]+>","", e.get("summary", e.get("description",""))).strip()[:500]
            img = None
            if hasattr(e, "media_content") and e.media_content:
                img = e.media_content[0].get("url")
            if not img and hasattr(e, "enclosures") and e.enclosures:
                enc = e.enclosures[0]
                if enc.get("type","").startswith("image"):
                    img = enc.get("url")
            if t and l:
                out.append({"title":t,"link":l,"summary":s,"source":source["name"],
                           "category":source["category"],"rss_image":img})
        log.info(f"  {source['name']}: {len(out)} entries")
        return out
    except Exception as ex:
        log.warning(f"  {source['name']}: {ex}")
        return []

def commentary(article, client):
    try:
        r = client.messages.create(
            model="claude-haiku-4-5", max_tokens=400,
            messages=[{"role":"user","content":f"""You write punchy populist conservative commentary for The Anvil Daily.
Write 2-3 short paragraphs for the "Why This Matters" section.
Drudge Report energy. Direct. No hedging. Talk to real Americans.
Title: {article['title']}
Source: {article['source']}
Summary: {article['summary']}
Return ONLY the commentary text, no labels or headers."""}]
        )
        return r.content[0].text.strip()
    except Exception as ex:
        log.warning(f"  Commentary failed: {ex}")
        return "This story is developing. Check back for analysis as details emerge."

def build_html(article, wtm, post_id, image_url=None):
    ts = datetime.now(timezone.utc).strftime("%B %d, %Y · %I:%M %p UTC")
    wtm_html = "\n".join(f"<p>{p.strip()}</p>" for p in wtm.split("\n") if p.strip())
    title_esc = article['title'].replace('"','&quot;').replace("'","&#39;").replace("<","&lt;").replace(">","&gt;")
    if image_url:
        hero = f'<img src="{image_url}" alt="{title_esc}" style="width:100%;aspect-ratio:16/9;object-fit:cover;border-radius:2px;margin-bottom:28px;display:block;">'
    else:
        hero = '<div style="width:100%;aspect-ratio:16/9;background:#f0f0f0;background-image:radial-gradient(rgba(11,11,12,0.08) 1px,transparent 1.4px);background-size:7px 7px;border-radius:2px;margin-bottom:28px;display:flex;align-items:center;justify-content:center;"><span style="font-family:monospace;font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#aaa">Photograph</span></div>'
    og_img = f'<meta property="og:image" content="{image_url}">' if image_url else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title_esc} -- The Anvil Daily</title>
<meta name="description" content="{article['summary'][:160]}">
<meta property="og:title" content="{title_esc}">
<meta property="og:type" content="article">
{og_img}
<link rel="icon" type="image/svg+xml" href="/assets/logo-mark.svg">
<link rel="canonical" href="https://anvildaily.com/posts/{post_id}/">
<link rel="stylesheet" href="/styles.css">
<link rel="stylesheet" href="/tokens/colors.css">
<link rel="stylesheet" href="/tokens/fonts.css">
<style>
*{{box-sizing:border-box}}html,body{{margin:0;background:#fff;color:#0B0B0C;font-family:var(--font-sans,-apple-system,sans-serif);-webkit-font-smoothing:antialiased}}
a{{color:inherit}}.wrap{{max-width:800px;margin:0 auto;padding:0 24px}}
.hdr{{border-bottom:1px solid #e5e5e5;padding:16px 0;display:flex;align-items:center;justify-content:space-between}}
.logo{{font-family:var(--font-display,Georgia,serif);font-weight:800;font-size:24px;letter-spacing:-.025em;color:#0B0B0C;text-decoration:none}}
.logo span{{color:#D6231F}}.back{{font-size:12px;font-family:monospace;letter-spacing:.08em;text-transform:uppercase;color:#888;text-decoration:none}}
.art{{padding:48px 0 80px}}.kat{{font-family:monospace;font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#D6231F;margin-bottom:12px}}
h1{{font-family:var(--font-display,Georgia,serif);font-weight:800;font-size:clamp(26px,4vw,42px);line-height:1.15;letter-spacing:-.02em;color:#0B0B0C;margin:0 0 18px}}
.meta{{font-size:12px;font-family:monospace;color:#888;margin-bottom:28px;padding-bottom:20px;border-bottom:1px solid #e5e5e5}}
.src-btn{{display:inline-block;margin-bottom:28px;font-size:13px;font-weight:700;color:#D6231F;text-decoration:none;border:1.5px solid #D6231F;padding:8px 16px;border-radius:2px}}
.src-btn:hover{{background:#D6231F;color:#fff}}
.summ{{font-size:16px;line-height:1.65;color:#555;margin-bottom:36px;padding:18px 20px;background:#f7f7f7;border-left:3px solid #ccc}}
.wtm{{background:#0B0B0C;color:#fff;padding:28px 30px;border-radius:2px;margin-bottom:40px}}
.wtm-label{{font-family:monospace;font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:#D6231F;margin-bottom:14px}}
.wtm p{{font-size:15px;line-height:1.65;margin:0 0 12px;color:rgba(255,255,255,.9)}}
.wtm p:last-child{{margin:0}}
footer{{background:#0B0B0C;color:rgba(255,255,255,.4);padding:24px 0;text-align:center;font-family:monospace;font-size:11px;letter-spacing:.08em;text-transform:uppercase}}
</style>
</head>
<body>
<header><div class="wrap hdr">
  <a href="/" class="logo">The Anvil<span> Daily</span></a>
  <a href="/" class="back">All Stories</a>
</div></header>
<main class="art"><div class="wrap">
  {hero}
  <div class="kat">{article['category']} -- {article['source']}</div>
  <h1>{article['title']}</h1>
  <div class="meta">Published {ts}</div>
  <a href="{article['link']}" target="_blank" rel="noopener" class="src-btn">Read full story at {article['source']} &rarr;</a>
  <div class="summ">{article['summary']}</div>
  <div class="wtm">
    <div class="wtm-label">Why This Matters</div>
    {wtm_html}
  </div>
</div></main>
<footer>2026 The Anvil Daily &middot; anvildaily.com</footer>
</body></html>"""

def rebuild_index(all_posts):
    index_path = REPO_ROOT / "public" / "index.html"
    if not index_path.exists():
        log.warning("index.html not found"); return
    content = index_path.read_text(encoding="utf-8")
    if "BOT:TOP_THREE_START" not in content or "BOT:LATEST_START" not in content:
        log.warning("Injectable markers missing - run fix_index.py first"); return

    def make_img(p, style="width:100%;aspect-ratio:16/9;object-fit:cover;border-radius:2px;"):
        if p.get("image_url"):
            return f'<img src="{p["image_url"]}" alt="" style="{style}">'
        return '<div class="placeholder" style="width:100%;aspect-ratio:16/9;"><span class="placeholder-label">Photograph</span></div>'

    def esc(t): return t.replace("<","&lt;").replace(">","&gt;").replace('"','&quot;')

    # Feed rows
    feed_rows = ""
    for p in all_posts[:20]:
        if p.get("image_url"):
            thumb = f'<img src="{p["image_url"]}" alt="" style="width:96px;height:72px;object-fit:cover;border-radius:2px;flex:0 0 96px;">'
        else:
            thumb = '<div class="placeholder" style="width:96px;height:72px;flex:0 0 96px;"><span class="placeholder-label">Photo</span></div>'
        feed_rows += f"""
        <div class="row"><a href="/posts/{p['id']}/" class="story compact"><article style="display:flex;gap:14px;align-items:flex-start;">
          {thumb}
          <div class="body">
            <div class="head"><span class="kicker">{p['category']}</span></div>
            <h3>{esc(p['title'])}</h3>
            <p class="byline"><strong>{p['source']}</strong> &middot; Just now &middot; 3 min</p>
          </div>
        </article></a></div>"""

    hero_posts = all_posts[:3] if len(all_posts) >= 3 else all_posts
    lead_html = ""
    if hero_posts:
        p = hero_posts[0]
        lead_html = f"""<a href="/posts/{p['id']}/" class="story lead"><article>
            <div class="media-wrap lead-ratio">{make_img(p)}</div>
            <div class="head"><span class="rank">01</span><span class="kicker accent">{p['category']}</span></div>
            <h3>{esc(p['title'])}</h3>
            <p class="standfirst">{esc(p['summary'][:180])}...</p>
            <p class="byline"><strong>{p['source']}</strong> &middot; Just now &middot; 4 min read</p>
          </article></a>"""

    secondaries_html = "<div class='secondaries'>"
    for i, p in enumerate(hero_posts[1:3], 2):
        cls = "bottom" if i == 3 else ""
        secondaries_html += f"""<div class='pair {cls}'><a href="/posts/{p['id']}/" class="story feature"><article>
            <div class="media-wrap feature-ratio">{make_img(p, "width:100%;aspect-ratio:3/2;object-fit:cover;border-radius:2px;")}</div>
            <div class="head"><span class="rank">0{i}</span><span class="kicker">{p['category']}</span></div>
            <h3>{esc(p['title'])}</h3>
            <p class="standfirst">{esc(p['summary'][:140])}...</p>
            <p class="byline"><strong>{p['source']}</strong> &middot; Just now &middot; 3 min read</p>
          </article></a></div>"""
    secondaries_html += "</div>"

    new_top_three = f"""<!-- BOT:TOP_THREE_START -->
      <div class="top-three">
        {lead_html}
        {secondaries_html}
      </div>
      <!-- BOT:TOP_THREE_END -->"""

    new_feed = f"""<!-- BOT:LATEST_START -->
      <div class="latest-feed">{feed_rows}
      </div>
      <!-- BOT:LATEST_END -->"""

    content = re.sub(r'<!-- BOT:TOP_THREE_START -->.*?<!-- BOT:TOP_THREE_END -->', new_top_three, content, flags=re.DOTALL)
    content = re.sub(r'<!-- BOT:LATEST_START -->.*?<!-- BOT:LATEST_END -->', new_feed, content, flags=re.DOTALL)
    index_path.write_text(content, encoding="utf-8")
    log.info(f"  Homepage rebuilt with {len(all_posts)} posts")

def git_push():
    try:
        subprocess.run(["git","add","-A"], cwd=REPO_ROOT, check=True, capture_output=True)
        r = subprocess.run(["git","diff","--cached","--quiet"], cwd=REPO_ROOT, capture_output=True)
        if r.returncode == 0:
            log.info("  No changes to commit"); return
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        subprocess.run(["git","commit","-m",f"bot: {ts}"], cwd=REPO_ROOT, check=True, capture_output=True)
        subprocess.run(["git","push","origin","main"], cwd=REPO_ROOT, check=True, capture_output=True)
        log.info("  Pushed to GitHub - Cloudflare rebuilding")
    except subprocess.CalledProcessError as ex:
        log.error(f"  Git error: {ex.stderr.decode() if ex.stderr else ex}")

def main():
    log.info("="*55)
    log.info("Anvil Daily newsbot v3 starting")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log.error("ANTHROPIC_API_KEY not set"); return
    client = anthropic.Anthropic(api_key=api_key)
    posted = load_ids()
    seen_titles = posted.get("titles", [])
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    new_posts = []

    for source in RSS_SOURCES:
        log.info(f"Fetching {source['name']}...")
        for art in fetch(source):
            h = uid(art["link"])
            if h in posted: continue
            if any(similar(art["title"], t) for t in seen_titles):
                log.info(f"  Dupe skip: {art['title'][:55]}"); continue
            image_url = art.get("rss_image")
            if not image_url:
                log.info(f"  Fetching OG image for: {art['title'][:45]}")
                image_url = get_og_image(art["link"])
                if image_url:
                    log.info(f"  Got image: {image_url[:60]}")
                else:
                    log.info(f"  No image found, using placeholder")
            log.info(f"  Writing: {art['title'][:55]}")
            wtm = commentary(art, client)
            ts_slug = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
            post_id = f"{ts_slug}-{slugify(art['title'])}"
            post_dir = POSTS_DIR / post_id
            post_dir.mkdir(parents=True, exist_ok=True)
            (post_dir / "index.html").write_text(build_html(art, wtm, post_id, image_url), encoding="utf-8")
            posted[h] = {"title": art["title"], "at": datetime.now(timezone.utc).isoformat()}
            seen_titles.append(art["title"])
            new_posts.append({
                "id": post_id,
                "title": art["title"],
                "summary": art["summary"][:180],
                "source": art["source"],
                "category": art["category"],
                "image_url": image_url,
            })

    if len(posted) > 600:
        keys = [k for k in posted if k != "titles"]
        for k in keys[:-500]: del posted[k]
    posted["titles"] = seen_titles[-300:]
    save_ids(posted)

    if new_posts:
        log.info(f"New posts: {len(new_posts)}. Rebuilding and pushing...")
        rebuild_index(new_posts)
        git_push()
    else:
        log.info("No new posts this run")
    log.info("Done")

if __name__ == "__main__":
    main()
