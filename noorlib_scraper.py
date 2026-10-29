#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
noorlib_scraper.py — download pages of a book from noorlib.ir as clean text.

Requires a logged-in session (Bearer token) because pages are credit-gated.
Usage:
  python3 noorlib_scraper.py --book 34592 --from 100 --to 160 -o out
  python3 noorlib_scraper.py --book 34592 --pages 100,102,105-110 -o out
  python3 noorlib_scraper.py --book 34592 --toc          # show table of contents
Token:
  put the "Bearer ey..." string in noorlib_token.txt (same folder),
  or set the NOORLIB_TOKEN environment variable.
"""

import argparse, base64, json, os, re, sys, time
import urllib.request, urllib.error

API = 'https://noorlib.ir/api'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0',
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    'Referer': 'https://noorlib.ir/',
}

# ---------------------------------------------------------------- decoding
def decode_page(b64: str, page: int) -> str:
    """noorlib obfuscation: base64url -> utf-8 -> shift each char code by
    -(pageNumber) -> swap adjacent code points."""
    s = b64.replace('-', '+').replace('_', '/')
    s += '=' * (-len(s) % 4)
    raw = base64.b64decode(s).decode('utf-8')
    shifted = ''.join(chr(ord(c) - page) for c in raw)
    ch = list(shifted)
    for i in range(0, len(ch) - 1, 2):
        ch[i], ch[i + 1] = ch[i + 1], ch[i]
    return ''.join(ch)


def html_to_text(html: str) -> str:
    """Paragraph text from the decoded page HTML (p[paragraph-id] blocks)."""
    paras = re.findall(r'<p[^>]*paragraph-id[^>]*>(.*?)</p>', html, re.S)
    out = []
    for p in paras:
        t = re.sub(r'<span[^>]*bookPage[^>]*>\s*\d+\s*</span>', '', p)
        t = re.sub(r'<[^>]+>', '', t)
        t = re.sub(r'\s+', ' ', t).strip()
        if t:
            out.append(t)
    return '\n\n'.join(out)


# ---------------------------------------------------------------- API
def api_post(token, path, payload, retries=3):
    req = urllib.request.Request(
        API + path, data=json.dumps(payload).encode(),
        headers={**HEADERS, 'Authorization': token, 'Origin': 'https://noorlib.ir'},
        method='POST')
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < retries - 1:
                wait = 5 * (attempt + 1)
                print(f'  [warn] HTTP {e.code}, retry in {wait}s', file=sys.stderr)
                time.sleep(wait)
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if attempt < retries - 1:
                time.sleep(3 * (attempt + 1))
                continue
            raise
    return None


def api_get(token, path_with_query):
    req = urllib.request.Request(
        API + path_with_query, headers={**HEADERS, 'Authorization': token})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def fetch_page(token, book_id, page, volume=1, section=1):
    """Returns (ok, decoded_html, info)."""
    payload = {
        'origin': 'noorlib.web.app', 'language': 'fa',
        'bookId': book_id, 'bookView': False,
        'volumeNumber': volume, 'sectionNumber': section,
        'viewType': 'html', 'isReferralFromGoogleSearch': False,
        'pageNumber': page,
    }
    j = api_post(token, '/book/getBookPageContent', payload)
    d = (j.get('data') or [{}])[0]
    val = d.get('validation', {})
    if val.get('code') == 1 and d.get('html'):
        return True, decode_page(d['html'], page), d
    return False, '', {'validation': val, 'pageNumber': d.get('pageNumber'),
                       'response': j}


def toc(token, book_id):
    q = ('/book/getBookTOC?origin=noorlib.web.app&language=fa'
         f'&bookId={book_id}&offset=0&limit=100&parentNodeId=')
    j = api_get(token, q)
    return j.get('data', [])


# ---------------------------------------------------------------- output
def save_page(out_dir, page, text, fmt='txt'):
    os.makedirs(out_dir, exist_ok=True)
    ext = 'md' if fmt == 'md' else 'txt'
    path = os.path.join(out_dir, f'p{page:04d}.{ext}')
    with open(path, 'w', encoding='utf-8') as f:
        if fmt == 'md':
            f.write(f'## صفحه {page}\n\n{text}\n')
        else:
            f.write(text + '\n')
    return path


def parse_pages(spec: str):
    """'100,102,105-110' -> [100,102,105,...,110]"""
    pages = []
    for part in spec.split(','):
        part = part.strip()
        if '-' in part:
            a, b = part.split('-')
            pages.extend(range(int(a), int(b) + 1))
        else:
            pages.append(int(part))
    return sorted(set(pages))


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description='noorlib.ir page scraper')
    ap.add_argument('--book', type=int, required=True)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument('--from', dest='p_from', type=int)
    src.add_argument('--pages', type=str, help='e.g. "100,102,105-110"')
    src.add_argument('--toc', action='store_true')
    ap.add_argument('--to', dest='p_to', type=int)
    ap.add_argument('-o', '--out', default='noorlib_out')
    ap.add_argument('--token-file', default='noorlib_token.txt')
    ap.add_argument('--md', action='store_true', help='save .md instead of .txt')
    ap.add_argument('--delay', type=float, default=1.0)
    args = ap.parse_args()

    token = None
    if os.environ.get('NOORLIB_TOKEN'):
        token = os.environ['NOORLIB_TOKEN'].strip()
    elif os.path.exists(args.token_file):
        with open(args.token_file) as f:
            token = f.read().strip()
    if not token:
        print('ERROR: no token found (noorlib_token.txt or NOORLIB_TOKEN).',
              file=sys.stderr)
        sys.exit(2)

    if args.toc:
        for it in toc(token, args.book):
            print(f"p{it['pageNumber']:>4}  {it['nodeTitle']}")
        return

    if args.pages:
        page_list = parse_pages(args.pages)
    else:
        if not args.p_to:
            print('ERROR: --from needs --to', file=sys.stderr)
            sys.exit(2)
        page_list = list(range(args.p_from, args.p_to + 1))

    fmt = 'md' if args.md else 'txt'
    ok_n = fail_n = 0
    for i, page in enumerate(page_list):
        ok, html, info = fetch_page(token, args.book, page)
        if ok:
            text = html_to_text(html)
            save_page(args.out, page, text, fmt)
            ok_n += 1
            print(f'  [ok] p{page} ({len(text)} chars)')
        else:
            fail_n += 1
            v = info.get('validation', {})
            print(f'  [FAIL] p{page}  code={v.get("code")} {v.get("message", "")}')
            os.makedirs(os.path.join(args.out, '_failed'), exist_ok=True)
            with open(os.path.join(args.out, '_failed', f'p{page:04d}.json'), 'w') as f:
                json.dump(info, f, ensure_ascii=False, indent=2)
        if i < len(page_list) - 1:
            time.sleep(args.delay)
    print(f'\ndone: {ok_n} ok, {fail_n} failed -> {args.out}/')


if __name__ == '__main__':
    main()
