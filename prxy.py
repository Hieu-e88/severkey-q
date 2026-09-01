#!/usr/bin/env python3
import os
import urllib.request
import urllib.parse
import urllib.error
import http.cookiejar
import re
import sys
import time
from urllib.parse import urlparse, parse_qs

KEY_URL = "https://solitudepremium.click/kzmod/key.php"
UA = "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
HDRS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
    "Accept-Encoding": "identity",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Connection": "keep-alive",
}

OUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "key.txt")
MAX_RETRY = 3


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def build_opener():
    cj = http.cookiejar.CookieJar()
    return urllib.request.build_opener(
        NoRedirect, urllib.request.HTTPCookieProcessor(cj)
    ), cj


def no_redirect_get(op, url, headers=None):
    h = dict(HDRS)
    h.update(headers or {})
    req = urllib.request.Request(url, headers=h)
    try:
        resp = op.open(req, timeout=30)
        return resp.status, dict(resp.headers.items()), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers.items()), e.read()


def decode_multi(value):
    prev = None
    while prev != value:
        prev = value
        value = urllib.parse.unquote(value)
    return value


def get_key(op):
    code, hdrs, body = no_redirect_get(op, KEY_URL)
    if code not in (301, 302, 303, 307, 308):
        raise RuntimeError("key.php khong redirect (status %s)" % code)
    loc = hdrs.get("Location") or hdrs.get("location")
    if not loc:
        raise RuntimeError("key.php khong co Location header")

    q = parse_qs(urlparse(loc).query)
    raw = q.get("url", [""])[0]
    if not raw:
        raise RuntimeError("khong co tham so url trong redirect")
    target = decode_multi(raw)

    req = urllib.request.Request(target, headers=HDRS)
    resp = urllib.request.urlopen(req, timeout=30)
    html = resp.read().decode("utf-8", "replace")

    m = re.search(r'id="keyDisplay"[^>]*value="([^"]+)"', html)
    if not m:
        raise RuntimeError("khong tim thay key trong trang ket qua")
    key = m.group(1).strip()
    if not key or key == "HẾT HẠN" or "het han" in key.lower():
        raise RuntimeError("key khong hop le: %r" % key)

    total = re.search(r'id="totalGenerated">(\d+)', html)
    remain = re.search(r'id="remainingDisplay">(\d+)', html)
    info = None
    if total and remain:
        info = (total.group(1), remain.group(1))
    return key, info


def main():
    if len(sys.argv) > 1:
        try:
            count = int(sys.argv[1])
        except ValueError:
            count = None
    else:
        count = None

    if not count:
        try:
            count = int(input("Nhap so luong key can tao: ").strip())
        except (ValueError, EOFError):
            print("So luong khong hop le.")
            return
    if count < 1:
        print("So luong phai >= 1.")
        return

    print("Dang tao %d key..." % count)
    keys = []
    with open(OUT_FILE, "a", encoding="utf-8") as f:
        for i in range(1, count + 1):
            key = None
            info = None
            for attempt in range(1, MAX_RETRY + 1):
                try:
                    op, _ = build_opener()
                    key, info = get_key(op)
                    break
                except Exception as e:
                    msg = str(e)
                    print("  [%d/%d] loi (lan %d): %s" % (i, count, attempt, msg))
                    time.sleep(1.5)
            if not key:
                print("  [%d/%d] THAT BAI sau %d lan thu." % (i, count, MAX_RETRY))
                continue
            keys.append(key)
            f.write(key + "\n")
            f.flush()
            extra = ""
            if info:
                extra = "  (da tao %s/%s)" % (info[0], info[1])
            print("  [%d/%d] KEY: %s%s" % (i, count, key, extra))
            time.sleep(0.8)

    print("")
    if keys:
        print("Hoan thanh! %d key da luu vao %s" % (len(keys), OUT_FILE))
        for k in keys:
            print("  " + k)
    else:
        print("Khong tao duoc key nao.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nDa huy.")
        sys.exit(130)