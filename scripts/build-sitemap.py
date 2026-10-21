#!/usr/bin/env python3
"""Regenerate sitemap.xml from the page folders of the static export.

Run from the repo root: python3 -I scripts/build-sitemap.py
Idempotent: the output depends only on the files on disk.
"""
import os
import re
import sys
from xml.sax.saxutils import escape

BASE_URL = "https://tonus.kiev.ua"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

IGNORE_DIRS = {
    ".git", "wp-content", "wp-includes", "wp-json", "cdn-cgi",
    ".claude", ".specify", "scripts", "node_modules", ".vercel",
}

# Root-level folders that duplicate a ru/ or uk/ twin and are 301-redirected
# by vercel.json. They stay on disk but must not be listed in the sitemap.
EXCLUDED_ROOT_SLUGS = {
    "bytovoj-alkogolizm",
    "kriptovaljuta-bitkojn-lovushka",
    "kto-takoj-volontjor",
    "shho-take-himichna-zalezhnist",
    "terapevtichne-seredovishhe",
    "test-na-narkotichni-rechovini-instrukcija-ta-vidminnosti",
    "testi-na-narkotiki",
}

MODIFIED_RE = re.compile(
    r'<meta[^>]+property=["\']article:modified_time["\'][^>]+content=["\']([^"\']+)["\']'
    r'|<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']article:modified_time["\']',
    re.IGNORECASE,
)
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def lastmod_for(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        html = fh.read()
    m = MODIFIED_RE.search(html)
    if not m:
        return None
    d = DATE_RE.match((m.group(1) or m.group(2)).strip())
    return d.group(0) if d else None


def collect():
    pages = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        rel = os.path.relpath(dirpath, ROOT)
        rel = "" if rel == "." else rel.replace(os.sep, "/")
        if rel == "":
            dirnames[:] = [
                d for d in dirnames
                if d not in IGNORE_DIRS and d not in EXCLUDED_ROOT_SLUGS
            ]
        else:
            dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        dirnames.sort()
        if "index.html" not in filenames:
            continue
        url = BASE_URL + "/" if rel == "" else f"{BASE_URL}/{rel}"
        pages.append((url, lastmod_for(os.path.join(dirpath, "index.html"))))
    pages.sort(key=lambda p: p[0])
    return pages


def render(pages):
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for url, lastmod in pages:
        out.append("  <url>")
        out.append(f"    <loc>{escape(url)}</loc>")
        if lastmod:
            out.append(f"    <lastmod>{escape(lastmod)}</lastmod>")
        out.append("  </url>")
    out.append("</urlset>")
    return "\n".join(out) + "\n"


def main():
    pages = collect()
    target = os.path.join(ROOT, "sitemap.xml")
    with open(target, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(render(pages))
    print(f"sitemap.xml: {len(pages)} URLs written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
