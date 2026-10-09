# -*- coding: utf-8 -*-
"""
Công cụ mã hóa/giải mã Python — 50 tầng + ký tự lạ
"""
import os, re, sys, zlib, base64, random, hashlib
from pathlib import Path

LAYERS = 50

# ── Ký tự lạ chèn vào data (visual noise, KHÔNG phải identifier) ──────────────
_NOISE = (
    "꠰꠱꠲꠳꠴꠵꠶꠷꠸꠹"    # Sylheti Nagri digits
    "ᕀᕁᕂᕃᕄᕅᕆᕇᕈᕉ"    # UCAS extensions
    "᠐᠑᠒᠓᠔᠕᠖᠗᠘᠙"    # Mongolian digits
    "꩐꩑꩒꩓꩔꩕꩖꩗꩘꩙"    # Cham digits
    "𝄞𝄟𝄠𝄡𝄢𝄣𝄤𝄥𝄦"     # Musical symbols
    "ꔀꔁꔂꔃꔄꔅꔆꔇꔈꔉ"    # Vai syllables
    "ꁰꁱꁲꁳꁴꁵꁶꁷꁸꁹ"    # Yi radicals
)
_NOISE_SET = set(_NOISE)

# ── Tên biến cho wrapper: Cherokee + Ethiopic (valid Python identifiers) ───────
_V = [
    "ᏓᏔᏕ","ᏖᏗᏘ","ᏙᏚᏛ","ᏜᏝᏞ","ᏟᏠᏡ",
    "ᏢᏣᏤ","ᏥᏦᏧ","ᏨᏩᏪ","ᏫᏬᏭ","ᏮᏯᏰ",
    "ሀሁሂ","ሃሄህ","ሆሇለ","ሉሊሌ","ሎሏሐ",
    "ሑሒሓ","ሔሕሖ","ሗመሙ","ሚማሜ","ምሞሟ",
]

# ── Key derivation ─────────────────────────────────────────────────────────────
def _key(pwd: str, layer: int) -> bytes:
    return hashlib.sha256(f"{pwd}|L{layer}|obf".encode()).digest()

# ── Primitives ─────────────────────────────────────────────────────────────────
def _xor(data: bytes, k: bytes) -> bytes:
    return bytes(b ^ k[i % len(k)] for i, b in enumerate(data))

def _rot(data: bytes, n: int) -> bytes:
    return bytes((b + n) % 256 for b in data)

def _unrot(data: bytes, n: int) -> bytes:
    return bytes((b - n) % 256 for b in data)

def _shuffle(data: bytes, seed: int) -> bytes:
    perm = list(range(len(data)))
    random.Random(seed).shuffle(perm)
    return bytes(data[perm[i]] for i in range(len(data)))

def _unshuffle(data: bytes, seed: int) -> bytes:
    perm = list(range(len(data)))
    random.Random(seed).shuffle(perm)
    out = bytearray(len(data))
    for i, p in enumerate(perm):
        out[p] = data[i]
    return bytes(out)

# ── Per-layer ──────────────────────────────────────────────────────────────────
def _enc_layer(data: bytes, pwd: str, layer: int) -> bytes:
    k    = _key(pwd, layer)
    seed = int.from_bytes(k[:8], 'big')
    op   = layer % 6
    if op == 0: return _xor(data, k)
    if op == 1: return zlib.compress(data, 9)
    if op == 2: return base64.b85encode(data)
    if op == 3: return _rot(data, (layer % 251) + 1)
    if op == 4: return _shuffle(data, seed)
    if op == 5: return _xor(bytes(reversed(data)), k)
    return data

def _dec_layer(data: bytes, pwd: str, layer: int) -> bytes:
    k    = _key(pwd, layer)
    seed = int.from_bytes(k[:8], 'big')
    op   = layer % 6
    if op == 0: return _xor(data, k)
    if op == 1: return zlib.decompress(data)
    if op == 2: return base64.b85decode(data)
    if op == 3: return _unrot(data, (layer % 251) + 1)
    if op == 4: return _unshuffle(data, seed)
    if op == 5: return bytes(reversed(_xor(data, k)))
    return data

def _encode_all(data: bytes, pwd: str) -> bytes:
    for i in range(LAYERS):
        data = _enc_layer(data, pwd, i)
    return data

def _decode_all(data: bytes, pwd: str) -> bytes:
    for i in range(LAYERS - 1, -1, -1):
        data = _dec_layer(data, pwd, i)
    return data

# ── Noise ──────────────────────────────────────────────────────────────────────
def _inject_noise(s: str, pwd: str) -> str:
    rng  = random.Random(hashlib.md5(pwd.encode()).hexdigest())
    pool = list(_NOISE)
    out  = []
    for c in s:
        out.append(c)
        if rng.random() < 0.10:
            out.append(rng.choice(pool))
        if rng.random() < 0.04:
            out.extend(rng.choices(pool, k=rng.randint(1, 3)))
    return ''.join(out)

def _strip_noise(s: str) -> str:
    return ''.join(c for c in s if c not in _NOISE_SET)

