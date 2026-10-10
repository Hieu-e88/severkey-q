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


def parse_keys(raw: str) -> dict[str, str]:
    """
    Format Key_tc.txt:
        key|thông báo
    VD: meobeodns_vipdnske82j|Update v2 mới nhé!
    Không có phần ngày nữa.
    """
    keys: dict[str, str] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if "|" in line:
            key, msg = line.split("|", 1)
        else:
            key, msg = line, ""
        keys[key.strip()] = msg.strip()
    return keys


def verify_key(input_key: str) -> tuple[bool, str]:
    raw = fetch_keys()
    if raw is None:
        return False, "Không thể kết nối server key"
    keys = parse_keys(raw)
    if input_key in keys:
        return True, keys[input_key]
    return False, "Key sai hoặc không tồn tại"


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

# ─── Core fetch functions (dùng cho menu đơn lẻ và batch Tà đạo) ─────────────

def _extract_any_url_param(url: str) -> Optional[str]:
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)
    raw    = params.get("url", [""])[0]
    return urllib.parse.unquote(raw) if raw else None


def fetch_key_adr() -> Optional[str]:
    """Lấy 1 key ADR — trả về key string hoặc None."""
    _, _, hdrs = get_page(
        "https://goctool.vn/GETKEY/tumadam/com.garena.game.kgvn",
        follow_redirects=False,
    )
    redirect_url = hdrs.get("Location", "")
    if not redirect_url:
        print("[!] Không lấy được redirect URL")
        return None
    print(f"[*] Redirect: {redirect_url}")
    decoded = _resolve_api_redirect(redirect_url)
    if not decoded:
        return None
    reward = extract_reward_url(decoded)
    if not reward:
        print("[!] Không tìm thấy reward URL")
    return reward


