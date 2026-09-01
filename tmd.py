#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Tool.py - Get Key LQM iOS

import os
import re
import sys
import urllib.request
import urllib.parse

PYY = '/storage/emulated/0/pyy'
DIR = os.path.join(PYY, 'authtool')
LINKVUOT_FILE = os.path.join(DIR, 'linkvuot.txt')
KEY_FILE = os.path.join(DIR, 'key.txt')
GETKEY_PAGE = 'https://unlock.tumadam.com/getkeylqm.html'

UA = ('Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36')


def fetch(url, referer=None):
    headers = {
        'User-Agent': UA,
        'Accept-Language': 'vi-VN,vi;q=0.9',
    }
    if referer:
        headers['Referer'] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.geturl(), r.read().decode('utf-8', 'ignore')


def extract_key(text):
    """Trich key dang tumadam-day-... tu bat ky text/url nao."""
    decoded = urllib.parse.unquote(text)
    m = re.search(r'result=([A-Za-z0-9_.\-]+)', decoded)
    if m and m.group(1).startswith('tumadam'):
        return m.group(1)
    m = re.search(r'result=(tumadam[-\w.]+)', decoded)
    if m:
        return m.group(1)
    m = re.search(r'(tumadam(?:-\w+)+-\w+)', decoded)
    if m:
        return m.group(1)
    return None


def get_unlock_links():
    """Lay tat ca link unlock tu trang getkeygame (main/backup/ads)."""
    _, html = fetch(GETKEY_PAGE)
    links = re.findall(r"https://authtool\.app/get-key\?code=[^'\"\s]+", html)
    seen, out = set(), []
    for l in links:
        if l not in seen:
            seen.add(l)
            out.append(l)
    return out


def vuot_link(count=None):
    print('[*] Lay link unlock tu', GETKEY_PAGE)
    base_links = get_unlock_links()
    if not base_links:
        print('[X] Khong tim thay link nao tren trang getkeygame.')
        return
    print('[+] Tim thay', len(base_links), 'link goc tren trang.')

    # 1. Đọc danh sách link đã lưu trước đó để chống trùng
    existing_links = set()
    if os.path.exists(LINKVUOT_FILE):
        with open(LINKVUOT_FILE, 'r', encoding='utf-8') as f:
            existing_links = {line.strip() for line in f if line.strip()}

    if count is None:
        try:
            count = int(input('[?] Nhap so link muon tao: ').strip())
        except (ValueError, EOFError):
            print('[!] Khong hop le.')
            return
    if count < 1:
        print('[!] So link phai >= 1.')
        return

    new_links = []
    idx = 1
    # 2. Sinh link mới bằng cách xoay vòng link gốc và biến đổi query/hash nếu cần
    while len(new_links) < count:
        base = base_links[(idx - 1) % len(base_links)]
        
        # Tạo định danh duy nhất cho từng lượt để không bị lặp link
        if idx <= len(base_links):
            candidate = base
        else:
            # Nếu vượt quá số link gốc, nối thêm tham số phụ
            separator = '&' if '?' in base else '?'
            candidate = f"{base}{separator}idx={idx}"

        if candidate not in existing_links and candidate not in new_links:
            new_links.append(candidate)
        
        idx += 1
        # Tránh vòng lặp vô tận nếu có giới hạn
        if idx > count * 10 + 100:
            break

    if not new_links:
        print('[!] Khong tao them duoc link moi nao (tat ca da co trong file).')
        return

    # 3. Ghi bổ sung vào file linkvuot.txt
    os.makedirs(DIR, exist_ok=True)
    with open(LINKVUOT_FILE, 'a', encoding='utf-8') as f:
        for l in new_links:
            f.write(l + '\n')

    total_count = len(existing_links) + len(new_links)
    print(f'[+] Da tao va luu {len(new_links)} link moi (khong trung) vao {LINKVUOT_FILE}')
    print(f'[+] Tong so link hien co trong file: {total_count}')