# ── Wrapper tự giải mã ─────────────────────────────────────────────────────────
def _make_wrapper(noisy_b85: str, pwd: str) -> str:
    v = _V
    junk_a = _NOISE[:28]
    junk_b = _NOISE[28:56][::-1]
    return (
        f"# -*- coding: utf-8 -*-\n"
        f"# {junk_a}ᕃ꩒ꁴꔅ𝄡꠸ᕇ꩗ꁹꔀ𝄦꠳᠕꩒ᕄꁵꔆ𝄢꠹᠒꩓ᕅꁶꔇ𝄣꠴᠖꩔ᕆꁷꔈ𝄤꠵᠗꩕ᕇꁸꔉ𝄥\n"
        f"# {junk_b}꠰᠑꩑ᕀꁰꔀ𝄞꠶᠒꩒ᕁꁱꔁ𝄟꠷᠓꩓ᕂꁲꔂ𝄠꠸᠔꩔ᕃꁳꔃ𝄡꠹᠕꩕ᕄꁴꔄ𝄢\n"
        f"import zlib as {v[0]},base64 as {v[1]},random as {v[2]},hashlib as {v[3]}\n"
        f"{v[4]}={repr(noisy_b85)}\n"
        f"{v[5]}={repr(pwd)}\n"
        f"{v[6]}=set({repr(_NOISE)})\n"
        f"{v[7]}={LAYERS}\n"
        f"def {v[8]}(p,n):return {v[3]}.sha256(f'{{p}}|L{{n}}|obf'.encode()).digest()\n"
        f"def {v[9]}(d,k):return bytes(b^k[i%len(k)]for i,b in enumerate(d))\n"
        f"def {v[10]}(d,s):\n"
        f" p=list(range(len(d)));{v[2]}.Random(s).shuffle(p)\n"
        f" o=bytearray(len(d))\n"
        f" for i,x in enumerate(p):o[x]=d[i]\n"
        f" return bytes(o)\n"
        f"def {v[11]}(d,p,n):\n"
        f" k={v[8]}(p,n);s=int.from_bytes(k[:8],'big');o=n%6\n"
        f" if o==0:return {v[9]}(d,k)\n"
        f" if o==1:return {v[0]}.decompress(d)\n"
        f" if o==2:return {v[1]}.b85decode(d)\n"
        f" if o==3:return bytes((b-(n%251)-1)%256 for b in d)\n"
        f" if o==4:return {v[10]}(d,s)\n"
        f" if o==5:return bytes(reversed({v[9]}(d,k)))\n"
        f" return d\n"
        f"{v[12]}=''.join(c for c in {v[4]} if c not in {v[6]})\n"
        f"{v[13]}={v[1]}.b85decode({v[12]}.encode())\n"
        f"for {v[14]} in range({v[7]}-1,-1,-1):{v[13]}={v[11]}({v[13]},{v[5]},{v[14]})\n"
        f"exec({v[13]}.decode('utf-8'))\n"
    )

# ── Public API ─────────────────────────────────────────────────────────────────
def encode_file(src: str, dst: str, pwd: str) -> None:
    print(f"[*] Đang mã hóa {LAYERS} tầng...")
    raw   = Path(src).read_bytes()
    enc   = _encode_all(raw, pwd)
    b85   = base64.b85encode(enc).decode('ascii')
    noisy = _inject_noise(b85, pwd)
    code  = _make_wrapper(noisy, pwd)
    Path(dst).write_text(code, encoding='utf-8')
    print(f"[+] Xong! {src} ({len(raw)}B) → {dst} ({Path(dst).stat().st_size}B)")
    print(f"[i] Mật khẩu  : {pwd}")
    print(f"[i] Chạy thử  : python {dst}")

def decode_file(src: str, dst: str, pwd: str) -> None:
    print(f"[*] Đang giải mã {LAYERS} tầng...")
    text = Path(src).read_text(encoding='utf-8')
    # Chuỗi dài nhất trong file = data mã hóa
    hits = re.findall(r"'([^']{100,})'|\"([^\"]{100,})\"", text)
    if not hits:
        print("[!] Không tìm thấy dữ liệu")
        return
    noisy = max((a or b for a, b in hits), key=len)
    clean = _strip_noise(noisy)
    try:
        data = _decode_all(base64.b85decode(clean.encode()), pwd)
        Path(dst).write_bytes(data)
        print(f"[+] Giải mã xong → {dst}")
    except Exception as e:
        print(f"[!] Lỗi (sai mật khẩu?): {e}")

# ── CLI ────────────────────────────────────────────────────────────────────────
def safe_input(p=""):
    try: return input(p).strip()
    except EOFError: return ""

def main():
    print("╔══════════════════════════════════════════╗")
    print("║   🔐 Python Obfuscator — 50 tầng mã hóa  ║")
    print("╠══════════════════════════════════════════╣")
    print("║  1. Mã hóa file                          ║")
    print("║  2. Giải mã file                         ║")
    print("╚══════════════════════════════════════════╝")
    ch = safe_input("Chọn: ")

    if ch == "1":
        src = safe_input("File nguồn (.py): ")
        if not src or not Path(src).exists():
            print("[!] File không tồn tại"); return
        dst = safe_input(f"File đầu ra (Enter = {Path(src).stem}_enc.py): ")
        if not dst: dst = Path(src).stem + "_enc.py"
        pwd = safe_input("Mật khẩu (Enter = tự động): ")
        if not pwd:
            pwd = hashlib.sha256(Path(src).read_bytes()).hexdigest()[:16]
            print(f"[i] Mật khẩu tự động: {pwd}")
        encode_file(src, dst, pwd)

    elif ch == "2":
        src = safe_input("File mã hóa: ")
        if not src or not Path(src).exists():
            print("[!] File không tồn tại"); return
        dst = safe_input(f"File đầu ra (Enter = {Path(src).stem}_dec.py): ")
        if not dst: dst = Path(src).stem + "_dec.py"
        pwd = safe_input("Mật khẩu: ")
        if not pwd: print("[!] Cần nhập mật khẩu"); return
        decode_file(src, dst, pwd)
    else:
        print("[!] Không hợp lệ")

if __name__ == "__main__":
    main()

