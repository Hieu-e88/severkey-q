# -*- coding: utf-8 -*-
#!/usr/bin/env python3
"""
Key manager tool - optimized version
"""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path
from typing import Optional

# ─── Constants ───────────────────────────────────────────────────────────────

KEY_URL    = "https://raw.githubusercontent.com/Hieu-e88/severkey-q/refs/heads/main/Key_tc.txt"
BASE_DIR   = Path.cwd()
KEY_FILE   = BASE_DIR / ".severkey_saved"
IOS_KEY_FILE   = BASE_DIR / "key_ios.txt"
ADR_KEY_FILE   = BASE_DIR / "key_adr.txt"
PROXY_KEY_FILE = BASE_DIR / "key_proxy_v4.txt"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

MOBILE_UA = {"User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36"}

# ─── Types ────────────────────────────────────────────────────────────────────

KeyInfo = dict[str, str]          # {"days": str, "msg": str}
PageResult = tuple[str, str, dict] # (html, final_url, headers)

# ─── Clipboard ────────────────────────────────────────────────────────────────

_CLIPBOARD_CMDS: list[list[str]] = [
    ["termux-clipboard-set", "{text}"],
    ["pbcopy"],
    ["xclip", "-selection", "clipboard"],
    ["wl-copy"],
    ["xsel", "--clipboard", "--input"],
]


def _copy_osc52(text: str) -> bool:
    """
    OSC 52 — hoạt động trên Termux (Android) và a-Shell/iSH (iOS).
    Ghi escape sequence thẳng vào terminal, không cần cài thêm gì.
    """
    try:
        b64 = base64.b64encode(text.encode("utf-8")).decode()
        seq = f"\033]52;c;{b64}\007".encode()

        # Thử /dev/tty trước (Termux / Linux)
        for tty_path in ("/dev/tty", "/dev/stderr"):
            if os.path.exists(tty_path):
                try:
                    with open(tty_path, "wb") as tty:
                        tty.write(seq)
                        tty.flush()
                    return True
                except OSError:
                    continue

        # iOS shell (a-Shell / iSH): /dev/tty có thể không có
        # → ghi thẳng qua stderr fd để tránh bị pipe nuốt
        try:
            os.write(2, seq)   # fd 2 = stderr, luôn tới terminal
            return True
        except OSError:
            pass

        # Last resort: stdout buffer
        sys.stdout.buffer.write(seq)
        sys.stdout.flush()
        return True

    except Exception:
        return False

def _cmd_exists(name: str) -> bool:
    """Check if a shell command is available on PATH."""
    import shutil
    return shutil.which(name) is not None


def copy_to_clipboard(text: str) -> bool:
    """
    Thứ tự ưu tiên:
      1. OSC 52  — hoạt động thẳng trong Termux, không cần cài gì
      2. termux-clipboard-set / pbcopy / xclip / wl-copy / xsel
      3. pyperclip
    """
    # 1. OSC 52 (Termux native)
    if _copy_osc52(text):
        return True

    # 2. System commands
    encoded = text.encode()
    for cmd_template in _CLIPBOARD_CMDS:
        bin_name = cmd_template[0]
        if not _cmd_exists(bin_name):
            continue
        cmd = [c.replace("{text}", text) for c in cmd_template]
        try:
            if bin_name == "termux-clipboard-set":
                subprocess.run(cmd, check=True, capture_output=True, timeout=5)
            else:
                subprocess.run(cmd, input=encoded, check=True, capture_output=True, timeout=5)
            return True
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError):
            continue

    # 3. pyperclip fallback
    try:
        import pyperclip  # type: ignore
        pyperclip.copy(text)
        return True
    except Exception:
        pass

    return False

# ─── HTTP helpers ─────────────────────────────────────────────────────────────

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore
        return None


