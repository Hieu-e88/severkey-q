#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# vnping.py - Get Key VN PING 24H
# Luong: getkey.php -> link ontops -> vuot (mo trinh duyet, ban lam tay) -> step2 -> vuot -> KEY
import os
import re
import sys
import time
import subprocess
import urllib.request
import urllib.parse
from urllib.parse import urlparse, parse_qs

DIR = '/storage/emulated/0/pyy'
KEY_FILE = os.path.join(DIR, 'key.txt')
GETKEY_PAGE = 'https://nxlmods.id.vn/vnping/getkey.php'

UA = ('Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36')


def fetch(url, referer=None, follow=True):
    h = {'User-Agent': UA, 'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8',
         'Accept-Language': 'vi-VN,vi;q=0.9,en;q=0.8'}
    if referer:
        h['Referer'] = referer
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, r.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')
    except Exception as e:
        return 0, str(e)


def decode_multi(value):
    prev = None
    while prev != value:
        prev = value
        value = urllib.parse.unquote(value)
    return value


def extract_ontops_link(html):
    m = re.search(r'https://ontops\.link/st\?apikey=[^"\'\s<>]+', html)
    if m:
        return m.group(0).replace('&amp;', '&')
    m = re.search(r'https://ontops\.link/st[^"\'\s<>]+', html)
    if m:
        return m.group(0).replace('&amp;', '&')
    return None


def target_from_ontops(link):
    q = parse_qs(urlparse(link).query)
    raw = q.get('url', [''])[0]
    if not raw:
        raise ValueError('Khong co tham so url trong link ontops')
    target = decode_multi(raw)
    if not target.lower().startswith('http'):
        target = 'https://' + target
    return target


def step_of(link):
    try:
        t = target_from_ontops(link)
        q = parse_qs(urlparse(t).query)
        return int(q.get('step', ['0'])[0])
    except Exception:
        return 0


def extract_key(html):
    m = re.search(r'id="finalKey"[^>]*>([^<]+)<', html)
    if m and m.group(1).strip():
        return m.group(1).strip()
    m = re.search(r'value="(kezmod[^"]+)"', html)
    if m:
        return m.group(1).strip()
    return None


def open_browser(url):
    try:
        subprocess.run(['am', 'start', '-a', 'android.intent.action.VIEW', '-d', url],
                       capture_output=True, timeout=10)
        return True
    except Exception:
        return False


def vuot_manual(link, target, step):
    """Mo trinh duyet, huong dan nguoi dung hoan tat vuot, roi doc lai ket qua."""
    print('  ================================================')
    print('  BUOC VUOT %d (ontops): ' % step)
    print('  Trinh duyet dang mo. Hay hoan tat tren trinh duyet:')
    print('   1. Cho trang quang cao chay (3 giay)')
    print('   2. Vao website trong hinh anh, tim nut "lay ma" (Telegram)')
    print('   3. Lay ma roi quay lai trang, nhap ma vao o "Nhap ma xac nhan"')
    print('   4. Bam nut xac nhan -> tu dong chuyen ve trang getkey')
    print('  Link: ' + link)
    print('  ================================================')
    open_browser(link)
    input('  Nhan Enter sau khi vuot xong tren trinh duyet...')

    # doc lai target xem da tien step chua
    code, html = fetch(target, referer=link.split('&url=')[0])
    key = extract_key(html)
    if key:
        return key, None
    next_link = extract_ontops_link(html)
    if next_link and step_of(next_link) > step:
        return None, next_link
    return None, None


def get_key_once():
    print('[*] Truy cap getkey.php...')
    code, html = fetch(GETKEY_PAGE)
    if code != 200:
        print('[X] Loi truy cap getkey.php:', code)
        return None

    key = extract_key(html)
    if key:
        return key
    link = extract_ontops_link(html)
    if not link:
        print('[X] Khong tim thay link ontops.')
        return None

    current_step = step_of(link)
    print('[+] Bat dau o step %d' % current_step)

    for _ in range(1, 8):
        target = target_from_ontops(link)
        print('  [*] Link ontops:', link[:90] + '...')
        print('  [*] Target:', target)

        # Thu truc tiep (truong hop da vuot truoc do)
        code, html = fetch(target, referer=link.split('&url=')[0])
        key = extract_key(html)
        if key:
            return key
        next_link = extract_ontops_link(html)
        if next_link and step_of(next_link) > current_step:
            link = next_link
            current_step = step_of(link)
            print('  [+] Tien len step', current_step)
            continue

        # Chua vuot -> vuot bang trinh duyet
        key, next_link = vuot_manual(link, target, current_step)
        if key:
            return key
        if next_link:
            link = next_link
            current_step = step_of(link)
            print('  [+] Sau khi vuot, tien len step', current_step)
            continue

        # Van chua -> lay link moi tu dau
        print('  [!] Chua co ket qua, thoi.')
        return None

    return None


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'auto':
        n = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 1
    else:
        try:
            n = int(input('Nhap so luong key can tao: ').strip())
        except (ValueError, EOFError):
            print('So luong khong hop le.')
            return

    os.makedirs(DIR, exist_ok=True)
    keys = []
    for i in range(1, n + 1):
        print('\n=== Lan %d/%d ===' % (i, n))
        key = get_key_once()
        if key:
            keys.append(key)
            with open(KEY_FILE, 'a', encoding='utf-8') as f:
                f.write(key + '\n')
            print('[+] KEY [%d]: %s' % (i, key))
        else:
            print('[!] Lan %d that bai.' % i)
        time.sleep(1)

    print('\n=== KET QUA ===')
    if keys:
        print('Da luu', len(keys), 'key vao', KEY_FILE)
        for k in keys:
            print('  ' + k)
    else:
        print('Khong lay duoc key nao.')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nDa dung.')