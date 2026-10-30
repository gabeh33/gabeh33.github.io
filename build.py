#!/usr/bin/env python3
"""Builds the portfolio into dist/. Standard library only.

    python3 build.py            # build once
    python3 build.py --serve    # build, serve on http://localhost:4321, rebuild on save

Content lives in content/ (JSON + posts/*.html). Styles and scripts in src/.
"""
from __future__ import annotations

import html
import json
import os
import re
import shutil
import sys
import threading
import time
from datetime import date
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"
SRC = ROOT / "src"
DIST = ROOT / "dist"
PORT = int(os.environ.get("PORT", "4321"))

e = html.escape

ICONS = {
    "shield": '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="M9 12l2 2 4-4"/>',
    "radar": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4"/><path d="M12 12l6-6"/>',
    "board": '<rect x="3" y="4" width="18" height="12" rx="1.5"/><path d="M8 20l4-4 4 4"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>',
    "cap": '<path d="M2 9l10-5 10 5-10 5z"/><path d="M6 11v5c3 2 9 2 12 0v-5"/>',
    "briefcase": '<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2M3 13h18"/>',
    "terminal": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 9l3 3-3 3M13 15h4"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>',
    "trash": '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
    "badge": '<circle cx="12" cy="9" r="6"/><path d="M8.5 14L7 22l5-3 5 3-1.5-8"/>',
    "mail": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/>',
    "linkedin": '<rect x="3" y="3" width="18" height="18" rx="3"/><path d="M8 10v7M8 7v.01M12 17v-4a2 2 0 0 1 4 0v4M12 10v7"/>',
    "github": '<path d="M9 19c-4.3 1.4-4.3-2.5-6-3m12 5v-3.5c0-1 .1-1.4-.5-2 2.8-.3 5.5-1.4 5.5-6a4.6 4.6 0 0 0-1.3-3.2 4.2 4.2 0 0 0-.1-3.2s-1.1-.3-3.5 1.3a12.3 12.3 0 0 0-6.2 0C6.5 2.8 5.4 3.1 5.4 3.1a4.2 4.2 0 0 0-.1 3.2A4.6 4.6 0 0 0 4 9.5c0 4.6 2.7 5.7 5.5 6-.6.6-.6 1.2-.5 2V21"/>',
    "arrow": '<path d="M5 12h14M13 6l6 6-6 6"/>',
    "pen": '<path d="M4 20l4-1 11-11-3-3L5 16z"/><path d="M14 7l3 3"/>',
    "book": '<path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2z"/><path d="M4 19V5"/>',
    "pin": '<path d="M12 21s-7-6.2-7-12a7 7 0 0 1 14 0c0 5.8-7 12-7 12z"/><circle cx="12" cy="9" r="2.5"/>',
    "spark": '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5L18 18M6 18l2.5-2.5M15.5 8.5L18 6"/>',
}


def icon(name: str, size: int = 22) -> str:
    return (f'<svg class="i" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
            f'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
            f'aria-hidden="true">{ICONS[name]}</svg>')


def load(name: str):
    return json.loads((CONTENT / name).read_text())


def load_posts() -> list[dict]:
    posts = []
    for f in sorted((CONTENT / "posts").glob("*.html")):
        raw = f.read_text()
        m = re.match(r"\s*<!--(.*?)-->(.*)", raw, re.S)
        if not m:
            raise SystemExit(f"{f.name}: missing front matter comment")
        meta = json.loads(m.group(1))
        if meta.get("draft"):
            continue
        meta["slug"] = f.stem
        meta["body"] = m.group(2).strip()
        meta["read_min"] = max(1, round(len(re.sub(r"<[^>]+>", " ", meta["body"]).split()) / 220))
        posts.append(meta)
    posts.sort(key=lambda p: p["date"], reverse=True)
    return posts


def fmt_date(iso: str) -> str:
    return date.fromisoformat(iso).strftime("%b %-d, %Y")


# ---------- shared chrome ----------

