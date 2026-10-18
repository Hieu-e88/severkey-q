# -*- coding: utf-8 -*-
#!/usr/bin/env python3
"""
Key Manager Tool - Modern Monochrome UI
Auto-detect iOS (iSH/a-Shell) & Android (Termux)
"""
from __future__ import annotations

import base64
import json
import os
import platform
import re
import shutil
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from pathlib import Path
from typing import Optional

# ─── Constants ───────────────────────────────────────────────────────────────

KEY_URL        = "https://raw.githubusercontent.com/Hieu-e88/severkey-q/refs/heads/main/Key_tc.txt"
BASE_DIR       = Path.cwd()
KEY_FILE       = BASE_DIR / ".severkey_saved"
IOS_KEY_FILE   = BASE_DIR / "key_ios.txt"
ADR_KEY_FILE   = BASE_DIR / "key_adr.txt"
PROXY_KEY_FILE = BASE_DIR / "key_proxy_v4.txt"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Connection": "keep-alive",
}

MOBILE_UA = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36",
    "Connection": "keep-alive",
}

try:
    _SSL_CTX = ssl.create_default_context()
except Exception:
    _SSL_CTX = None

# Biên dịch sẵn Regex giúp xử lý mượt hơn
_RE_AUTHTOOL_1  = re.compile(r'https?://authtool\.app/get-key\?code=[a-f0-9\-]+')
_RE_AUTHTOOL_2  = re.compile(r'https?://authtool\.app/get-key/[^\s"\'<>]+')
_RE_RESULT      = re.compile(r'result=([^&\s]+)')
_RE_AFTER_URL   = re.compile(r'[?&]url=([^&\s"\'<>]+)', re.IGNORECASE)
_RE_UNLOCK_HASH = re.compile(r'/([a-z0-9]+)\.html')
_RE_PROXY_URL_1 = re.compile(r'(?:&amp;|[?&])url=(http[^"\'&\s<>]+)', re.IGNORECASE)
_RE_PROXY_URL_2 = re.compile(
    r'name=["\']url["\'][^>]*value=["\']([^"\']+)["\']'
    r'|value=["\']([^"\']+)["\'][^>]*name=["\']url["\']',
    re.IGNORECASE,
)
_RE_PROXY_URL_3 = re.compile(r'https?://[^\s"\'<>]*(?:token|key|access)[^\s"\'<>]*', re.IGNORECASE)

PageResult = tuple[str, str, dict]

# ─── Nhận diện Hệ điều hành & Tên máy ─────────────────────────────────────────

@lru_cache(maxsize=32)
def _cmd_exists(name: str) -> bool:
    return shutil.which(name) is not None


@lru_cache(maxsize=1)
def detect_platform() -> str:
    """Trả về 'IOS', 'ANDROID', hoặc 'UNKNOWN'."""
    if (
        os.path.exists("/dev/clipboard")
        or os.path.exists("/proc/ish")
        or "ios" in sys.platform.lower()
        or os.environ.get("TERM_PROGRAM", "").lower() in ("a-shell", "ish")
    ):
        return "IOS"

    if (
        "TERMUX_VERSION" in os.environ
        or "com.termux" in os.environ.get("PREFIX", "")
        or os.path.exists("/data/data/com.termux")
    ):
        return "ANDROID"

    return "UNKNOWN"


@lru_cache(maxsize=1)
def get_os_device_name() -> str:
    """Lấy thông tin Hệ điều hành và Tên máy để hiển thị khi vào tool."""
    plat  = detect_platform()
    uname = platform.uname()

    if plat == "IOS":
        arch = uname.machine or "iPhone"
        if os.path.exists("/proc/ish") or os.path.exists("/dev/clipboard"):
            return f"iOS - iPhone/iPad (iSH {arch})"
        return f"iOS ({arch})"

    if plat == "ANDROID":
        model, ver = "", ""
        try:
            r_model = subprocess.run(
                ["getprop", "ro.product.model"],
                capture_output=True, text=True, timeout=1,
            )
            if r_model.returncode == 0:
                model = r_model.stdout.strip()

            r_ver = subprocess.run(
                ["getprop", "ro.build.version.release"],
                capture_output=True, text=True, timeout=1,
            )
            if r_ver.returncode == 0:
                ver = r_ver.stdout.strip()
        except Exception:
            pass

        os_label = f"Android {ver}".strip() if ver else "Android"
        if model:
            return f"{os_label} ({model} - Termux)"
        return f"{os_label} (Termux - {uname.machine})"

    sys_name = uname.system or "Unknown"
    node     = uname.node or uname.machine or "Device"
    return f"{sys_name} {uname.release} ({node})"

