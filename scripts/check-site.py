#!/usr/bin/env python3
"""Consistency checks for the tonus.kiev.ua static export.

Run from the repo root:  python3 -I scripts/check-site.py
Python 3 stdlib only. Read-only: never modifies a file.
Prints one PASS/FAIL line per check (WARN lines are informational and do not
change the exit code). Exit code 1 if any check fails.
"""
import datetime
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://tonus.kiev.ua"
IGNORE_DIRS = {".git", "wp-content", "wp-includes", "wp-json", "cdn-cgi",
               ".claude", ".specify", "scripts"}
SM_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
DUPLICATES = {
    "bytovoj-alkogolizm": "/ru/bytovoj-alkogolizm",
    "kriptovaljuta-bitkojn-lovushka": "/ru/kriptovaljuta-bitkojn-lovushka",
    "kto-takoj-volontjor": "/ru/kto-takoj-volontjor",
    "shho-take-himichna-zalezhnist": "/uk/shho-take-himichna-zalezhnist",
    "terapevtichne-seredovishhe": "/uk/terapevtichne-seredovishhe",
    "test-na-narkotichni-rechovini-instrukcija-ta-vidminnosti":
        "/uk/test-na-narkotichni-rechovini-instrukcija-ta-vidminnosti",
    "testi-na-narkotiki": "/uk/testi-na-narkotiki",
}
EXPECTED_PAGES = 516
EXPECTED_SITEMAP = EXPECTED_PAGES - len(DUPLICATES)
MAX_ITEMS = 20

results = []  # (status, name, detail, items)


def report(name, failures, detail="", warn=False):
    status = "PASS" if not failures else ("WARN" if warn else "FAIL")
    results.append((status, name, detail, failures))
    line = "%-4s  %s" % (status, name)
    if detail:
        line += "  [%s]" % detail
    if failures:
        line += "  (%d problem%s)" % (len(failures), "" if len(failures) == 1 else "s")
    print(line, flush=True)
    for item in failures[:MAX_ITEMS]:
        print("        - " + item)
    if len(failures) > MAX_ITEMS:
        print("        ... and %d more" % (len(failures) - MAX_ITEMS))


def read(rel):
    with open(os.path.join(ROOT, rel), "rb") as fh:
        return fh.read().decode("utf-8", errors="replace")


def page_url(rel):
    return BASE + "/" if rel == "" else BASE + "/" + rel


def path_to_rel(path):
    """'/' -> '', '/x/y' -> 'x/y'. Returns None if the path is malformed."""
    if not path.startswith("/"):
        return None
    if path == "/":
        return ""
    if path.endswith("/") or "//" in path:
        return None
    return path[1:]


def url_to_rel(url):
    """Absolute https://tonus.kiev.ua URL -> page rel, or None."""
    if url == BASE + "/":
        return ""
    if not url.startswith(BASE + "/"):
        return None
    parts = urlsplit(url)
    if parts.query or parts.fragment:
        return None
    return path_to_rel(unquote(parts.path))


def page_exists(rel):
    return rel is not None and os.path.isfile(os.path.join(ROOT, rel, "index.html"))


def collect_pages():
    pages = []
    for d, dirs, files in os.walk(ROOT):
        rel = os.path.relpath(d, ROOT).replace(os.sep, "/")
        rel = "" if rel == "." else rel
        if rel == "":
            dirs[:] = [x for x in dirs if x not in IGNORE_DIRS]
        dirs.sort()
        if "index.html" in files:
            pages.append(rel)
    return sorted(pages)


class TagCollector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = []  # (tag, attrs dict, raw text)
        self.html_lang = None
        self.seen = set()

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v if v is not None else "") for k, v in attrs}
        self.seen.add(tag)
        if tag == "html" and self.html_lang is None:
            self.html_lang = a.get("lang")
        if tag in ("link", "meta", "a"):
            self.tags.append((tag, a, self.get_starttag_text() or ""))

    handle_startendtag = handle_starttag


def parse_html(text):
    p = TagCollector()
    p.feed(text)
    p.close()
    return p


def primary(lang):
    return lang.split("-")[0].lower() if lang else None