def get_page(
    url: str,
    headers: Optional[dict] = None,
    follow_redirects: bool = True,
    timeout: int = 20,
) -> PageResult:
    """Fetch a URL; return (html, final_url, response_headers)."""
    h = {**MOBILE_UA, **(headers or {})}
    req = urllib.request.Request(url, headers=h)

    if not follow_redirects:
        opener = urllib.request.build_opener(_NoRedirect)
        try:
            resp = opener.open(req, timeout=timeout)
            return resp.read().decode("utf-8", errors="ignore"), resp.geturl(), dict(resp.headers)
        except urllib.error.HTTPError as e:
            return e.read().decode("utf-8", errors="ignore"), e.url or url, dict(e.headers)

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore"), resp.geturl(), dict(resp.headers)


def get_redirect_location(url: str) -> str:
    """Return the Location header from a non-following request, or ''."""
    try:
        _, _, hdrs = get_page(url, follow_redirects=False)
        return hdrs.get("Location", "")
    except Exception:
        return ""

# ─── Key store ────────────────────────────────────────────────────────────────

def fetch_keys() -> Optional[str]:
    try:
        req = urllib.request.Request(KEY_URL, headers=DEFAULT_HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"[!] Không thể kết nối server key: {e}")
        return None


def parse_keys(raw: str) -> dict[str, KeyInfo]:
    keys: dict[str, KeyInfo] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or "|" not in line:
            continue
        parts = line.split("|")
        keys[parts[0].strip()] = {
            "days": parts[1].strip() if len(parts) > 1 else "?",
            "msg":  parts[2].strip() if len(parts) > 2 else "",
        }
    return keys


def verify_key(input_key: str) -> tuple[bool, str, Optional[str]]:
    raw = fetch_keys()
    if raw is None:
        return False, "Không thể kết nối server key", None
    keys = parse_keys(raw)
    if input_key in keys:
        info = keys[input_key]
        return True, info["msg"], info["days"]
    return False, "Key sai hoặc không tồn tại", None


def save_key(key: str)   -> None: KEY_FILE.write_text(key)
def load_saved_key()     -> Optional[str]: return KEY_FILE.read_text().strip() if KEY_FILE.exists() else None
def clear_saved_key()    -> None:
    if KEY_FILE.exists():
        KEY_FILE.unlink()


def append_key_to_file(path: Path, value: str) -> None:
    with path.open("a") as f:
        f.write(value + "\n")
    print(f"[+] Đã lưu vào {path}")

# ─── Regex extractors ─────────────────────────────────────────────────────────

def extract_authtool_links(html: str) -> list[str]:
    for pattern in (
        r'https?://authtool\.app/get-key\?code=[a-f0-9\-]+',
        r'https?://authtool\.app/get-key/[^\s"\'<>]+',
    ):
        links = list(set(re.findall(pattern, html)))
        if links:
            return links
    return []


def extract_ontops_url(html: str) -> Optional[str]:
    for pattern in (
        r'https?://ontops\.link/st\?apikey=[^\s"\'<>]+',
        r'https?://ontops\.link/[^\s"\'<>]+',
    ):
        matches = re.findall(pattern, html)
        if matches:
            return urllib.parse.unquote(matches[0])
    return None


def extract_result_param(url: str) -> Optional[str]:
    m = re.search(r'result=([^&]+)', url)
    return m.group(1) if m else None


def extract_reward_url(html: str) -> Optional[str]:
    for pattern in (
        r'https?://goctool\.vn/GETKEY/tumadam/reward/[A-Za-z0-9]+',
        r'https?://goctool\.vn/GETKEY/tumadam/reward/[^\s"\'<>]+',
    ):
        matches = re.findall(pattern, html)
        if matches:
            return matches[0]
    return None


def extract_hash_from_unlock_url(url: str) -> Optional[str]:
    m = re.search(r'/([a-z0-9]+)\.html', url)
    return m.group(1) if m else None

# ─── Shared helpers ───────────────────────────────────────────────────────────