# ─── Clipboard (Tự động theo máy: iOS / Android / Cả hai) ─────────────────────

def _copy_osc52(text: str) -> bool:
    """OSC 52 — hoạt động trên Termux & a-Shell/SSH."""
    try:
        b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
        seq = f"\033]52;c;{b64}\007".encode("ascii")

        for tty_path in ("/dev/tty", "/dev/stderr"):
            if os.path.exists(tty_path):
                try:
                    with open(tty_path, "wb") as tty:
                        tty.write(seq)
                        tty.flush()
                    return True
                except OSError:
                    continue

        try:
            os.write(2, seq)
            return True
        except OSError:
            pass

        sys.stdout.buffer.write(seq)
        sys.stdout.flush()
        return True
    except Exception:
        return False


def _copy_ios(text: str) -> bool:
    """Copy cho iPhone (iSH / a-Shell / Pythonista)."""
    copied = False

    if os.path.exists("/dev/clipboard"):
        try:
            with open("/dev/clipboard", "wb") as f:
                f.write(text.encode("utf-8"))
                f.flush()
            copied = True
        except OSError:
            pass

    if not copied:
        try:
            import clipboard  # type: ignore
            clipboard.set(text)
            copied = True
        except Exception:
            pass

    if not copied and _cmd_exists("pbcopy"):
        try:
            subprocess.run(
                ["pbcopy"],
                input=text.encode("utf-8"),
                check=True,
                capture_output=True,
                timeout=2,
            )
            copied = True
        except Exception:
            pass

    if not copied:
        copied = _copy_osc52(text)

    return copied


def _copy_android(text: str) -> bool:
    """Copy cho Android (Termux): chạy cả OSC 52 và termux-clipboard-set."""
    osc_ok = _copy_osc52(text)
    api_ok = False
    if _cmd_exists("termux-clipboard-set"):
        try:
            subprocess.run(
                ["termux-clipboard-set", text],
                check=True,
                capture_output=True,
                timeout=1.5,
            )
            api_ok = True
        except Exception:
            pass
    return osc_ok or api_ok


def _copy_desktop_fallbacks(text: str) -> bool:
    encoded = text.encode("utf-8")
    for cmd in (
        ["xclip", "-selection", "clipboard"],
        ["wl-copy"],
        ["xsel", "--clipboard", "--input"],
        ["clip"],
    ):
        if not _cmd_exists(cmd[0]):
            continue
        try:
            subprocess.run(cmd, input=encoded, check=True, capture_output=True, timeout=2)
            return True
        except Exception:
            continue

    try:
        import pyperclip  # type: ignore
        pyperclip.copy(text)
        return True
    except Exception:
        return False


def copy_to_clipboard(text: str) -> bool:
    """
    - Nếu phát hiện iPhone (IOS)     -> Chạy copy iOS
    - Nếu phát hiện Android (Termux) -> Chạy copy Android
    - Nếu không phát hiện được       -> Thực hiện CẢ HAI + Desktop fallback
    """
    if not text:
        return False

    plat = detect_platform()
    if plat == "IOS":
        return _copy_ios(text)
    if plat == "ANDROID":
        return _copy_android(text)

    ok_ios     = _copy_ios(text)
    ok_android = _copy_android(text)
    ok_desktop = _copy_desktop_fallbacks(text)
    return ok_ios or ok_android or ok_desktop


