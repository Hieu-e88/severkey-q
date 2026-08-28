from urllib.parse import urlencode
import base64
import os
import sys
import ssl
import re
import time
import random
import threading
import requests
import hashlib
import json
from datetime import datetime, timedelta
from urllib3.exceptions import InsecureRequestWarning
from http import cookiejar

class BlockCookies(cookiejar.CookiePolicy):
    return_ok = set_ok = domain_return_ok = path_return_ok = lambda self, *args, **kwargs: False
    netscape = True
    rfc2965 = hide_cookie2 = False

requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
ssl._create_default_https_context = ssl._create_unverified_context

r = requests.Session()
r.cookies.set_policy(BlockCookies())

__domains = [
    "api22-core-c-useast1a.tiktokv.com",
    "api19-core-c-useast1a.tiktokv.com",
    "api16-core-c-useast1a.tiktokv.com",
    "api21-core-c-useast1a.tiktokv.com"
]
__devices = [
    "SM-G9900", "SM-A136U1", "SM-M225FV", "SM-E426B", "SM-M526BR", 
    "SM-M326B", "SM-A528B", "SM-F711B", "SM-F926B", "SM-A037G", 
    "SM-A225F", "SM-M325FV", "SM-A226B", "SM-M426B", "SM-A525F", "SM-N976N"
]
__versions = ["190303", "190205", "190204", "190103", "180904", "180804", "180803", "180802", "270204"]

class Gorgon:
    def __init__(self, params: str, data: str, cookies: str, unix: int) -> None:
        self.unix = unix
        self.params = params
        self.data = data
        self.cookies = cookies

    def hash(self, data: str) -> str:
        try:
            _hash = str(hashlib.md5(data.encode()).hexdigest())
        except Exception:
            _hash = str(hashlib.md5(data).hexdigest())
        return _hash

    def get_base_string(self) -> str:
        base_str = self.hash(self.params)
        base_str = base_str + self.hash(self.data) if self.data else base_str + str('0' * 32)
        base_str = base_str + self.hash(self.cookies) if self.cookies else base_str + str('0' * 32)
        return base_str

    def get_value(self) -> json:
        base_str = self.get_base_string()
        return self.encrypt(base_str)

    def encrypt(self, data: str) -> json:
        unix = self.unix
        len_val = 20
        key = [223, 119, 185, 64, 185, 155, 132, 131, 209, 185, 203, 209, 247, 194, 185, 133, 195, 208, 251, 195]
        param_list = []
        for i in range(0, 12, 4):
            temp = data[8 * i:8 * (i + 1)]
            for j in range(4):
                H = int(temp[j * 2:(j + 1) * 2], 16)
                param_list.append(H)
        param_list.extend([0, 6, 11, 28])
        H = int(hex(unix), 16)
        param_list.append((H & 4278190080) >> 24)
        param_list.append((H & 16711680) >> 16)
        param_list.append((H & 65280) >> 8)
        param_list.append((H & 255) >> 0)
        eor_result_list = []
        for (A, B) in zip(param_list, key):
            eor_result_list.append(A ^ B)
        for i in range(len_val):
            C = self.reverse(eor_result_list[i])
            D = eor_result_list[(i + 1) % len_val]
            E = C ^ D
            F = self.rbit_algorithm(E)
            H = (F ^ 4294967295 ^ len_val) & 255
            eor_result_list[i] = H
        result = ''
        for param in eor_result_list:
            result += self.hex_string(param)
        return {'X-Gorgon': '0404b0d30000' + result, 'X-Khronos': str(unix)}

    def rbit_algorithm(self, num):
        result = ''
        tmp_string = bin(num)[2:]
        while len(tmp_string) < 8:
            tmp_string = '0' + tmp_string
        for i in range(0, 8):
            result = result + tmp_string[7 - i]
        return int(result, 2)

    def hex_string(self, num):
        tmp_string = hex(num)[2:]
        if len(tmp_string) < 2:
            tmp_string = '0' + tmp_string
        return tmp_string

    def reverse(self, num):
        tmp_string = self.hex_string(num)
        return int(tmp_string[1:] + tmp_string[:1], 16)