def page(site: dict, *, title: str, desc: str, body: str, base: str, path: str, active: str = "") -> str:
    canonical = site["url"].rstrip("/") + "/" + path
    nav_items = [("About", "#top", "home"), ("Career", "#career", "home"), ("Projects", "#projects", "home"),
                 ("Certs", "#certs", "home"), ("Writing", "writing/", "writing")]
    links = []
    for label, href, kind in nav_items:
        url = (base + href) if not href.startswith("#") else (href if active == "home" else base + href)
        cur = ' aria-current="page"' if active == "writing" and kind == "writing" else ""
        links.append(f'<a href="{url}"{cur}>{label}</a>')
    ld = {"@context": "https://schema.org", "@type": "Person", "name": site["name"], "jobTitle": site["title"],
          "url": site["url"], "sameAs": [s["url"] for s in site["socials"] if s["url"].startswith("http")]}
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<meta name="author" content="{e(site['name'])}">
<link rel="canonical" href="{e(canonical)}">
<meta property="og:type" content="website">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{e(canonical)}">
<meta name="twitter:card" content="summary">
<meta name="theme-color" content="#f3f1ec">
<link rel="icon" href="{base}favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Alexandria:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{base}styles.css">
<script type="application/ld+json">{json.dumps(ld)}</script>
<script>document.documentElement.classList.add('js')</script>
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site-header">
  <div class="wrap nav">
    <a class="brand" href="{base}" aria-label="{e(site['name'])}, home">
      <span class="brand-mark">{e(site['short'])}</span><span class="brand-name">{e(site['name'])}</span>
    </a>
    <nav aria-label="Main">{''.join(links)}</nav>
    <a class="btn btn-small btn-green nav-cta" href="mailto:{e(site['email'])}">Contact</a>
  </div>
</header>
<main id="main">
{body}
</main>
<footer class="site-footer">
  <div class="wrap footer-inner">
    <div class="footer-socials">
      {''.join(f'<a class="sticker-icon bg-{s["color"]}" href="{e(s["url"])}" aria-label="{e(s["name"])}"' + (' target="_blank" rel="noopener"' if s["url"].startswith("http") else '') + f'>{icon(s["icon"])}</a>' for s in site["socials"])}
    </div>
    <p>&copy; {date.today().year} {e(site['name'])}</p>
  </div>
</footer>
<script src="{base}main.js" defer></script>
</body>
</html>
"""


# ---------- home sections ----------

def hero(site: dict) -> str:
    if site.get("photo"):
        portrait = f'<img src="{e(site["photo"])}" alt="{e(site["name"])}" width="320" height="360">'
    else:
        portrait = f'<div class="monogram" aria-hidden="true">{e(site["short"])}</div>'
    socials = "".join(
        f'<a class="btn btn-white" href="{e(s["url"])}"' + (' target="_blank" rel="noopener"' if s["url"].startswith("http") else "")
        + f'>{icon(s["icon"], 18)}{e(s["name"])}</a>'
        for s in site["socials"] if s["name"] != "Email")
    return f"""
<section class="hero wrap" id="top">
  <div class="hero-text">
    <p class="kicker">{e(site['kicker'])}</p>
    <h1>{e(site['headline'])}</h1>
    <p class="lede">{e(site['intro'])}</p>
    <p class="status"><span class="pulse" aria-hidden="true"></span>{e(site['status'])}</p>
    <div class="hero-actions">
      <a class="btn btn-green" href="mailto:{e(site['email'])}">{icon('mail', 18)}Get in touch</a>
      {socials}
    </div>
  </div>
  <div class="hero-art" aria-hidden="false">
    <div class="portrait">{portrait}</div>
    <span class="float-sticker s1 bg-pink">{icon('shield', 26)}</span>
    <span class="float-sticker s2 bg-orange round">{icon('radar', 24)}</span>
    <span class="float-sticker s3 bg-yellow">{icon('terminal', 22)}</span>
    <span class="name-tag bg-green">{icon('pin', 16)}{e(site['location'])}</span>
  </div>
</section>"""


def section_head(eyebrow: str, title: str, sub: str = "") -> str:
    return (f'<div class="section-head"><p class="eyebrow">{e(eyebrow)}</p><h2>{e(title)}</h2>'
            + (f'<p class="section-sub">{e(sub)}</p>' if sub else "") + "</div>")


COLOR_BY_TYPE = {"work": "blue", "education": "pink"}


def career(items: list[dict]) -> str:
    rows = []
    for i, it in enumerate(items):
        side = "left" if i % 2 == 0 else "right"
        color = "green" if i == 0 else COLOR_BY_TYPE.get(it["type"], "orange")
        pts = "".join(f"<li>{e(p)}</li>" for p in it["points"])
        tags = "".join(f'<span class="tag">{e(t)}</span>' for t in it["tags"])
        rows.append(f"""
    <li class="tl-item {side} reveal" data-type="{e(it['type'])}">
      <span class="tl-node bg-{color}">{icon(it['icon'], 20)}</span>
      <article class="card tl-card">
        <div class="tl-meta"><span class="mono">{e(it['period'])}</span><span class="chip bg-{COLOR_BY_TYPE.get(it['type'], 'orange')}">{e(it['label'])}</span></div>
        <h3>{e(it['role'])}</h3>
        <p class="tl-org">{e(it['org'])} <span>· {e(it['place'])}</span></p>
        <ul class="tl-points">{pts}</ul>
        <div class="tags">{tags}</div>
      </article>
    </li>""")
    return f"""