def parse_line_selection(spec: str, max_len: int) -> list[int]:
    selected: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            try:
                start_s, end_s = part.split("-", 1)
                start, end = int(start_s), int(end_s)
                if start > end:
                    start, end = end, start
                for idx in range(start, end + 1):
                    if 1 <= idx <= max_len and (idx - 1) not in selected:
                        selected.append(idx - 1)
            except ValueError:
                continue
        else:
            try:
                idx = int(part)
                if 1 <= idx <= max_len and (idx - 1) not in selected:
                    selected.append(idx - 1)
            except ValueError:
                continue
    return selected

# ─── HTTP helpers ─────────────────────────────────────────────────────────────

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore
        return None


_NO_REDIRECT_OPENER = urllib.request.build_opener(_NoRedirect)


def get_page(
    url: str,
    headers: Optional[dict] = None,
    follow_redirects: bool = True,
    timeout: int = 15,
) -> PageResult:
    h = {**MOBILE_UA, **(headers or {})}
    req = urllib.request.Request(url, headers=h)

    if not follow_redirects:
        try:
            resp = _NO_REDIRECT_OPENER.open(req, timeout=timeout)
            return resp.read().decode("utf-8", errors="ignore"), resp.geturl(), dict(resp.headers)
        except urllib.error.HTTPError as e:
            return e.read().decode("utf-8", errors="ignore"), e.url or url, dict(e.headers)
        except Exception:
            return "", url, {}

    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:
            return resp.read().decode("utf-8", errors="ignore"), resp.geturl(), dict(resp.headers)
    except Exception:
        return "", url, {}

# ─── Key store ────────────────────────────────────────────────────────────────

def fetch_keys() -> Optional[str]:
    try:
        req = urllib.request.Request(KEY_URL, headers=DEFAULT_HEADERS)
        with urllib.request.urlopen(req, timeout=12, context=_SSL_CTX) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"[!] Không thể kết nối server key: {e}")
        return None


def parse_keys(raw: str) -> dict[str, str]:
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


def save_key(key: str) -> None:
    KEY_FILE.write_text(key, encoding="utf-8")


def load_saved_key() -> Optional[str]:
    try:
        return KEY_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None


def clear_saved_key() -> None:
    try:
        KEY_FILE.unlink()
    except FileNotFoundError:
        pass


def append_key_to_file(path: Path, value: str) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(value + "\n")
    print(f"[+] Đã lưu vào {path.name}")

# ─── Regex & URL extractors ───────────────────────────────────────────────────

def extract_authtool_links(html: str) -> list[str]:
    for pattern in (_RE_AUTHTOOL_1, _RE_AUTHTOOL_2):
        links = list(dict.fromkeys(pattern.findall(html)))
        if links:
            return links
    return []


def extract_result_param(url: str) -> Optional[str]:
    decoded = urllib.parse.unquote(url)
    m = _RE_RESULT.search(decoded)
    return m.group(1) if m else None


def extract_after_url(link: str) -> Optional[str]:
    """
    Chấp nhận mọi loại link (không bắt buộc ontops.link).
    Chỉ cần tách và giải mã phần nằm ngay sau 'url='.
    """
    # 1. Tách qua query string chuẩn
    parsed = urllib.parse.urlparse(link)
    params = urllib.parse.parse_qs(parsed.query)
    if "url" in params and params["url"]:
        return urllib.parse.unquote(params["url"][0]).strip()

    # 2. Tách bằng regex ?url= hoặc &url=
    m = _RE_AFTER_URL.search(link)
    if m:
        return urllib.parse.unquote(m.group(1)).strip()

    # 3. Tách thẳng chuỗi sau 'url=' nếu cấu trúc link đặc biệt
    if "url=" in link:
        raw_after = link.split("url=", 1)[1].split("&")[0]
        return urllib.parse.unquote(raw_after).strip()

    return None


def extract_hash_from_unlock_url(url: str) -> Optional[str]:
    m = _RE_UNLOCK_HASH.search(url)
    return m.group(1) if m else None