def safe_input(prompt: str = "") -> str:
    try:
        return input(prompt).strip()
    except EOFError:
        return ""


def repeat_menu() -> bool:
    print("\n╔══════════════════════════╗")
    print("║    🔔 Hệ thống thông báo  ║")
    print("╠══════════════════════════╣")
    print("║  1. Làm lại              ║")
    print("║  2. Thoát                ║")
    print("╚══════════════════════════╝")
    return safe_input("  Chọn: ") == "1"


def show_value(label: str, value: str) -> None:
    """Luôn hiển thị value nổi bật. Clipboard là bonus."""
    w = max(len(value) + 4, len(label) + 4, 44)
    bar = "═" * w
    print(f"\n╔{bar}╗")
    print(f"║  {label:<{w-2}}║")
    print(f"╠{bar}╣")
    print(f"║  {value:<{w-2}}║")
    print(f"╚{bar}╝")
    ok = copy_to_clipboard(value)
    if ok:
        print("  ✓ Đã copy vào clipboard tự động")
    else:
        print("  ⚠ Bấm giữ vào dòng trên → Copy để lấy")


def _clip_and_save(value: str, path: Path, label: str = "KẾT QUẢ") -> None:
    show_value(label, value)
    append_key_to_file(path, value)


def _resolve_api_redirect(unlock_url: str) -> Optional[str]:
    """
    Given an unlock.tumadam.com URL, call its /api/go/<hash>.html endpoint
    and return the decoded Location header, or None on failure.
    """
    hash_val = extract_hash_from_unlock_url(unlock_url)
    if not hash_val:
        print("[!] Không thể trích xuất hash từ link")
        return None

    api_url = f"https://unlock.tumadam.com/api/go/{hash_val}.html"
    print(f"[*] API URL: {api_url}")

    _, _, api_hdrs = get_page(api_url, follow_redirects=False)
    redirect = api_hdrs.get("Location", "")
    if not redirect:
        print("[!] Không thể lấy API redirect")
        return None

    print(f"[*] API Redirect: {redirect}")
    if "ontops.link" not in redirect:
        print("[!] Không phải ontops.link")
        return None

    return urllib.parse.unquote(redirect)

# ─── Menus ────────────────────────────────────────────────────────────────────

def menu_getkey_ios() -> None:
    while True:
        print("\n=== LẤY KEY iOS ===")
        html, _, _ = get_page("https://unlock.tumadam.com/getkeylqm.html")
        if not html:
            print("[!] Không thể tải trang")
            return

        links = extract_authtool_links(html)
        if not links:
            print("[!] Không tìm thấy link authtool.app")
            return

        show_value("LINK AUTHTOOL (mở trình duyệt dán vào)", links[0])
        if len(links) > 1:
            print("  Link dự phòng:")
            for i, link in enumerate(links[1:], 2):
                print(f"    {i}. {link}")

        input("\nHoàn thành nhiệm vụ xong nhấn Enter để tiếp tục...")

        user_link = safe_input("\n[*] Nhập link unlock.tumadam.com:\n").strip()
        if "unlock.tumadam.com" not in user_link:
            print("[!] Link không hợp lệ!")
            return

        print("[*] Đang xử lý...")
        decoded = _resolve_api_redirect(user_link)
        if decoded is None:
            if not repeat_menu():
                return
            continue

        result = extract_result_param(decoded)
        if result:
            _clip_and_save(result, IOS_KEY_FILE, label="KEY iOS")
        else:
            print("[!] Không tìm thấy result param")

        if not repeat_menu():
            return