# ---------------------------------------------------------------- check 1
def check_files():
    # robots.txt
    f = []
    try:
        robots = read("robots.txt")
        lines = {ln.strip() for ln in robots.splitlines()}
        for need in ("Sitemap: https://tonus.kiev.ua/sitemap.xml",
                     "Disallow: /wp-json/", "Disallow: /wp-includes/",
                     "Disallow: /cdn-cgi/"):
            if need not in lines:
                f.append("robots.txt missing line %r" % need)
        if "User-agent: *" not in lines:
            f.append("robots.txt has no 'User-agent: *' group")
        if "Disallow: /" in lines:
            f.append("robots.txt contains 'Disallow: /' (blocks the whole site)")
    except OSError as e:
        f.append("robots.txt unreadable: %s" % e)
    report("1a robots.txt", f)

    # 404.html
    f = []
    try:
        text = read("404.html")
        p = parse_html(text)
        for t in ("html", "head", "body", "title"):
            if t not in p.seen:
                f.append("404.html has no <%s>" % t)
        if p.html_lang != "uk":
            f.append("404.html <html lang> is %r, expected 'uk'" % p.html_lang)
        robots = [a.get("content", "") for t, a, _ in p.tags
                  if t == "meta" and a.get("name", "").lower() == "robots"]
        if not any("noindex" in c.lower() for c in robots):
            f.append("404.html has no <meta name=robots content=noindex> (found %r)" % robots)
        if not any(t == "a" and a.get("href") == "tel:+380951046244" for t, a, _ in p.tags):
            f.append("404.html has no <a href=\"tel:+380951046244\">")
        for m in re.finditer(r"https?://", text):
            ln = text.count("\n", 0, m.start()) + 1
            f.append("404.html line %d references %r" % (ln, text[m.start():m.start() + 60]))
    except OSError as e:
        f.append("404.html unreadable: %s" % e)
    except Exception as e:  # HTMLParser errors
        f.append("404.html does not parse: %s" % e)
    report("1b 404.html", f)

    # .vercelignore
    f = []
    try:
        lines = {ln.strip() for ln in read(".vercelignore").splitlines()
                 if ln.strip() and not ln.strip().startswith("#")}
        for need in ("scripts/", ".claude/", ".specify/", "CLAUDE.md", "AGENTS.md",
                     "_downloads.html"):
            if need not in lines:
                f.append(".vercelignore missing %r" % need)
        for deployable in ("robots.txt", "sitemap.xml", "404.html", "index.html",
                           "ru/", "uk/", "wp-content/", "/robots.txt", "/sitemap.xml",
                           "/404.html", "*.html", "*.xml", "*.txt"):
            if deployable in lines:
                f.append(".vercelignore excludes deployable %r" % deployable)
    except OSError as e:
        f.append(".vercelignore unreadable: %s" % e)
    report("1c .vercelignore", f)


# ---------------------------------------------------------------- check 2
def check_vercel(pages):
    f = []
    redirects = {}
    try:
        cfg = json.loads(read("vercel.json"))
    except (OSError, ValueError) as e:
        report("2  vercel.json", ["vercel.json does not parse: %s" % e])
        return redirects
    if cfg.get("cleanUrls") is not True:
        f.append("cleanUrls is %r, expected true" % cfg.get("cleanUrls"))
    if cfg.get("trailingSlash") is not False:
        f.append("trailingSlash is %r, expected false" % cfg.get("trailingSlash"))
    reds = cfg.get("redirects")
    if not isinstance(reds, list):
        f.append("redirects is not a list")
        reds = []
    src_re = re.compile(r"^/[a-z0-9-]+$")
    page_set = set(pages)
    for i, r in enumerate(reds):
        if not isinstance(r, dict) or "source" not in r or "destination" not in r:
            f.append("redirect #%d lacks source/destination: %r" % (i, r))
            continue
        s, d = r["source"], r["destination"]
        if r.get("permanent") is not True:
            f.append("%s: permanent is %r" % (s, r.get("permanent")))
        if s in redirects:
            f.append("duplicate source %s" % s)
        redirects[s] = d
        if not (src_re.match(s) or s in ("/uk", "/ru")):
            f.append("source %r does not match ^/[a-z0-9-]+$" % s)
        extra = set(r) - {"source", "destination", "permanent"}
        if extra:
            f.append("%s: unexpected keys %s" % (s, sorted(extra)))
    for s, d in redirects.items():
        rel = path_to_rel(d) if isinstance(d, str) else None
        if not page_exists(rel):
            f.append("%s -> %s: destination is not an existing page" % (s, d))
        if d in redirects:
            f.append("%s -> %s: chain, destination is itself a source (-> %s)"
                     % (s, d, redirects[d]))
        slug = s[1:]
        if s not in ("/uk", "/ru"):
            taken = (slug in page_set or os.path.exists(os.path.join(ROOT, slug))
                     or os.path.isfile(os.path.join(ROOT, slug + ".html")))
            if taken and slug not in DUPLICATES:
                f.append("source %s shadows an existing root path" % s)
    for slug, dest in DUPLICATES.items():
        got = redirects.get("/" + slug)
        if got != dest:
            f.append("duplicate /%s redirects to %r, expected %r" % (slug, got, dest))
    if redirects.get("/narkotik-mefedron") != "/ru/narkotik-mefedron":
        f.append("/narkotik-mefedron redirects to %r, expected /ru/narkotik-mefedron"
                 % redirects.get("/narkotik-mefedron"))
    if len(reds) >= 1024:
        f.append("%d redirects, Vercel limit is 1024" % len(reds))
    report("2  vercel.json", f, "%d redirects" % len(reds))
    return redirects