# ─── Giao diện & Helpers (Đen trắng hiện đại) ────────────────────────────────

def safe_input(prompt: str = "") -> str:
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return ""


def repeat_menu() -> bool:
    print("\n┌──────────────────────────┐")
    print("│  1. Làm lại              │")
    print("│  2. Quay lại Menu        │")
    print("└──────────────────────────┘")
    return safe_input("Chọn: ") == "1"


def show_value(label: str, value: str, auto_copy: bool = True) -> None:
    term_w = min(shutil.get_terminal_size((44, 20)).columns, 46)
    line   = "─" * max(term_w - 2, 36)
    print(f"\n┌{line}┐")
    print(f"│ {label}")
    print(f"└{line}┘")
    print(f"  {value}")
    print(f"  {line}")

    if auto_copy:
        if copy_to_clipboard(value):
            print("  [✓] Đã tự động copy vào clipboard")
        else:
            print("  [!] Bấm giữ vào dòng trên để copy")


def _clip_and_save(value: str, path: Path, label: str = "KẾT QUẢ") -> None:
    show_value(label, value, auto_copy=True)
    append_key_to_file(path, value)


def _resolve_api_redirect(unlock_url: str) -> Optional[str]:
    """
    Gọi /api/go/<hash>.html và trả về link Location header (chấp nhận mọi domain).
    """
    hash_val = extract_hash_from_unlock_url(unlock_url)
    if not hash_val:
        print("[!] Không thể trích xuất mã hash từ link")
        return None

    api_url = f"https://unlock.tumadam.com/api/go/{hash_val}.html"
    print(f"[*] API URL: {api_url}")

    _, _, api_hdrs = get_page(api_url, follow_redirects=False)
    redirect = api_hdrs.get("Location") or api_hdrs.get("location") or ""
    if not redirect:
        print("[!] Không lấy được link chuyển hướng từ API")
        return None

    print(f"[*] Redirect: {redirect}")
    return redirect

# ─── Core fetch functions ─────────────────────────────────────────────────────

def fetch_key_adr() -> Optional[str]:
    """Lấy 1 key ADR — không giới hạn domain, chỉ tách phần sau 'url='."""
    _, _, hdrs = get_page(
        "https://goctool.vn/GETKEY/tumadam/com.garena.game.kgvn",
        follow_redirects=False,
    )
    redirect_url = hdrs.get("Location") or hdrs.get("location") or ""
    if not redirect_url:
        print("[!] Không lấy được redirect URL ban đầu")
        return None

    api_redirect = _resolve_api_redirect(redirect_url)
    if not api_redirect:
        return None

    target_url = extract_after_url(api_redirect)
    if not target_url:
        print("[!] Không tìm thấy tham số 'url=' trong link chuyển hướng")
        return None

    return target_url


