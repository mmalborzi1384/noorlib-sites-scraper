# Noorlib scraper — quick notes

## Files
- `noorlib_scraper.py`  — the scraper
- `noorlib_token.txt`   — your session token (expires ~2026-09-22)
- `noorlib_100_143/`    — pages 100–143 already scraped (whole rest of the book)

## Usage
```bash
python3 noorlib_scraper.py --book 34592 --from 100 --to 160 -o name
python3 noorlib_scraper.py --book 34592 --pages 100,102,105-110 -o name
python3 noorlib_scraper.py --book 34592 --toc        # show chapter start pages
```
Add `--md` for markdown output, `--delay 0.5` to go faster.

## When the token expires (401 / login errors)
1. Log in at noorlib.ir in your browser.
2. F12 → Application → Cookies → `https://noorlib.ir` → copy the value of
   `auth._token.inoor` (it already starts with "Bearer ").
3. Paste it into `noorlib_token.txt` (one line, no quotes).

Or, while logged in on the site, run in the browser console (F12):
`document.cookie.match(/auth._token.inoor=([^;]+)/)[1]`
(then decodeURIComponent it if it looks URL-encoded).

## Notes
- Every page fetched consumes your account's viewing credit, same as reading it on the site.
- p115 is a section-title page (short) and p116 has no text layer (image page in the print edition) — that's the book, not a bug.
- For a different book, just change the `--book` number (it's in the book's URL).
- Personal use only — Noorlib's terms prohibit redistribution.