# ---------------------------------------------------------------- check 3
def check_sitemap(pages, redirects):
    f = []
    locs = []
    try:
        tree = ET.parse(os.path.join(ROOT, "sitemap.xml"))
    except (OSError, ET.ParseError) as e:
        report("3  sitemap.xml", ["sitemap.xml does not parse: %s" % e])
        return locs
    root = tree.getroot()
    if root.tag != SM_NS + "urlset":
        f.append("root element is %r, expected %surlset" % (root.tag, SM_NS))
    date_re = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    seen = set()
    for url in root:
        if url.tag != SM_NS + "url":
            f.append("unexpected element %r" % url.tag)
            continue
        loc_el = url.find(SM_NS + "loc")
        if loc_el is None or not (loc_el.text or "").strip():
            f.append("<url> without <loc>")
            continue
        loc = loc_el.text.strip()
        locs.append(loc)
        if loc in seen:
            f.append("duplicate loc %s" % loc)
        seen.add(loc)
        if not loc.startswith(BASE + "/"):
            f.append("loc not under %s/: %s" % (BASE, loc))
            continue
        if loc != BASE + "/" and loc.endswith("/"):
            f.append("trailing slash: %s" % loc)
        rel = url_to_rel(loc)
        if not page_exists(rel):
            f.append("no index.html for %s" % loc)
        path = "/" if rel == "" else "/" + (rel or "")
        if rel is not None and path in redirects:
            f.append("loc is a redirect source (%s -> %s): %s" % (path, redirects[path], loc))
        lm = url.find(SM_NS + "lastmod")
        if lm is not None:
            txt = (lm.text or "").strip()
            ok = bool(date_re.match(txt))
            if ok:
                try:
                    datetime.date.fromisoformat(txt)
                except ValueError:
                    ok = False
            if not ok:
                f.append("bad lastmod %r for %s" % (txt, loc))
    expected = [p for p in pages if p not in DUPLICATES]
    loc_set = set(locs)
    for p in expected:
        n = locs.count(page_url(p)) if page_url(p) in loc_set else 0
        if n != 1:
            f.append("page /%s appears %d times in sitemap" % (p, n))
    for d in DUPLICATES:
        if page_url(d) in loc_set:
            f.append("redirected duplicate in sitemap: %s" % page_url(d))
    if len(expected) != EXPECTED_SITEMAP:
        f.append("expected %d sitemap-eligible pages on disk, found %d"
                 % (EXPECTED_SITEMAP, len(expected)))
    report("3  sitemap.xml", f, "%d locs, %d expected" % (len(locs), len(expected)))
    return locs