def menu_getkey_adr() -> None:
    while True:
        print("\n=== LẤY KEY ADR ===")
        _, _, hdrs = get_page(
            "https://goctool.vn/GETKEY/tumadam/com.garena.game.kgvn",
            follow_redirects=False,
        )

        redirect_url = hdrs.get("Location", "")
        if not redirect_url:
            print("[!] Không thể lấy redirect URL")
            if not repeat_menu():
                return
            continue

        print(f"[*] Redirect: {redirect_url}")
        decoded = _resolve_api_redirect(redirect_url)
        if decoded is None:
            if not repeat_menu():
                return
            continue

        reward = extract_reward_url(decoded)
        if reward:
            _clip_and_save(reward, ADR_KEY_FILE, label="KEY ADR")
        else:
            print("[!] Không tìm thấy reward URL")

        if not repeat_menu():
            return


def menu_ipa_mob() -> None:
    url = "https://honghac86.com/getkey.php?partner=admin"
    while True:
        print(f"\n=== IPA MOB ===\n[*] Đang gọi API: {url}")
        post_data = urllib.parse.urlencode({
            "action":        "generate_bypass_link",
            "hwid":          "",
            "customer_name": "Khách iOS",
        }).encode("utf-8")

        headers = {
            **DEFAULT_HEADERS,
            "Content-Type":  "application/x-www-form-urlencoded",
            "Accept":        "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.5",
            "Origin":        "https://honghac86.com",
            "Referer":       url,
        }
        req = urllib.request.Request(url, data=post_data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
            payload = json.loads(raw)
            shortlink = payload.get("shortlink_url", "").replace("\\/", "/")
            if shortlink:
                _clip_and_save(shortlink, ADR_KEY_FILE, label="SHORTLINK IPA MOB")
            else:
                print("[!] Không tìm thấy shortlink_url trong response")
        except json.JSONDecodeError:
            print("[!] Response không phải JSON")
        except Exception as e:
            print(f"[!] Lỗi: {e}")

        if not repeat_menu():
            return


def _extract_any_url_param(url: str) -> Optional[str]:
    """Lấy param 'url' từ bất kỳ shortlink nào."""
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)
    raw = params.get("url", [""])[0]
    return urllib.parse.unquote(raw) if raw else None


