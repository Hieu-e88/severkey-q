#!/usr/bin/env python3
import os
import re
import time
import json
import urllib.request
import urllib.parse
import webbrowser
from pathlib import Path

KEY_URL = "https://raw.githubusercontent.com/Hieu-e88/severkey-q/refs/heads/main/Key_tc.txt"
KEY_FILE = Path.home() / ".severkey_saved"
IOS_KEY_FILE = Path.home() / "key_ios.txt"
ADR_KEY_FILE = Path.home() / "key_adr.txt"
DOWNLOAD_DIR = Path.home() / "download"

def fetch_keys():
    try:
        req = urllib.request.Request(KEY_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"[!] Không thể kết nối server key: {e}")
        return None

def parse_keys(raw):
    keys = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or "|" not in line:
            continue
        parts = line.split("|")
        key = parts[0].strip()
        days = parts[1].strip() if len(parts) > 1 else "?"
        msg = parts[2].strip() if len(parts) > 2 else ""
        keys[key] = {"days": days, "msg": msg}
    return keys

def verify_key(input_key):
    raw = fetch_keys()
    if raw is None:
        return False, "Không thể kết nối server key", None
    keys = parse_keys(raw)
    if input_key in keys:
        info = keys[input_key]
        return True, info["msg"], info["days"]
    return False, "Key sai hoặc không tồn tại", None

def save_key(key):
    KEY_FILE.write_text(key)

def load_saved_key():
    if KEY_FILE.exists():
        return KEY_FILE.read_text().strip()
    return None

def clear_saved_key():
    if KEY_FILE.exists():
        KEY_FILE.unlink()

def open_browser(url):
    try:
        webbrowser.open(url)
    except Exception:
        os.system(f'open "{url}" 2>/dev/null || xdg-open "{url}" 2>/dev/null')