# ---------------------------------------------------------------- check 4
def check_pages(pages, redirects):
    f = []
    warn_recip = []
    warn_redirect_target = []
    warn_home = []
    canon_of = {}
    lang_of = {}
    parsed = {}
    for rel in pages:
        try:
            parsed[rel] = parse_html(read(os.path.join(rel, "index.html") if rel else "index.html"))
        except Exception as e:
            f.append("/%s: does not parse: %s" % (rel, e))
            continue
        lang_of[rel] = primary(parsed[rel].html_lang)
    if len(pages) != EXPECTED_PAGES:
        f.append("expected %d index.html pages, found %d" % (EXPECTED_PAGES, len(pages)))
    hreflang_map = {}
    for rel, p in parsed.items():
        name = "/" + rel
        lang = lang_of[rel]
        if lang not in ("ru", "uk"):
            f.append("%s: <html lang> is %r" % (name, p.html_lang))
        expected_canon = (BASE + DUPLICATES[rel]) if rel in DUPLICATES else page_url(rel)
        links = [(a, raw) for t, a, raw in p.tags if t == "link"]
        canons = [(a, raw) for a, raw in links
                  if "canonical" in a.get("rel", "").lower().split()]
        alts = [(a, raw) for a, raw in links if "hreflang" in a]
        for a, raw in canons + alts:
            if re.search(r'href\s*=\s*["\']?(index\.html|\.\./)', raw, re.I):
                f.append("%s: relative href left in %s" % (name, raw.strip()))
        if len(canons) != 1:
            f.append("%s: %d canonical tags" % (name, len(canons)))
        canon = canons[0][0].get("href", "") if canons else None
        if canon is not None:
            if canon != expected_canon:
                f.append("%s: canonical %r, expected %r" % (name, canon, expected_canon))
            canon_of[rel] = canon
        ogs = [a.get("content", "") for t, a, _ in p.tags
               if t == "meta" and a.get("property", "").lower() == "og:url"]
        if not ogs:
            f.append("%s: no og:url" % name)
        for og in ogs:
            if og != canon:
                f.append("%s: og:url %r != canonical %r" % (name, og, canon))
        if len(ogs) > 1:
            f.append("%s: %d og:url tags" % (name, len(ogs)))
        seen_langs = {}
        own = []
        for a, raw in alts:
            hl = a.get("hreflang", "").strip()
            href = a.get("href", "")
            if "alternate" not in a.get("rel", "").lower().split():
                f.append("%s: hreflang link without rel=alternate: %s" % (name, raw.strip()))
            if hl.lower() in seen_langs:
                f.append("%s: duplicate hreflang %r" % (name, hl))
            seen_langs[hl.lower()] = href
            trel = url_to_rel(href)
            if not href.startswith(BASE + "/") or (href != BASE + "/" and href.endswith("/")):
                f.append("%s: hreflang=%s href not absolute/clean: %r" % (name, hl, href))
                continue
            if not page_exists(trel):
                f.append("%s: hreflang=%s target missing: %s" % (name, hl, href))
                continue
            tpath = "/" + trel if trel else "/"
            if tpath in redirects:
                warn_redirect_target.append("%s: hreflang=%s points at redirect source %s"
                                            % (name, hl, href))
            if hl.lower() == "x-default":
                continue
            if trel in ("", "uk/home") and rel not in ("", "uk/home"):
                warn_home.append("%s: hreflang=%s points at a home page %s" % (name, hl, href))
            tlang = lang_of.get(trel)
            if primary(hl) != tlang:
                f.append("%s: hreflang=%s but target %s has lang %r" % (name, hl, href, tlang))
            if primary(hl) == lang:
                own.append(href)
        if len(own) != 1:
            f.append("%s: %d hreflang entries for own language %r" % (name, len(own), lang))
        elif canon is not None and own[0] != canon:
            f.append("%s: own-language hreflang %r != canonical %r" % (name, own[0], canon))
        hreflang_map[rel] = {k: v for k, v in seen_langs.items() if k != "x-default"}
    # Extra (informational): reciprocity of hreflang clusters, among canonical pages.
    canon_to_rel = {}
    for rel, c in canon_of.items():
        if rel not in DUPLICATES:
            canon_to_rel[c] = rel
    for rel, m in hreflang_map.items():
        if rel in DUPLICATES:
            continue
        me = canon_of.get(rel)
        for hl, href in m.items():
            trel = canon_to_rel.get(href)
            if trel is None or trel == rel:
                continue
            back = hreflang_map.get(trel, {})
            if me not in back.values():
                warn_recip.append("/%s -> %s (hreflang=%s) has no return link"
                                  % (rel, href, hl))
    report("4  page canonical/og:url/hreflang", f,
           "%d pages, %d hreflang tags" % (len(parsed), sum(len(v) for v in hreflang_map.values())))
    report("4x (extra) hreflang reciprocity", warn_recip, warn=True)
    report("4y (extra) hreflang targets are not redirect sources", warn_redirect_target, warn=True)
    report("4z (extra) article hreflang does not point at a home page", warn_home, warn=True)
    return canon_of