def verify_key():
    os.system("cls" if os.name == "nt" else "clear")
    print("""
    ████████╗██╗██╗  ██╗████████╗██╗  ██╗
    ╚══██╔══╝██║██║ ██╔╝╚══██╔══╝██║  ██║
       ██║   ██║█████═╝    ██║   ███████║
       ██║   ██║██╔═██╗    ██║   ██╔══██║
       ██║   ██║██║  ██╗   ██║   ██║  ██║
       ╚═╝   ╚═╝╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝
    """)
    
    # Kiểm tra file lưu key cục bộ (nếu đã kích hoạt trước đó)
    saved_key_file = "activated_key.json"
    if os.path.exists(saved_key_file):
        try:
            with open(saved_key_file, "r") as f:
                data_saved = json.load(f)
                if datetime.now().timestamp() < data_saved["expiry"]:
                    print(f"[+] Key đã được lưu từ trước. Còn hạn sử dụng.")
                    return True
        except:
            pass

    user_key = input("Nhập KEY bản quyền của bạn: ").strip()
    if not user_key:
        sys.exit("[-] Bạn chưa nhập key!")

    try:
        url_key = "https://github.com/Hieu-e88/severkey-q/raw/refs/heads/main/Key_tc.txt"
        response = requests.get(url_key, timeout=10)
        if not response.ok:
            sys.exit("[-] Không thể kết nối đến máy chủ chứa Key!")
        
        lines = response.text.splitlines()
        found = False
        days = 0

        for line in lines:
            line = line.strip()
            if not line or "." not in line:
                continue
            # Tách key và số ngày ở sau dấu chấm cuối cùng hoặc theo định dạng key.days
            parts = line.rsplit(".", 1)
            if len(parts) == 2:
                k_val, d_val = parts[0].strip(), parts[1].strip()
                if k_val == user_key:
                    found = True
                    days = float(d_val)
                    break
        
        if found:
            expiry_time = datetime.now() + timedelta(days=days)
            with open(saved_key_file, "w") as f:
                json.dump({"key": user_key, "expiry": expiry_time.timestamp()}, f)
            print(f"[+] Kích hoạt thành công! Key có thời hạn {days} ngày.")
            time.sleep(1.5)
        else:
            sys.exit("[-] Key không tồn tại hoặc không hợp lệ!")
    except Exception as e:
        sys.exit(f"[-] Lỗi xác thực key: {e}")

def send(__device_id, __install_id, cdid, openudid):
    global success, _lock
    for x in range(10):
        try:
            version = random.choice(__versions)
            params = urlencode({
                "os_api": "25",
                "device_type": random.choice(__devices),
                "ssmix": "a",
                "manifest_version_code": version,
                "dpi": "240",
                "region": "VN",
                "carrier_region": "VN",
                "app_name": "musically_go",
                "version_name": "27.2.4",
                "timezone_offset": "-28800",
                "ab_version": "27.2.4",
                "ac2": "wifi",
                "ac": "wifi",
                "app_type": "normal",
                "channel": "googleplay",
                "update_version_code": version,
                "device_platform": "android",
                "iid": __install_id,
                "build_number": "27.2.4",
                "locale": "vi",
                "op_region": "VN",
                "version_code": version,
                "timezone_name": "Asia/Ho_Chi_Minh",
                "device_id": __device_id,
                "sys_region": "VN",
                "app_language": "vi",
                "resolution": "720*1280",
                "device_brand": "samsung",
                "language": "vi",
                "os_version": "7.1.2",
                "aid": "1340"
            })
            payload = f"item_id={__aweme_id}&play_delta=1"
            sig = Gorgon(params=params, cookies=None, data=payload, unix=int(time.time())).get_value()
            proxy = random.choice(proxies) if config['proxy']['use-proxy'] else ""

            response = r.post(
                url="https://" + random.choice(__domains) + "/aweme/v1/aweme/stats/?" + params,
                data=payload,
                headers={
                    'cookie': 'sessionid=90c38a59d8076ea0fbc01c8643efbe47',
                    'x-gorgon': sig['X-Gorgon'],
                    'x-khronos': sig['X-Khronos'],
                    'user-agent': 'com.zhiliaoapp.musically/2022405030 (Linux; U; Android 12; vi_VN; SM-G9900; Build/TP1A.220624.014; Cronet/58.0.2991.0)',
                    'content-type': 'application/x-www-form-urlencoded'
                },
                verify=False,
                proxies={"http": proxy_format + proxy, "https": proxy_format + proxy} if config['proxy']['use-proxy'] else {}
            )
            if response.json().get('status_code') == 0:
                with _lock:
                    success += 1
                    print(f"THÀNH CÔNG: +{success} View", end="\r")
        except Exception:
            pass