def tach_key_tu_link_unlock(link):
    key = extract_key(link)
    if key:
        return key, 'key trong link'

    if 'unlock.tumadam.com' in link:
        print('   [*] Mo trang unlock...')
        try:
            final_url, html = fetch(link)
        except Exception as e:
            return None, 'khong mo duoc trang unlock: ' + str(e)[:120]
        
        body_only = re.sub(r'<script.*?</script>', '', html, flags=re.S)
        if 'het han' in body_only.lower() or 'hết hạn' in body_only:
            return None, 'link da het han'
        m = re.search(r'DEST\s*=\s*"([^"]+)"', html)
        if not m:
            return None, 'khong tim thay DEST /api/go trong trang'
        dest = m.group(1)
        if dest.startswith('/'):
            dest = 'https://unlock.tumadam.com' + dest
        print('   [*] Truy cap', dest)
        try:
            final_url, _ = fetch(dest, referer=link)
        except Exception as e:
            return None, 'loi khi goi /api/go: ' + str(e)[:120]
        key = extract_key(final_url)
        if key:
            return key, 'key tu API'
        key = extract_key(dest)
        if key:
            return key, 'key tu DEST'
        return None, 'khong thay key trong URL ket qua: ' + final_url[:160]

    return None, 'khong phai link unlock.tumadam.com va khong co key trong link'


def tach_key(links):
    if isinstance(links, str):
        links = [links]
    os.makedirs(DIR, exist_ok=True)
    existing = []
    if os.path.exists(KEY_FILE):
        existing = [l.strip() for l in open(KEY_FILE, encoding='utf-8') if l.strip()]

    saved, dup, fail = 0, 0, 0
    for link in links:
        link = link.strip()
        if not link:
            continue
        print('[*] Xu ly:', link[:110])
        key, note = tach_key_tu_link_unlock(link)
        if not key:
            print('[!] THAT BAI (' + note + ')')
            fail += 1
            continue
        if key in existing:
            print('[=] Trung key (bo qua):', key)
            dup += 1
            continue
        existing.append(key)
        print('[+] KEY (' + note + '):', key)
        saved += 1

    if saved > 0:
        with open(KEY_FILE, 'w', encoding='utf-8') as f:
            f.write('\n'.join(existing) + '\n')
        print('[+] Da luu', saved, 'key moi vao', KEY_FILE, '(tong', len(existing), ')')
    else:
        print('[!] Khong co key moi. Tong trong file:', len(existing))


def input_links():
    print('[?] Dan link unlock vao day (moi link 1 dong, nhan Enter 2 lan de xong):')
    lines = []
    prev_empty = False
    try:
        while True:
            line = input('')
            if line.strip() == '':
                if prev_empty:
                    break
                prev_empty = True
            else:
                prev_empty = False
                lines.append(line)
    except (EOFError, KeyboardInterrupt):
        pass
    return lines


def menu():
    print('=========================')
    print('  GET KEY LQM iOS')
    print('=========================')
    print('  1. Vuot link  -> linkvuot.txt')
    print('  2. Tach key   -> key.txt')
    print('  0. Thoat')
    print('=========================')
    try:
        choice = input('Chon (0-2): ').strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return 0
    if choice == '1':
        vuot_link()
        return 1
    if choice == '2':
        links = input_links()
        if links:
            tach_key(links)
        else:
            print('[!] Khong co link nao.')
        return 1
    if choice == '0':
        return 0
    print('[!] Lua chon khong hop le.')
    return 1


def main():
    args = sys.argv[1:]
    if args and args[0] in ('vuotlink', 'vuot'):
        n = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
        vuot_link(n)
        return
    if args and args[0] in ('tachkey', 'tach'):
        if len(args) > 1:
            tach_key(args[1:])
        else:
            tach_key(input_links())
        return
    while menu() != 0:
        pass


if __name__ == '__main__':
    main()