# ---------------------------------------------------------------- check 5
def check_stray_html():
    """Extra: .html files other than index.html that cleanUrls would also serve."""
    w = []
    known = {"404.html", "_downloads.html"}
    for d, dirs, files in os.walk(ROOT):
        rel = os.path.relpath(d, ROOT).replace(os.sep, "/")
        rel = "" if rel == "." else rel
        if rel == "":
            dirs[:] = [x for x in dirs if x not in IGNORE_DIRS]
        for fn in files:
            if not fn.endswith(".html") or fn == "index.html":
                continue
            path = fn if rel == "" else rel + "/" + fn
            if path in known:
                continue
            twin = path[:-5]
            note = " (clashes with folder %s/index.html under cleanUrls)" % twin \
                if os.path.isfile(os.path.join(ROOT, twin, "index.html")) else ""
            w.append("/%s%s" % (path, note))
    report("4s (extra) no stray .html pages outside the index.html scheme", sorted(w), warn=True)


def check_cross(locs, canon_of):
    f = []
    for loc in locs:
        rel = url_to_rel(loc)
        if rel is None or rel not in canon_of:
            f.append("%s: no page/canonical to compare" % loc)
            continue
        if canon_of[rel] != loc:
            f.append("%s: page canonical is %s" % (loc, canon_of[rel]))
    report("5  sitemap loc == page canonical", f, "%d locs" % len(locs))


# ---------------------------------------------------------------- check 6
def check_http():
    f = []
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    proc = subprocess.Popen(
        [sys.executable, "-I", "-m", "http.server", str(port), "--bind", "127.0.0.1",
         "--directory", ROOT],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = "http://127.0.0.1:%d" % port
    try:
        deadline = time.time() + 10
        while True:
            try:
                socket.create_connection(("127.0.0.1", port), timeout=0.5).close()
                break
            except OSError:
                if time.time() > deadline or proc.poll() is not None:
                    raise RuntimeError("http.server did not start on port %d" % port)
                time.sleep(0.1)
        cases = [
            ("/robots.txt", 200, ("text/plain",)),
            ("/sitemap.xml", 200, ("application/xml", "text/xml")),
            ("/404.html", 200, ("text/html",)),
            ("/", 200, ("text/html",)),
            ("/ru/bytovoj-alkogolizm/", 200, ("text/html",)),
            ("/uk/home/", 200, ("text/html",)),
            ("/this-does-not-exist-xyz/", 404, None),
        ]
        for path, want, types in cases:
            try:
                with urllib.request.urlopen(base + path, timeout=10) as resp:
                    code, ctype = resp.status, resp.headers.get("Content-Type", "")
                    resp.read()
            except urllib.error.HTTPError as e:
                code, ctype = e.code, e.headers.get("Content-Type", "")
            except Exception as e:
                f.append("%s: request failed: %s" % (path, e))
                continue
            if code != want:
                f.append("%s: HTTP %d, expected %d" % (path, code, want))
            if types and not any(ctype.lower().startswith(t) for t in types):
                f.append("%s: Content-Type %r, expected one of %s" % (path, ctype, types))
    except Exception as e:
        f.append(str(e))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
    report("6  HTTP smoke test (python http.server)", f, "port %d" % port)
    print("      note: python's http.server does not emulate Vercel redirects or "
          "cleanUrls; redirect behaviour is covered by the file checks only.")


def main():
    os.chdir(ROOT)
    pages = collect_pages()
    check_files()
    redirects = check_vercel(pages)
    locs = check_sitemap(pages, redirects)
    canon_of = check_pages(pages, redirects)
    check_stray_html()
    check_cross(locs, canon_of)
    check_http()
    failed = [r for r in results if r[0] == "FAIL"]
    warned = [r for r in results if r[0] == "WARN"]
    print("\n%d checks: %d passed, %d failed, %d warnings"
          % (len(results), len(results) - len(failed) - len(warned), len(failed), len(warned)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