<section class="section wrap" id="career">
  <div class="section-row">
    {section_head('Career', 'Where I have been', 'From auditing SOX controls to running a SOC. Newest first.')}
    <div class="filters" role="group" aria-label="Filter timeline">
      <button class="filter is-on" data-filter="all" aria-pressed="true">All</button>
      <button class="filter" data-filter="work" aria-pressed="false">{icon('briefcase', 16)}Work</button>
      <button class="filter" data-filter="education" aria-pressed="false">{icon('cap', 16)}Education</button>
    </div>
  </div>
  <ol class="timeline">{''.join(rows)}
  </ol>
</section>"""


def projects(data: dict, base: str) -> str:
    cards = []
    for p in data["featured"]:
        links = "".join(
            f'<a class="link-btn" href="{e((base + l["url"]) if l.get("internal") else l["url"])}"'
            + ("" if l.get("internal") else ' target="_blank" rel="noopener"')
            + f'>{icon(l["icon"], 16)}{e(l["label"])}{icon("arrow", 16)}</a>'
            for l in p["links"])
        if not links:
            links = '<span class="private-note">Code available on request.</span>'
        tags = "".join(f'<span class="tag">{e(t)}</span>' for t in p["tags"])
        cards.append(f"""
    <article class="card project reveal">
      <div class="project-top">
        <span class="tile bg-{p['color']}">{icon(p['icon'], 24)}</span>
        <span class="chip">{e(p['category'])}</span>
      </div>
      <h3>{e(p['title'])}</h3>
      <p>{e(p['summary'])}</p>
      <div class="angle"><span class="angle-label">{icon('shield', 16)}Security angle</span><p>{e(p['angle'])}</p></div>
      <div class="tags">{tags}</div>
      <div class="project-links">{links}</div>
    </article>""")
    course = "".join(f"""
      <li><a href="{e(c['url'])}" target="_blank" rel="noopener"><span class="cw-title">{e(c['title'])}</span><span class="cw-sum">{e(c['summary'])}</span>{icon('arrow', 18)}</a></li>"""
                     for c in data["coursework"])
    return f"""
<section class="section wrap" id="projects">
  {section_head('Projects', 'Things I have built', 'Side projects I run every day. Each one had a security decision worth explaining.')}
  <div class="grid">{''.join(cards)}
  </div>
  <div class="card coursework reveal">
    <div class="coursework-head"><span class="tile bg-blue">{icon('book', 22)}</span><div><h3>Coursework and labs</h3><p>Offensive and systems work from Northeastern.</p></div></div>
    <ul>{course}
    </ul>
  </div>
</section>"""


def certs(items: list[dict]) -> str:
    cards = "".join(f"""
    <li class="cert reveal">
      <span class="cert-code bg-{c['color']}">{e(c['code'])}</span>
      <div><p class="cert-name">{e(c['name'])}</p><p class="cert-meta">{e(c['issuer'])} · {e(c['date'])}</p></div>
    </li>""" for c in items)
    return f"""
<section class="section wrap" id="certs">
  {section_head('Certifications', 'Seven certs in 18 months', 'Microsoft identity and M365 administration, plus the CompTIA trifecta.')}
  <ul class="certs">{cards}
  </ul>
</section>"""


def post_card(p: dict, base: str) -> str:
    tags = "".join(f'<span class="tag">{e(t)}</span>' for t in p.get("tags", []))
    return f"""
    <article class="card post-card reveal">
      <p class="mono">{fmt_date(p['date'])} · {p['read_min']} min read</p>
      <h3><a href="{base}writing/{p['slug']}/">{e(p['title'])}</a></h3>
      <p>{e(p['summary'])}</p>
      <div class="tags">{tags}</div>
    </article>"""


def writing_preview(posts: list[dict], base: str) -> str:
    if not posts:
        return ""
    cards = "".join(post_card(p, base) for p in posts[:3])
    return f"""
<section class="section wrap" id="writing">
  <div class="section-row">
    {section_head('Writing', 'Notes from the work', 'Write-ups on detections, incidents, and the tools I build.')}
    <a class="btn btn-white" href="{base}writing/">All posts{icon('arrow', 18)}</a>
  </div>
  <div class="grid posts">{cards}
  </div>