def fetch_key_ipa() -> Optional[str]:
    """Lấy 1 shortlink IPA MOB — trả về link string hoặc None."""
    url       = "https://honghac86.com/getkey.php?partner=admin"
    post_data = urllib.parse.urlencode({
        "action": "generate_bypass_link", "hwid": "", "customer_name": "Khách iOS",
    }).encode("utf-8")
    headers = {
        **DEFAULT_HEADERS,
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.5",
        "Origin": "https://honghac86.com",
        "Referer": url,
    }
    try:
        req = urllib.request.Request(url, data=post_data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
        payload   = json.loads(raw)
        shortlink = payload.get("shortlink_url", "").replace("\\/", "/")
        return shortlink or None
    except json.JSONDecodeError:
        print("[!] Response không phải JSON")
    except Exception as e:
        print(f"[!] Lỗi IPA: {e}")
    return None


def fetch_key_proxy() -> Optional[str]:
    """Lấy 1 link Proxy V4 — trả về link string hoặc None."""
    api_url   = "https://solitudepremium.click/kzmod/key.php"
    post_data = urllib.parse.urlencode({
        "action": "generate_bypass_link", "hwid": "", "customer_name": "Khách Proxy",
    }).encode("utf-8")
    headers = {
        **DEFAULT_HEADERS,
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "text/html,application/xhtml+xml,*/*",
        "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
        "Origin": "https://solitudepremium.click",
        "Referer": api_url,
    }
    try:
        req = urllib.request.Request(api_url, data=post_data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=20) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        # &amp;url= / &url= / ?url=
        m = re.search(r'(?:&amp;|[?&])url=(http[^"\'&\s<>]+)', html, re.IGNORECASE)
        if m:
            return urllib.parse.unquote(m.group(1))
        # input hidden name="url"
        m = re.search(
            r'name=["\']url["\'][^>]*value=["\']([^"\']+)["\']'
            r'|value=["\']([^"\']+)["\'][^>]*name=["\']url["\']',
            html, re.IGNORECASE
        )
        if m:
            return urllib.parse.unquote(m.group(1) or m.group(2))
        # token/key URL
        m = re.search(r'https?://[^\s"\'<>]*(?:token|key|access)[^\s"\'<>]*', html, re.IGNORECASE)
        if m:
            return m.group(0)
        print("[!] Không tìm thấy URL trong response")
        print(f"[~] HTML (300c): {html[:300]}")
    except urllib.error.HTTPError as e:
        print(f"[!] HTTP {e.code}")
    except Exception as e:
        print(f"[!] Lỗi Proxy: {e}")
    return None


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
            if not repeat_menu(): return
            continue
        result = extract_result_param(decoded)
        if result:
            _clip_and_save(result, IOS_KEY_FILE, label="KEY iOS")
        else:
            print("[!] Không tìm thấy result param")
        if not repeat_menu(): return


def menu_getkey_adr() -> None:
    while True:
        print("\n=== LẤY KEY ADR ===")
        result = fetch_key_adr()
        if result:
            _clip_and_save(result, ADR_KEY_FILE, label="KEY ADR")
        if not repeat_menu(): return


def menu_ipa_mob() -> None:
    while True:
        print("\n=== IPA MOB ===")
        result = fetch_key_ipa()
        if result:
            _clip_and_save(result, ADR_KEY_FILE, label="SHORTLINK IPA MOB")
        else:
            print("[!] Không lấy được link")
        if not repeat_menu(): return


def menu_proxy_v4() -> None:
    while True:
        print("\n=== PROXY V4 ===")
        result = fetch_key_proxy()
        if result:
            _clip_and_save(result, PROXY_KEY_FILE, label="LINK PROXY V4")
        if not repeat_menu(): return


# ─── Tà đạo: batch tất cả loại ───────────────────────────────────────────────

# (fetch_fn=None → yêu cầu tương tác thủ công, xử lý riêng)
_BATCH_TYPES: dict[str, tuple] = {
    "1": ("iOS",      None,            IOS_KEY_FILE,   "KEY iOS"),
    "2": ("ADR",      fetch_key_adr,   ADR_KEY_FILE,   "KEY ADR"),
    "3": ("IPA MOB",  fetch_key_ipa,   ADR_KEY_FILE,   "SHORTLINK IPA MOB"),
    "4": ("PROXY V4", fetch_key_proxy, PROXY_KEY_FILE, "LINK PROXY V4"),
}


def _batch_run_auto(name: str, fetch_fn, save_file: Path,
                    label: str, count: int, delay: float) -> int:
    """Chạy batch cho loại key có thể tự động fetch. Trả về số key thành công."""
    ok = 0
    for i in range(1, count + 1):
        print(f"\n  [{i}/{count}] Đang lấy {name}...")
        result = fetch_fn()
        if result:
            show_value(f"{label} [{i}/{count}]", result)
            append_key_to_file(save_file, result)
            ok += 1
        else:
            print(f"  [!] Lần {i} thất bại")
        if i < count and delay > 0:
            time.sleep(delay)
    return ok


def _batch_run_ios(count: int) -> int:
    """Batch iOS — yêu cầu tương tác browser, lặp count lần."""
    ok = 0
    for i in range(1, count + 1):
        print(f"\n{'─'*38}")
        print(f"  iOS [{i}/{count}] — Cần mở trình duyệt")
        print(f"{'─'*38}")
        html, _, _ = get_page("https://unlock.tumadam.com/getkeylqm.html")
        if not html:
            print("  [!] Không tải được trang, bỏ qua")
            continue
        links = extract_authtool_links(html)
        if not links:
            print("  [!] Không tìm thấy link authtool")
            continue
        show_value("LINK AUTHTOOL", links[0])
        input("  Hoàn thành nhiệm vụ → nhấn Enter...")
        user_link = safe_input("  Nhập link unlock.tumadam.com: ").strip()
        if "unlock.tumadam.com" not in user_link:
            print("  [!] Link không hợp lệ, bỏ qua")
            continue
        decoded = _resolve_api_redirect(user_link)
        if decoded:
            result = extract_result_param(decoded)
            if result:
                show_value(f"KEY iOS [{i}/{count}]", result)
                append_key_to_file(IOS_KEY_FILE, result)
                ok += 1
                continue
        print("  [!] Không lấy được key iOS lần này")
    return ok


def menu_tadao() -> None:
    while True:
        print("\n╔══════════════════════════════════╗")
        print("║       TÀ ĐẠO — Batch Key         ║")
        print("╠══════════════════════════════════╣")
        for k, (name, *_) in _BATCH_TYPES.items():
            print(f"║  {k}. {name:<30}║")
        print("║  5. Tất cả cùng lúc              ║")
        print("╚══════════════════════════════════╝")

        choice = safe_input("Chọn loại key: ")
        if choice not in _BATCH_TYPES and choice != "5":
            print("[!] Lựa chọn không hợp lệ")
            continue

        try:
            count = int(safe_input("Số lượng mỗi loại: "))
            if count <= 0: raise ValueError
        except ValueError:
            print("[!] Số lượng không hợp lệ"); continue

        delay = 0.0
        try:
            d = safe_input("Delay giữa request (giây, Enter=0): ")
            if d: delay = float(d)
        except ValueError:
            pass

        jobs = list(_BATCH_TYPES.values()) if choice == "5" else [_BATCH_TYPES[choice]]
        summary: list[tuple[str,int,int]] = []   # (name, ok, total)

        for name, fetch_fn, save_file, label in jobs:
            print(f"\n{'═'*38}")
            print(f"  ▶ {name}  ×{count}")
            print(f"{'═'*38}")
            if fetch_fn is None:          # iOS — manual
                ok = _batch_run_ios(count)
            else:
                ok = _batch_run_auto(name, fetch_fn, save_file, label, count, delay)
            summary.append((name, ok, count))

        # ── Tổng kết ──────────────────────────────────────────────────────
        print(f"\n╔══════════════════════════════════╗")
        print(f"║           TỔNG KẾT               ║")
        print(f"╠══════════════════════════════════╣")
        total_ok = 0
        for name, ok, total in summary:
            bar  = "█" * ok + "░" * (total - ok)
            print(f"║  {name:<10} {bar:<12} {ok}/{total}       ║")
            total_ok += ok
        print(f"╠══════════════════════════════════╣")
        print(f"║  Tổng: {total_ok} key thành công{'':<14}║")
        print(f"╚══════════════════════════════════╝")

        if not repeat_menu(): return


# ─── Xuất key ────────────────────────────────────────────────────────────────

_EXPORT_FILES: dict[str, tuple[str, Path]] = {
    "1": ("iOS",      IOS_KEY_FILE),
    "2": ("ADR",      ADR_KEY_FILE),
    "3": ("Proxy V4", PROXY_KEY_FILE),
    "4": ("ios.txt",  BASE_DIR / "ios.txt"),
    "5": ("adr.txt",  BASE_DIR / "adr.txt"),
}


def menu_export() -> None:
    while True:
        print("\n╔══════════════════════════════════╗")
        print("║         XUẤT KEY                 ║")
        print("╠══════════════════════════════════╣")

        # Hiện số lượng key mỗi file
        for k, (name, path) in _EXPORT_FILES.items():
            lines = []
            if path.exists():
                lines = [l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
            print(f"║  {k}. {name:<14} ({len(lines)} key)         ║")

        print("║  6. Tất cả → 1 file xuất        ║")
        print("║  7. 🗑  Reset — xóa toàn bộ file ║")
        print("╚══════════════════════════════════╝")

        choice = safe_input("Chọn: ")

        if choice in _EXPORT_FILES:
            name, path = _EXPORT_FILES[choice]
            if not path.exists() or path.stat().st_size == 0:
                print(f"[!] File {path} trống hoặc chưa có key")
                if not repeat_menu(): return
                continue
            lines = [l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
            print(f"\n{'═'*40}")
            print(f"  {name} — {len(lines)} key")
            print(f"{'═'*40}")
            all_text = "\n".join(lines)
            for i, line in enumerate(lines, 1):
                print(f"  [{i:>3}] {line}")
            ok = copy_to_clipboard(all_text)
            print(f"\n{'═'*40}")
            if ok:
                print("  ✓ Đã copy tất cả vào clipboard")
            else:
                print("  ⚠ Bấm giữ dòng key để copy thủ công")
            print(f"{'═'*40}")

        elif choice == "6":
            out_path = BASE_DIR / "all_keys_export.txt"
            total    = 0
            with out_path.open("w", encoding="utf-8") as out:
                for name, path in _EXPORT_FILES.values():
                    if not path.exists(): continue
                    lines = [l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
                    if not lines: continue
                    out.write(f"# ── {name} ({len(lines)} key) ──\n")
                    for line in lines:
                        out.write(line + "\n")
                    out.write("\n")
                    total += len(lines)
            print(f"\n[+] Xuất {total} key → {out_path}")
            all_text = out_path.read_text(encoding="utf-8")
            if copy_to_clipboard(all_text):
                print("[+] Đã copy tất cả vào clipboard ✓")
            else:
                print(f"[~] Mở file {out_path} để xem toàn bộ")

        elif choice == "7":
            # ── Reset: xóa toàn bộ file key ──────────────────────────────
            print("\n╔══════════════════════════════════╗")
            print("║  ⚠  Xác nhận xóa TẤT CẢ file?  ║")
            print("║     Gõ  YES  để xác nhận        ║")
            print("╚══════════════════════════════════╝")
            confirm = safe_input("  Xác nhận: ")
            if confirm.upper() != "YES":
                print("[~] Huỷ reset")
            else:
                deleted = 0
                # Xóa các file key + file export tổng hợp
                extra = [BASE_DIR / "all_keys_export.txt",
                         BASE_DIR / "ios.txt",
                         BASE_DIR / "adr.txt"]
                for _, path in _EXPORT_FILES.values():
                    if path.exists():
                        path.unlink()
                        print(f"  🗑 Đã xóa {path.name}")
                        deleted += 1
                for path in extra:
                    if path.exists() and path not in [p for _, p in _EXPORT_FILES.values()]:
                        path.unlink()
                        print(f"  🗑 Đã xóa {path.name}")
                        deleted += 1
                print(f"\n[+] Reset xong — đã xóa {deleted} file")

        else:
            print("[!] Lựa chọn không hợp lệ")

        if not repeat_menu(): return


# ─── Entry point ─────────────────────────────────────────────────────────────

_MENU_ACTIONS = {
    "1": menu_getkey_ios,
    "2": menu_getkey_adr,
    "3": menu_proxy_v4,
    "4": menu_ipa_mob,
    "5": menu_tadao,
    "6": menu_export,
}


def _show_login_success(msg: str) -> None:
    W   = 40
    bar = "═" * W
    def row(text: str) -> str:
        return f"║ {text:<{W-1}}║"
    print(f"\n╔{bar}╗")
    print(row("✅  DANG NHAP THANH CONG"))
    print(f"╠{bar}╣")
    print(row("Key hop le!"))
    if msg:
        print(f"╠{bar}╣")
        print(row("📢 Thong bao:"))
        step = W - 3
        for i in range(0, len(msg), step):
            print(row("  " + msg[i:i+step]))
    print(f"╚{bar}╝")


def _show_key_expired() -> None:
    W   = 40
    bar = "═" * W
    def row(text: str) -> str:
        return f"║ {text:<{W-1}}║"
    print(f"\n╔{bar}╗")
    print(row("❌  KEY DA HET HAN"))
    print(f"╠{bar}╣")
    print(row("Vui long lien he de mua key moi:"))
    print(row("  👉  @m.hieuu5"))
    print(f"╚{bar}╝\n")


def main() -> None:
    print("=" * 40)
    print("  Welcome Buy key ib: m.hieuu5")
    print("=" * 40)

    saved = load_saved_key()
    if saved:
        print(f"[*] Dang kiem tra key: {saved}")
        ok, msg = verify_key(saved)
        if ok:
            _show_login_success(msg)
        else:
            # Key lưu ở máy nhưng không còn tồn tại trên server → hết hạn
            clear_saved_key()
            _show_key_expired()
            saved = None

    while not saved:
        key = safe_input("Nhap key: ")
        if not key: continue
        ok, msg = verify_key(key)
        if ok:
            _show_login_success(msg)
            save_key(key)
            saved = key
        else:
            _show_key_expired()

    while True:
        print("\n" + "=" * 40)
        print("1. Lấy key iOS")
        print("2. Lấy key ADR")
        print("3. Proxy V4")
        print("4. IPA MOB")
        print("5. Tà đạo  (batch)")
        print("6. Xuất key")
        print("7. Đăng xuất")
        print("=" * 40)
        choice = safe_input("Chọn: ")
        if not choice: return

        if choice == "7":
            print("\n╔══════════════════════════════════╗")
            print("║  ⚠  Xác nhận đăng xuất?         ║")
            print("║     Gõ  YES  để xác nhận        ║")
            print("╚══════════════════════════════════╝")
            if safe_input("  Xác nhận: ").upper() == "YES":
                clear_saved_key()
                print("[+] Đã đăng xuất — key đã lưu bị xóa")
                print("[~] Khởi động lại tool để đăng nhập lại")
                return
            else:
                print("[~] Huỷ đăng xuất")
            continue

        action = _MENU_ACTIONS.get(choice)
        if action:
            action()
        else:
            print("[!] Lựa chọn không hợp lệ")


if __name__ == "__main__":
    main()