def fetch_key_ipa() -> Optional[str]:
    """Lấy 1 shortlink IPA MOB."""
    url       = "https://honghac86.com/getkey.php?partner=admin"
    post_data = urllib.parse.urlencode({
        "action": "generate_bypass_link", "hwid": "", "customer_name": "Khách iOS",
    }).encode("utf-8")
    headers = {
        **DEFAULT_HEADERS,
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://honghac86.com",
        "Referer": url,
    }
    try:
        req = urllib.request.Request(url, data=post_data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
        payload   = json.loads(raw)
        shortlink = payload.get("shortlink_url", "").replace("\\/", "/")
        return shortlink or None
    except json.JSONDecodeError:
        print("[!] Phản hồi không phải định dạng JSON")
    except Exception as e:
        print(f"[!] Lỗi IPA: {e}")
    return None


def fetch_key_proxy() -> Optional[str]:
    """Lấy 1 link Proxy V4."""
    api_url   = "https://solitudepremium.click/kzmod/key.php"
    post_data = urllib.parse.urlencode({
        "action": "generate_bypass_link", "hwid": "", "customer_name": "Khách Proxy",
    }).encode("utf-8")
    headers = {
        **DEFAULT_HEADERS,
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "text/html,application/xhtml+xml,*/*",
        "Origin": "https://solitudepremium.click",
        "Referer": api_url,
    }
    try:
        req = urllib.request.Request(api_url, data=post_data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        m = _RE_PROXY_URL_1.search(html)
        if m:
            return urllib.parse.unquote(m.group(1))

        m = _RE_PROXY_URL_2.search(html)
        if m:
            return urllib.parse.unquote(m.group(1) or m.group(2))

        m = _RE_PROXY_URL_3.search(html)
        if m:
            return m.group(0)

        print("[!] Không tìm thấy URL trong phản hồi")
    except urllib.error.HTTPError as e:
        print(f"[!] HTTP {e.code}")
    except Exception as e:
        print(f"[!] Lỗi Proxy: {e}")
    return None

# ─── Menus ────────────────────────────────────────────────────────────────────

def menu_getkey_ios() -> None:
    while True:
        print("\n── LẤY KEY iOS ──────────────────────")
        html, _, _ = get_page("https://unlock.tumadam.com/getkeylqm.html")
        if not html:
            print("[!] Không thể tải trang")
            return
        links = extract_authtool_links(html)
        if not links:
            print("[!] Không tìm thấy link authtool.app")
            return
        show_value("LINK AUTHTOOL (Mở trình duyệt dán vào)", links[0])
        if len(links) > 1:
            print("  Link dự phòng:")
            for i, link in enumerate(links[1:], 2):
                print(f"    {i}. {link}")
        safe_input("\nHoàn thành nhiệm vụ xong nhấn Enter để tiếp tục...")
        user_link = safe_input("\n[*] Nhập link unlock.tumadam.com:\n")
        if "unlock.tumadam.com" not in user_link:
            print("[!] Link không hợp lệ!")
            return
        print("[*] Đang xử lý...")
        redirect = _resolve_api_redirect(user_link)
        if redirect is None:
            if not repeat_menu(): return
            continue
        result = extract_result_param(redirect)
        if result:
            _clip_and_save(result, IOS_KEY_FILE, label="KEY iOS")
        else:
            print("[!] Không tìm thấy result param")
        if not repeat_menu(): return


def menu_getkey_adr() -> None:
    while True:
        print("\n── LẤY KEY ADR ──────────────────────")
        result = fetch_key_adr()
        if result:
            _clip_and_save(result, ADR_KEY_FILE, label="KEY ADR")
        if not repeat_menu(): return


def menu_ipa_mob() -> None:
    while True:
        print("\n── IPA MOB ──────────────────────────")
        result = fetch_key_ipa()
        if result:
            _clip_and_save(result, ADR_KEY_FILE, label="SHORTLINK IPA MOB")
        else:
            print("[!] Không lấy được link")
        if not repeat_menu(): return


def menu_proxy_v4() -> None:
    while True:
        print("\n── PROXY V4 ─────────────────────────")
        result = fetch_key_proxy()
        if result:
            _clip_and_save(result, PROXY_KEY_FILE, label="LINK PROXY V4")
        if not repeat_menu(): return

# ─── Tà đạo: Batch tốc độ cao ─────────────────────────────────────────────────

_BATCH_TYPES: dict[str, tuple] = {
    "1": ("iOS",      None,            IOS_KEY_FILE,   "KEY iOS"),
    "2": ("ADR",      fetch_key_adr,   ADR_KEY_FILE,   "KEY ADR"),
    "3": ("IPA MOB",  fetch_key_ipa,   ADR_KEY_FILE,   "SHORTLINK IPA MOB"),
    "4": ("PROXY V4", fetch_key_proxy, PROXY_KEY_FILE, "LINK PROXY V4"),
}


def _batch_run_auto(name: str, fetch_fn, save_file: Path,
                    label: str, count: int, delay: float) -> list[str]:
    results: list[str] = []

    if delay <= 0 and count > 1:
        workers = min(4, count)
        print(f"  [*] Đang lấy {count} key {name} ({workers} luồng song song)...")
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(fetch_fn): i for i in range(1, count + 1)}
            for fut in as_completed(futures):
                idx = futures[fut]
                try:
                    res = fut.result()
                except Exception:
                    res = None
                if res:
                    results.append(res)
                    print(f"  [✓] [{len(results)}/{count}] {res}")
                else:
                    print(f"  [!] Lần {idx} thất bại")
        if results:
            with save_file.open("a", encoding="utf-8") as f:
                f.write("\n".join(results) + "\n")
            print(f"  [+] Đã lưu {len(results)} key vào {save_file.name}")
        return results

    for i in range(1, count + 1):
        print(f"\n  [{i}/{count}] Đang lấy {name}...")
        result = fetch_fn()
        if result:
            show_value(f"{label} [{i}/{count}]", result, auto_copy=True)
            append_key_to_file(save_file, result)
            results.append(result)
        else:
            print(f"  [!] Lần {i} thất bại")
        if i < count and delay > 0:
            time.sleep(delay)
    return results


def _batch_run_ios(count: int) -> list[str]:
    results: list[str] = []
    for i in range(1, count + 1):
        print(f"\n── iOS [{i}/{count}] (Mở trình duyệt) ──────")
        html, _, _ = get_page("https://unlock.tumadam.com/getkeylqm.html")
        if not html:
            print("  [!] Không tải được trang, bỏ qua")
            continue
        links = extract_authtool_links(html)
        if not links:
            print("  [!] Không tìm thấy link authtool")
            continue
        show_value("LINK AUTHTOOL", links[0], auto_copy=True)
        safe_input("  Hoàn thành nhiệm vụ -> nhấn Enter...")
        user_link = safe_input("  Nhập link unlock.tumadam.com: ")
        if "unlock.tumadam.com" not in user_link:
            print("  [!] Link không hợp lệ, bỏ qua")
            continue
        redirect = _resolve_api_redirect(user_link)
        if redirect:
            result = extract_result_param(redirect)
            if result:
                show_value(f"KEY iOS [{i}/{count}]", result, auto_copy=True)
                append_key_to_file(IOS_KEY_FILE, result)
                results.append(result)
                continue
        print("  [!] Không lấy được key iOS lần này")
    return results


def menu_tadao() -> None:
    while True:
        print("\n┌──────────────────────────────────┐")
        print("│  TÀ ĐẠO — LẤY KEY HÀNG LOẠT      │")
        print("├──────────────────────────────────┤")
        for k, (name, *_) in _BATCH_TYPES.items():
            print(f"│  {k}. {name:<29}│")
        print("│  5. Tất cả cùng lúc              │")
        print("└──────────────────────────────────┘")

        choice = safe_input("Chọn loại key: ")
        if choice not in _BATCH_TYPES and choice != "5":
            print("[!] Lựa chọn không hợp lệ")
            continue

        try:
            count = int(safe_input("Số lượng mỗi loại: "))
            if count <= 0:
                raise ValueError
        except ValueError:
            print("[!] Số lượng không hợp lệ")
            continue

        delay = 0.0
        try:
            d = safe_input("Delay giữa request (giây, Enter = 0): ")
            if d:
                delay = float(d)
        except ValueError:
            pass

        jobs = list(_BATCH_TYPES.values()) if choice == "5" else [_BATCH_TYPES[choice]]
        summary: list[tuple[str, int, int]] = []
        all_fetched_keys: list[str] = []

        for name, fetch_fn, save_file, label in jobs:
            print(f"\n── Đang xử lý: {name} (x{count}) ────────────")
            if fetch_fn is None:
                batch_keys = _batch_run_ios(count)
            else:
                batch_keys = _batch_run_auto(name, fetch_fn, save_file, label, count, delay)
            summary.append((name, len(batch_keys), count))
            all_fetched_keys.extend(batch_keys)

        print("\n┌──────────────────────────────────┐")
        print("│  TỔNG KẾT                        │")
        print("├──────────────────────────────────┤")
        total_ok = 0
        for name, ok, total in summary:
            print(f"│  {name:<12} : {ok}/{total:<16}│")
            total_ok += ok
        print("├──────────────────────────────────┤")
        print(f"│  Tổng thành công: {total_ok:<15}│")
        print("└──────────────────────────────────┘")

        if all_fetched_keys and copy_to_clipboard("\n".join(all_fetched_keys)):
            print(f"  [✓] Đã tự động copy gộp {len(all_fetched_keys)} key mới vào clipboard")

        if not repeat_menu(): return

# ─── Xuất key ────────────────────────────────────────────────────────────────

_EXPORT_FILES: dict[str, tuple[str, Path]] = {
    "1": ("iOS",      IOS_KEY_FILE),
    "2": ("ADR",      ADR_KEY_FILE),
    "3": ("Proxy V4", PROXY_KEY_FILE),
    "4": ("ios.txt",  BASE_DIR / "ios.txt"),
    "5": ("adr.txt",  BASE_DIR / "adr.txt"),
}


def _read_clean_lines(path: Path) -> list[str]:
    try:
        return [l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    except FileNotFoundError:
        return []


def menu_export() -> None:
    while True:
        print("\n┌──────────────────────────────────┐")
        print("│  XUẤT KEY & QUẢN LÝ FILE         │")
        print("├──────────────────────────────────┤")

        cached_lines: dict[str, list[str]] = {}
        for k, (name, path) in _EXPORT_FILES.items():
            lines = _read_clean_lines(path)
            cached_lines[k] = lines
            print(f"│  {k}. {name:<14} ({len(lines)} key){'':<7}│")

        print("│  6. Xuất tất cả ra 1 file        │")
        print("│  7. Reset — Xóa toàn bộ file     │")
        print("└──────────────────────────────────┘")

        choice = safe_input("Chọn: ")

        if choice in _EXPORT_FILES:
            name, path = _EXPORT_FILES[choice]
            lines = cached_lines[choice]
            if not lines:
                print(f"[!] File {path.name} trống hoặc chưa có key")
                if not repeat_menu(): return
                continue

            print(f"\n── {name} ({len(lines)} key) ──────────────────")
            for i, line in enumerate(lines, 1):
                print(f"  [{i:>2}] {line}")

            all_text = "\n".join(lines)
            print("─" * 38)
            if copy_to_clipboard(all_text):
                print(f"  [✓] Đã tự động copy tất cả ({len(lines)} dòng) vào clipboard")
            else:
                print("  [!] Bấm giữ dòng key để copy thủ công")

            sel = safe_input("\n[?] Nhập dòng muốn copy riêng (VD: 1,3 hoặc 2-5, Enter = giữ tất cả): ")
            if sel:
                idxs = parse_line_selection(sel, len(lines))
                if idxs:
                    picked = [lines[i] for i in idxs]
                    if copy_to_clipboard("\n".join(picked)):
                        print(f"  [✓] Đã copy {len(picked)} dòng ({', '.join(str(i+1) for i in idxs)}) vào clipboard")
                else:
                    print("  [!] Số dòng không hợp lệ, vẫn giữ toàn bộ trong clipboard.")

        elif choice == "6":
            out_path = BASE_DIR / "all_keys_export.txt"
            raw_keys_only: list[str] = []
            with out_path.open("w", encoding="utf-8") as out:
                for k, (name, _) in _EXPORT_FILES.items():
                    lines = cached_lines[k]
                    if not lines:
                        continue
                    out.write(f"# ── {name} ({len(lines)} key) ──\n")
                    for line in lines:
                        out.write(line + "\n")
                        raw_keys_only.append(line)
                    out.write("\n")
            total = len(raw_keys_only)
            print(f"\n[+] Đã xuất {total} key -> {out_path.name}")
            if raw_keys_only and copy_to_clipboard("\n".join(raw_keys_only)):
                print(f"[✓] Đã copy toàn bộ {total} key vào clipboard")

        elif choice == "7":
            confirm = safe_input("\n[!] Xác nhận xóa TẤT CẢ file key? (Gõ YES để xóa): ")
            if confirm.upper() != "YES":
                print("[~] Đã huỷ thao tác xóa")
            else:
                deleted = 0
                targets = {p for _, p in _EXPORT_FILES.values()} | {
                    BASE_DIR / "all_keys_export.txt",
                    BASE_DIR / "ios.txt",
                    BASE_DIR / "adr.txt",
                }
                for path in targets:
                    try:
                        path.unlink()
                        print(f"  [-] Đã xóa {path.name}")
                        deleted += 1
                    except FileNotFoundError:
                        pass
                print(f"\n[+] Hoàn tất — đã xóa {deleted} file")

        else:
            print("[!] Lựa chọn không hợp lệ")

        if not repeat_menu(): return

# ─── Entry point & Giao diện chính ───────────────────────────────────────────

_MENU_ACTIONS = {
    "1": menu_getkey_ios,
    "2": menu_getkey_adr,
    "3": menu_proxy_v4,
    "4": menu_ipa_mob,
    "5": menu_tadao,
    "6": menu_export,
}


def _show_header() -> None:
    os_info = get_os_device_name()
    w = max(len(os_info) + 18, 42)
    line = "─" * w
    print(f"\n┌{line}┐")
    print(f"│  KEY MANAGER TOOL{'':<{w - 19}}│")
    print(f"│  Liên hệ mua key: @m.hieuu5{'':<{w - 29}}│")
    print(f"├{line}┤")
    print(f"│  Hệ điều hành: {os_info:<{w - 17}}│")
    print(f"└{line}┘")


def _show_login_success(msg: str) -> None:
    print("\n┌──────────────────────────────────────────┐")
    print("│  TRẠNG THÁI : ĐĂNG NHẬP THÀNH CÔNG       │")
    if msg:
        print("├──────────────────────────────────────────┤")
        print(f"│  Thông báo  : {msg}")
    print("└──────────────────────────────────────────┘")


def _show_key_expired() -> None:
    print("\n┌──────────────────────────────────────────┐")
    print("│  TRẠNG THÁI : KEY KHÔNG HỢP LỆ / HẾT HẠN │")
    print("│  Liên hệ    : @m.hieuu5                  │")
    print("└──────────────────────────────────────────┘\n")


def main() -> None:
    _show_header()

    saved = load_saved_key()
    if saved:
        print(f"[*] Đang kiểm tra key đã lưu: {saved}")
        ok, msg = verify_key(saved)
        if ok:
            _show_login_success(msg)
        else:
            clear_saved_key()
            _show_key_expired()
            saved = None

    while not saved:
        key = safe_input("Nhập key đăng nhập: ")
        if not key:
            continue
        ok, msg = verify_key(key)
        if ok:
            _show_login_success(msg)
            save_key(key)
            saved = key
        else:
            _show_key_expired()

    while True:
        print("\n┌──────────────────────────────────────────┐")
        print(f"│  Hệ điều hành: {get_os_device_name():<26}│")
        print("├──────────────────────────────────────────┤")
        print("│  1. Lấy key iOS                          │")
        print("│  2. Lấy key ADR                          │")
        print("│  3. Proxy V4                             │")
        print("│  4. IPA MOB                              │")
        print("│  5. Tà đạo (Batch lấy nhanh)             │")
        print("│  6. Xuất key & Chọn dòng copy            │")
        print("│  7. Đăng xuất                            │")
        print("└──────────────────────────────────────────┘")
        choice = safe_input("Chọn chức năng: ")
        if not choice:
            return

        if choice == "7":
            if safe_input("Xác nhận đăng xuất? (Gõ YES): ").upper() == "YES":
                clear_saved_key()
                print("[+] Đã đăng xuất và xóa key lưu trên máy.")
                return
            print("[~] Đã huỷ đăng xuất.")
            continue

        action = _MENU_ACTIONS.get(choice)
        if action:
            action()
        else:
            print("[!] Lựa chọn không hợp lệ")


if __name__ == "__main__":
    main()