def get_page(url, headers=None, follow_redirects=True):
    h = {"User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    if not follow_redirects:
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        opener = urllib.request.build_opener(NoRedirect)
        try:
            resp = opener.open(req, timeout=20)
            return resp.read().decode("utf-8", errors="ignore"), resp.geturl(), dict(resp.headers)
        except urllib.error.HTTPError as e:
            return e.read().decode("utf-8", errors="ignore"), e.url, dict(e.headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="ignore"), resp.geturl(), dict(resp.headers)

def extract_authtool_links(html):
    pattern = r'https?://authtool\.app/get-key\?code=[a-f0-9\-]+'
    links = list(set(re.findall(pattern, html)))
    if not links:
        pattern2 = r'https?://authtool\.app/get-key/[^\s"\'<>]+'
        links = list(set(re.findall(pattern2, html)))
    return links

def extract_ontops_url(html):
    pattern = r'https?://ontops\.link/st\?apikey=[^\s"\'<>]+'
    matches = re.findall(pattern, html)
    if not matches:
        pattern2 = r'https?://ontops\.link/[^\s"\'<>]+'
        matches = re.findall(pattern2, html)
    if matches:
        url = matches[0]
        url = url.replace("%%", "//").replace("%2F", "/").replace("%3F", "?").replace("%3D", "=").replace("%26", "&")
        return url
    return None

def extract_result_param(url):
    match = re.search(r'result=([^&]+)', url)
    if match:
        return match.group(1)
    return None

def extract_reward_url(html):
    pattern = r'https?://goctool\.vn/GETKEY/tumadam/reward/[A-Za-z0-9]+'
    matches = re.findall(pattern, html)
    if not matches:
        pattern2 = r'https?://goctool\.vn/GETKEY/tumadam/reward/[^\s"\'<>]+'
        matches = re.findall(pattern2, html)
    if matches:
        return matches[0]
    return None

def extract_api_go_url(html):
    pattern = r'/api/go/[a-f0-9]+\.html'
    matches = re.findall(pattern, html)
    if matches:
        return "https://unlock.tumadam.com" + matches[0]
    return None

def get_redirect_url(url):
    try:
        _, final_url, headers = get_page(url, follow_redirects=False)
        if "Location" in headers:
            return headers["Location"]
        return final_url
    except Exception:
        return None

def extract_hash_from_unlock_url(url):
    match = re.search(r'/([a-z0-9]+)\.html', url)
    if match:
        return match.group(1)
    return None

def menu_getkey_ios():
    print("\n=== LẤY KEY iOS ===")
    user_link = input("Nhập link unlock.tumadam.com: ").strip()
    if "unlock.tumadam.com" not in user_link:
        print("[!] Link không hợp lệ!")
        return
    print("[*] Đang xử lý...")
    hash_val = extract_hash_from_unlock_url(user_link)
    if not hash_val:
        print("[!] Không thể trích xuất hash từ link")
        return
    api_url = f"https://unlock.tumadam.com/api/go/{hash_val}.html"
    print(f"[*] API URL: {api_url}")
    _, _, api_headers = get_page(api_url, follow_redirects=False)
    api_redirect = api_headers.get("Location", "")
    if not api_redirect:
        print("[!] Không thể lấy API redirect")
        return
    print(f"[*] API Redirect: {api_redirect}")
    if "ontops.link" not in api_redirect:
        print("[!] Không phải ontops.link")
        return
    decoded_url = urllib.parse.unquote(api_redirect)
    result = extract_result_param(decoded_url)
    if result:
        print(f"\n[+] KEY: {result}")
        DOWNLOAD_DIR.mkdir(exist_ok=True)
        out_file = DOWNLOAD_DIR / "key_ios.txt"
        with open(out_file, "a") as f:
            f.write(result + "\n")
        print(f"[+] Đã lưu vào {out_file}")
    else:
        print("[!] Không tìm thấy result param")

def menu_getkey_adr():
    print("\n=== LẤY KEY ADR ===")
    url = "https://goctool.vn/GETKEY/tumadam/com.garena.game.kgvn"
    html, final_url, headers = get_page(url, follow_redirects=False)
    if not html and not headers:
        print("[!] Không thể tải trang")
        return
    redirect_url = headers.get("Location", "")
    if not redirect_url:
        redirect_url = final_url
    if redirect_url:
        print(f"[*] Redirect: {redirect_url}")
        hash_val = extract_hash_from_unlock_url(redirect_url)
        if hash_val:
            api_url = f"https://unlock.tumadam.com/api/go/{hash_val}.html"
            print(f"[*] API URL: {api_url}")
            _, _, api_headers = get_page(api_url, follow_redirects=False)
            api_redirect = api_headers.get("Location", "")
            if api_redirect:
                print(f"[*] API Redirect: {api_redirect}")
                if "ontops.link" in api_redirect:
                    decoded_url = urllib.parse.unquote(api_redirect)
                    reward_url = extract_reward_url(decoded_url)
                    if reward_url:
                        print(f"\n[+] KEY: {reward_url}")
                        DOWNLOAD_DIR.mkdir(exist_ok=True)
                        out_file = DOWNLOAD_DIR / "key_adr.txt"
                        with open(out_file, "a") as f:
                            f.write(reward_url + "\n")
                        print(f"[+] Đã lưu vào {out_file}")
                    else:
                        print("[!] Không tìm thấy reward URL")
                else:
                    print("[!] Không phải ontops.link")
            else:
                print("[!] Không thể lấy API redirect")
        else:
            print("[!] Không thể trích xuất hash từ link")
    else:
        print("[!] Không thể lấy redirect URL")

def menu_tadao():
    print("\n=== TÀ ĐẠO ===")
    print("1. iOS")
    print("2. ADR")
    choice = input("Chọn: ").strip()
    if choice == "1":
        fname = IOS_KEY_FILE
    elif choice == "2":
        fname = ADR_KEY_FILE
    else:
        print("[!] Lựa chọn không hợp lệ")
        return
    count = input("Nhập số lượng: ").strip()
    try:
        count = int(count)
    except ValueError:
        print("[!] Số lượng không hợp lệ")
        return
    print(f"[*] Đang tạo {count} key...")
    keys = []
    for i in range(count):
        key = f"tadao_{int(time.time())}_{i}"
        keys.append(key)
        print(f"  [{i+1}/{count}] {key}")
    with open(fname, "a") as f:
        for k in keys:
            f.write(k + "\n")
    print(f"[+] Đã lưu vào {fname}")

def main():
    print("=" * 40)
    print("  Welcome Buy key ib: m.hieuu5")
    print("=" * 40)

    saved = load_saved_key()
    if saved:
        print(f"[*] Đang kiểm tra key đã lưu: {saved}")
        ok, msg, days = verify_key(saved)
        if ok:
            print(f"[+] Key hợp lệ! Còn {days} ngày")
            print(f"[+] Thông báo: {msg}")
        else:
            print(f"[!] {msg}")
            saved = None

    if not saved:
        while True:
            key = input("\nNhập key: ").strip()
            if not key:
                continue
            ok, msg, days = verify_key(key)
            if ok:
                print(f"[+] Key hợp lệ! Còn {days} ngày")
                print(f"[+] Thông báo: {msg}")
                save_key(key)
                break
            else:
                print(f"[!] {msg}")

    while True:
        print("\n" + "=" * 40)
        print("1. Lấy key iOS")
        print("2. Lấy key ADR")
        print("3. Tà đạo")
        print("4. Đăng xuất key")
        print("=" * 40)
        choice = input("Chọn: ").strip()
        if choice == "1":
            menu_getkey_ios()
        elif choice == "2":
            menu_getkey_adr()
        elif choice == "3":
            menu_tadao()
        elif choice == "4":
            clear_saved_key()
            print("[+] Đã đăng xuất key!")
            break
        else:
            print("[!] Lựa chọn không hợp lệ")

if __name__ == "__main__":
    main()