def menu_proxy_v4() -> None:
    api_url = "https://solitudepremium.click/kzmod/key.php"
    while True:
        print(f"\n=== PROXY V4 ===\n[*] Đang gọi API: {api_url}")

        post_data = urllib.parse.urlencode({
            "action":        "generate_bypass_link",
            "hwid":          "",
            "customer_name": "Khách Proxy",
        }).encode("utf-8")

        headers = {
            **DEFAULT_HEADERS,
            "Content-Type":    "application/x-www-form-urlencoded",
            "Accept":          "text/html,application/xhtml+xml,*/*",
            "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
            "Origin":          "https://solitudepremium.click",
            "Referer":         "https://solitudepremium.click/kzmod/key.php",
        }

        try:
            req = urllib.request.Request(
                api_url, data=post_data, headers=headers, method="POST"
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                html = resp.read().decode("utf-8", errors="ignore")

            # HTML dạng: action="/st?api=xxx&amp;url=http%3A%2F%2F..."
            result = ""

            # Pattern 1: &amp;url= hoặc &url= hoặc ?url= (ưu tiên nhất)
            m = re.search(
                r'(?:&amp;|[?&])url=(http[^"\'&\s<>]+)',
                html, re.IGNORECASE
            )
            if m:
                result = urllib.parse.unquote(m.group(1))
                print(f"[*] URL từ param: {result}")

            # Pattern 2: input hidden name="url"
            if not result:
                m = re.search(
                    r'name=["\']url["\'][^>]*value=["\']([^"\']+)["\']'
                    r'|value=["\']([^"\']+)["\'][^>]*name=["\']url["\']',
                    html, re.IGNORECASE
                )
                if m:
                    raw = m.group(1) or m.group(2)
                    result = urllib.parse.unquote(raw)
                    print(f"[*] URL từ input hidden: {result}")

            # Pattern 3: URL chứa token/key
            if not result:
                m = re.search(
                    r'https?://[^\s"\'<>]*(?:token|key|access)[^\s"\'<>]*',
                    html, re.IGNORECASE
                )
                if m:
                    result = m.group(0)
                    print(f"[*] Token URL: {result}")

            if result:
                _clip_and_save(result, PROXY_KEY_FILE, label="LINK PROXY V4")
            else:
                print("[!] Không tìm thấy URL trong response")
                print(f"[~] HTML (500 ký tự): {html[:500]}")

        except urllib.error.HTTPError as e:
            print(f"[!] HTTP {e.code}: {e.read().decode('utf-8', errors='ignore')[:200]}")
        except Exception as e:
            print(f"[!] Lỗi: {e}")

        if not repeat_menu():
            return


_TADAO_TYPES: dict[str, str] = {
    "1": "ios",
    "2": "adr",
}

def menu_tadao() -> None:
    while True:
        print("\n=== TÀ ĐẠO ===")
        for k, v in _TADAO_TYPES.items():
            print(f"{k}. {v.upper()}")

        choice = safe_input("Chọn loại key: ")
        key_type = _TADAO_TYPES.get(choice)
        if not key_type:
            print("[!] Lựa chọn không hợp lệ")
            continue

        try:
            count = int(safe_input("Nhập số lượng: "))
            if count <= 0:
                raise ValueError
        except ValueError:
            print("[!] Số lượng không hợp lệ")
            continue

        # File lưu theo tên loại key: ios.txt / adr.txt
        fname = BASE_DIR / f"{key_type}.txt"
        ts    = int(time.time())
        keys  = [f"tadao_{key_type}_{ts}_{i}" for i in range(count)]

        print(f"\n[*] Đang tạo {count} key {key_type.upper()}...\n")

        for i, k in enumerate(keys, 1):
            # Hiển thị + copy từng key
            show_value(f"KEY {key_type.upper()} [{i}/{count}]", k)
            time.sleep(0.05)   # nhỏ để terminal kịp flush OSC52

        # Lưu tất cả vào file
        with fname.open("a") as f:
            f.writelines(k + "\n" for k in keys)

        print(f"\n[+] Đã lưu {count} key vào  →  {fname}")

        if not repeat_menu():
            return

# ─── Entry point ─────────────────────────────────────────────────────────────

_MENU_ACTIONS = {
    "1": menu_getkey_ios,
    "2": menu_getkey_adr,
    "3": menu_proxy_v4,
    "4": menu_ipa_mob,
    "5": menu_tadao,
}

def main() -> None:
    print("=" * 40)
    print("  Welcome Buy key ib: m.hieuu5")
    print("=" * 40)

    # Try cached key first
    saved = load_saved_key()
    if saved:
        print(f"[*] Đang kiểm tra key đã lưu: {saved}")
        ok, msg, days = verify_key(saved)
        if ok:
            print(f"[+] Key hợp lệ! Còn {days} ngày")
            if msg:
                print(f"[i] {msg}")
        else:
            print(f"[!] {msg}")
            saved = None

    # Prompt until valid key
    while not saved:
        key = safe_input("\nNhập key: ")
        if not key:
            continue
        ok, msg, days = verify_key(key)
        if ok:
            print(f"[+] Key hợp lệ! Còn {days} ngày")
            if msg:
                print(f"[i] {msg}")
            save_key(key)
            saved = key
        else:
            print(f"[!] {msg}")

    # Main loop
    while True:
        print("\n" + "=" * 40)
        print("1. Lấy key iOS")
        print("2. Lấy key ADR")
        print("3. Proxy V4")
        print("4. IPA MOB")
        print("5. Tà đạo")
        print("=" * 40)
        choice = safe_input("Chọn: ")
        if not choice:
            return
        action = _MENU_ACTIONS.get(choice)
        if action:
            action()
        else:
            print("[!] Lựa chọn không hợp lệ")


if __name__ == "__main__":
    main()