def fetch_proxies():
    url_list = [
        "https://raw.githubusercontent.com/yemixzy/proxy-list/main/proxy-list/data.txt",
        "https://raw.githubusercontent.com/UptimerBot/proxy-list/main/proxies/http.txt",
        "https://raw.githubusercontent.com/rdavydov/proxy-list/main/proxies/http.txt",
        "https://raw.githubusercontent.com/rdavydov/proxy-list/main/proxies/socks4.txt",
        "https://raw.githubusercontent.com/rdavydov/proxy-list/main/proxies/socks5.txt"
    ]
    for url in url_list:
        try:
            response = requests.get(url=url, timeout=5)
            if response.ok:
                with open("proxies.txt", "a+") as f:
                    f.write(response.text)
        except Exception:
            pass

if __name__ == "__main__":
    # Thực hiện check key trước tiên
    verify_key()

    if not os.path.exists('devices.txt'):
        with open('devices.txt', 'w') as f:
            f.write("did:iid:cdid:openudid")
    if not os.path.exists('config.json'):
        with open('config.json', 'w') as f:
            json.dump({"proxy": {"use-proxy": False, "proxy-type": "http", "proxyscrape": True, "credential": "", "auth": False}}, f)

    with open('devices.txt', 'r') as f:
        devices = f.read().splitlines()

    with open('config.json', 'r') as f:
        config = json.load(f)

    if config["proxy"]['proxyscrape']:
        fetch_proxies()

    proxy_format = f'{config["proxy"]["proxy-type"].lower()}://{config["proxy"]["credential"]+"@" if config["proxy"]["auth"] else ""}' if config['proxy']['use-proxy'] else ''
    proxies = []
    if config['proxy']['use-proxy'] and os.path.exists('proxies.txt'):
        with open('proxies.txt', 'r') as f:
            proxies = f.read().splitlines()

    # Xóa sạch màn hình console sau khi nhập key thành công
    os.system("cls" if os.name == "nt" else "clear")

    print("""
    ████████╗██╗██╗  ██╗████████╗██╗  ██╗
    ╚══██╔══╝██║██║ ██╔╝╚══██╔══╝██║  ██║
       ██║   ██║█████═╝    ██║   ███████║
       ██║   ██║██╔═██╗    ██║   ██╔══██║
       ██║   ██║██║  ██╗   ██║   ██║  ██║
       ╚═╝   ╚═╝╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝
    """)

    try:
        link = input("Nhập LINK VIDEO TikTok: ")
        __aweme_id = str(
            re.findall(r"(\d{18,19})", link)[0]
            if len(re.findall(r"(\d{18,19})", link)) == 1
            else re.findall(
                r"(\d{18,19})",
                requests.head(link, allow_redirects=True, timeout=5).url
            )[0]
        )
    except Exception:
        sys.exit("Link không hợp lệ!")

    _lock = threading.Lock()
    success = 0

    while True:
        if threading.active_count() < 50:
            device = random.choice(devices)
            try:
                did, iid, cdid, openudid = device.split(':')
                threading.Thread(target=send, args=[did, iid, cdid, openudid]).start()
            except Exception:
                continue
        time.sleep(0.01)

