#!/usr/bin/env python3
import json, html
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
digest_path = ROOT / "docs/api/research-digest.json"
out = ROOT / "docs/feed.xml"

if digest_path.exists():
    data = json.loads(digest_path.read_text(encoding="utf-8"))
    items = data.get("papers", [])[:15]
else:
    items = []

rows = []
for p in items:
    rows.append(f"""<item>
<title>{html.escape(p.get('title',''))}</title>
<link>{html.escape(p.get('url',''))}</link>
<guid>{html.escape(p.get('url',''))}</guid>
<description>{html.escape(p.get('summary','')[:500])}</description>
</item>""")

rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>RA-PSI-2026 Research Digest</title>
<link>https://REPLACE-WITH-PUBLIC-URL/</link>
<description>Persistent cross-model research continuity digest.</description>
<lastBuildDate>{datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S +0000')}</lastBuildDate>
{''.join(rows)}
</channel></rss>"""
out.write_text(rss, encoding="utf-8")
print("Built", out)
