# tonus.kiev.ua — static export of the legacy tonus.kiev.ua WordPress site (CLIENT)

> Fleet: **CLIENT** (remote: borntojesus, repo tonus-kiev-ua). The client may review this code.
> Stack is the CLIENT'S choice — do NOT impose the fleet golden path (pnpm/homelab/Payload). See /Users/dmytro/github/ARCHITECTURE-PLAN.md §2.2.

## What this is

A flat static HTML capture/export of the legacy tonus.kiev.ua site (addiction-rehab clinic,
uk/ru). Hundreds of per-article folders, each containing an `index.html`, plus `wp-content/`,
`wp-includes/`, `wp-json/` carried over from the original WordPress. The modern Astro rebuild
lives in the sibling `tonus-astro` repo.

## Stack (client-chosen — keep as-is)

- Framework/CMS: static HTML exported from WordPress (legacy)
- Package manager: none — do not introduce one
- Deploy: unknown — TODO (static hosting; `cdn-cgi/` suggests Cloudflare in front)

## Client-facing copy

Any text the client reads: no dashes as punctuation, run the `humanizer` skill before sending, no internal jargon.

## Run

```sh
# static files — serve the repo root with any static server, e.g.
python3 -m http.server 8000
```

## Notes

- This is an archived/legacy export, not a live CMS. Treat as content reference for the rebuild.
- Bilingual: `uk/` and `ru/` plus localized slug folders at root.
- Do not "modernize" in place; new work happens in `tonus-astro`.