</section>"""


def contact(site: dict) -> str:
    items = "".join(
        f'<a class="card contact-card bg-{s["color"]}-soft" href="{e(s["url"])}"' + (' target="_blank" rel="noopener"' if s["url"].startswith("http") else "")
        + f'><span class="tile bg-{s["color"]}">{icon(s["icon"], 22)}</span><span><strong>{e(s["name"])}</strong><span class="handle">{e(s["handle"])}</span></span>{icon("arrow", 18)}</a>'
        for s in site["socials"])
    return f"""
<section class="section wrap" id="contact">
  <div class="card contact reveal">
    <div>
      <p class="eyebrow">Contact</p>
      <h2>Hiring for IR, detection, or cloud security?</h2>
      <p class="section-sub">Email is the fastest way to reach me.</p>
    </div>
    <div class="contact-list">{items}</div>
  </div>
</section>"""


# ---------- build ----------

def build() -> None:
    site = load("site.json")
    posts = load_posts()
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    for f in SRC.iterdir():
        if f.is_file():
            shutil.copy2(f, DIST / f.name)
    if (SRC / "img").is_dir():
        shutil.copytree(SRC / "img", DIST / "img")

    body = (hero(site) + career(load("career.json")) + projects(load("projects.json"), "")
            + certs(load("certs.json")) + writing_preview(posts, "") + contact(site))
    (DIST / "index.html").write_text(page(
        site, title=f"{site['name']} | {site['title']}", desc=site["description"],
        body=body, base="", path="", active="home"))

    # writing index
    wdir = DIST / "writing"
    wdir.mkdir()
    listing = "".join(post_card(p, "../") for p in posts) or '<p class="section-sub">Posts coming soon.</p>'
    (wdir / "index.html").write_text(page(
        site, title=f"Writing | {site['name']}", desc="Write-ups on detections, incidents, and security tooling.",
        body=f'<section class="section wrap first">{section_head("Writing", "Notes from the work", "Write-ups on detections, incidents, and the tools I build.")}<div class="grid posts">{listing}</div></section>',
        base="../", path="writing/", active="writing"))

    # posts
    for p in posts:
        d = wdir / p["slug"]
        d.mkdir()
        tags = "".join(f'<span class="tag">{e(t)}</span>' for t in p.get("tags", []))
        article = f"""
<article class="wrap post first">
  <a class="back" href="../">{icon('arrow', 16)}All writing</a>
  <header class="post-head">
    <p class="mono">{fmt_date(p['date'])} · {p['read_min']} min read</p>
    <h1>{e(p['title'])}</h1>
    <p class="lede">{e(p['summary'])}</p>
    <div class="tags">{tags}</div>
  </header>
  <div class="prose">{p['body']}</div>
  <div class="card post-end">
    <p>Questions or a role you think I'd fit? <a href="mailto:{e(site['email'])}">Email me</a>.</p>
  </div>
</article>"""
        (d / "index.html").write_text(page(
            site, title=f"{p['title']} | {site['name']}", desc=p["summary"], body=article,
            base="../../", path=f"writing/{p['slug']}/", active="writing"))

    (DIST / "404.html").write_text(page(
        site, title=f"Not found | {site['name']}", desc="Page not found.", base="/", path="404.html",
        body='<section class="section wrap first notfound"><p class="eyebrow">404</p><h1>Nothing here.</h1><p class="lede">That page doesn\'t exist.</p><a class="btn btn-green" href="/">Back home</a></section>'))
    (DIST / ".nojekyll").write_text("")
    (DIST / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {site['url'].rstrip('/')}/sitemap.xml\n")
    urls = [""] + ["writing/"] + [f"writing/{p['slug']}/" for p in posts]
    (DIST / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{site['url'].rstrip('/')}/{u}</loc></url>\n" for u in urls) + "</urlset>\n")
    print(f"Built {len(posts)} post(s) into {DIST.relative_to(ROOT)}/", flush=True)


def snapshot() -> float:
    return max((f.stat().st_mtime for d in (CONTENT, SRC) for f in d.rglob("*") if f.is_file()),
               default=0) + (ROOT / "build.py").stat().st_mtime


def watch() -> None:
    last = snapshot()
    while True:
        time.sleep(1)
        now = snapshot()
        if now != last:
            last = now
            try:
                build()
            except Exception as ex:  # keep serving on a bad edit
                print(f"Build failed: {ex}", flush=True)


def serve() -> None:
    build()
    threading.Thread(target=watch, daemon=True).start()
    handler = partial(SimpleHTTPRequestHandler, directory=str(DIST))
    handler.log_message = lambda *a: None
    server = ThreadingHTTPServer(("127.0.0.1", PORT), handler)
    print(f"Preview at http://localhost:{PORT}  (rebuilds on save, Ctrl+C to stop)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    serve() if "--serve" in sys.argv else build()
