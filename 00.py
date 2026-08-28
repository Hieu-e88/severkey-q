from urllib.parse import urlencode
import base64
from pystyle import *
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
from urllib3.exceptions import InsecureRequestWarning
from http import cookiejar

#-----[MÀU VÀ BIẾN]-----#
trang = "\033[1;37m"
xanh_la = "\033[1;32m"
xanh_duong = "\033[1;34m"
do = "\033[1;31m"
vang = "\033[1;33m"
tim = "\033[1;35m"
dac_biet = "\033[32;5;245m\033[1m\033[38;5;39m"
kt_code = "</>"

#-----[BẮT ĐẦU]-----#
banner = f"""
\033[1;34m╔═════════════════════════════════════════════════════════════════╗
\033[1;32m║                                                                 ║
\033[1;31m║                             hieune                              ║
\033[1;33m║                                                                 ║
\033[1;34m╠═════════════════════════════════════════════════════════════════╣
\033[1;32m║➢ Author   : crack - Tool                                        ║
\033[1;36m║➢ hi                 ║
\033[1;31m║➣ hi                  ║
\033[1;33m║➣ hi               ║
\033[1;34m╚═════════════════════════════════════════════════════════════════╝\033[0m"""

class BlockCookies(cookiejar.CookiePolicy):
    return_ok = set_ok = domain_return_ok = path_return_ok = lambda self, *args, **kwargs: False
    netscape = True
    rfc2965 = hide_cookie2 = False

requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
ssl._create_default_https_context = ssl._create_unverified_context

r = requests.Session()
r.cookies.set_policy(BlockCookies())

	



__domains = ["api22-core-c-useast1a.tiktokv.com", "api19-core-c-useast1a.tiktokv.com",
             "api16-core-c-useast1a.tiktokv.com", "api21-core-c-useast1a.tiktokv.com"]
__devices = ["SM-G9900", "SM-A136U1", "SM-M225FV", "SM-E426B", "SM-M526BR", "SM-M326B", "SM-A528B",
             "SM-F711B", "SM-F926B", "SM-A037G", "SM-A225F", "SM-M325FV", "SM-A226B", "SM-M426B",
             "SM-A525F", "SM-N976N"]
__versions = ["190303", "190205", "190204", "190103", "180904", "180804", "180803", "180802", "270204"]

class Gorgon:
    def __init__(self, params: str, data: str, cookies: str, unix: int) -> None:
        self.unix = unix
        self.params = params
        self.data = data
        self.cookies = cookies
    def hash(self, data: str) -> str:
        try: _hash = str(hashlib.md5(data.encode()).hexdigest())
        except Exception: _hash = str(hashlib.md5(data).hexdigest())
        return _hash
    def get_base_string(self) -> str:
        base_str = self.hash(self.params)
        base_str = base_str + self.hash(self.data) if self.data else base_str + str('0'*32)
        base_str = base_str + self.hash(self.cookies) if self.cookies else base_str + str('0'*32)
        return base_str
    def get_value(self) -> json:
        base_str = self.get_base_string()
        return self.encrypt(base_str)
    def encrypt(self, data: str) -> json:
        unix = self.unix; len_val = 20; key = [223,119,185,64,185,155,132,131,209,185,203,209,247,194,185,133,195,208,251,195]; param_list = []
        for i in range(0, 12, 4):
            temp = data[8*i:8*(i+1)]
            for j in range(4): H = int(temp[j*2:(j+1)*2], 16); param_list.append(H)
        param_list.extend([0, 6, 11, 28]); H = int(hex(unix), 16); param_list.append((H & 4278190080) >> 24); param_list.append((H & 16711680) >> 16); param_list.append((H & 65280) >> 8); param_list.append((H & 255) >> 0); eor_result_list = []
        for (A, B) in zip(param_list, key): eor_result_list.append(A ^ B)
        for i in range(len_val):
            C = self.reverse(eor_result_list[i]); D = eor_result_list[(i+1)%len_val]; E = C ^ D; F = self.rbit_algorithm(E); H = (F ^ 4294967295 ^ len_val) & 255; eor_result_list[i] = H
        result = ''
        for param in eor_result_list: result += self.hex_string(param)
        return {'X-Gorgon': '0404b0d30000' + result, 'X-Khronos': str(unix)}
    def rbit_algorithm(self, num):
        result = ''; tmp_string = bin(num)[2:]
        while len(tmp_string) < 8: tmp_string = '0' + tmp_string
        for i in range(0, 8): result = result + tmp_string[7-i]
        return int(result, 2)
    def hex_string(self, num):
        tmp_string = hex(num)[2:]
        if len(tmp_string) < 2: tmp_string = '0' + tmp_string
        return tmp_string
    def reverse(self, num):
        tmp_string = self.hex_string(num)
        return int(tmp_string[1:] + tmp_string[:1], 16)

def send(__device_id, __install_id, cdid, openudid):
    global reqs, _lock, success, fails
    for x in range(10):
        try:
            version = random.choice(__versions)
            params = urlencode(
                {
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
                }
            )
            payload = f"item_id={__aweme_id}&play_delta=1"
            sig = Gorgon(params=params, cookies=None, data=payload, unix=int(time.time())).get_value()

            response = r.post(
                url=("https://" + random.choice(__domains) + "/aweme/v1/aweme/stats/?" + params),
                data=payload,
                headers={
                    'cookie': 'sessionid=90c38a59d8076ea0fbc01c8643efbe47',
                    'x-gorgon': sig['X-Gorgon'],
                    'x-khronos': sig['X-Khronos'],
                    'user-agent': 'com.zhiliaoapp.musically/2022405030 (Linux; U; Android 12; vi_VN; SM-G9900; Build/TP1A.220624.014; Cronet/58.0.2991.0)',
                    'content-type': 'application/x-www-form-urlencoded'
                },
                verify=False
            )
            reqs += 1
            try:
                if response.json().get('status_code') == 0:
                    with _lock:
                        success += 1
                        print(f'{do}[{vang}crack by hieune{do}] {do}[{xanh_la}THÀNH CÔNG {do}] {do}{xanh_duong}+: {trang}{success}{do} View')
                else:
                    fails += 1
            except:
                fails += 1
                continue
        except Exception:
            pass

if __name__ == "__main__":
    os.system("cls" if os.name == "nt" else "clear")
    print(banner)
    
    # Nhập thẳng Link Video TikTok
    try:
        link = input(f'{do}[{trang}{kt_code}{do}] {xanh_la} LINK VIDEO TikTok: {trang}')
        print(f'{trang}- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -')
        __aweme_id = str(
            re.findall(r"(\d{18,19})", link)[0]
            if len(re.findall(r"(\d{18,19})", link)) == 1
            else re.findall(
                r"(\d{18,19})",
                requests.head(link, allow_redirects=True, timeout=5).url
            )[0]
        )
    except Exception:
        exit(f"{do}[{trang}{kt_code}{do}] {do}INVALID LINK")
    
    _lock = threading.Lock()
    reqs = 0
    success = 0
    fails = 0

    # Chạy tool tăng view trực tiếp với luồng tự động
    while True:
        if threading.active_count() < 50:
            did = str(random.randint(1000000000000000000, 9999999999999999999))
            iid = str(random.randint(1000000000000000000, 9999999999999999999))
            cdid = "00000000-0000-0000-0000-000000000000"
            openudid = "0000000000000000"
            threading.Thread(target=send, args=[did, iid, cdid, openudid]).start()
        time.sleep(0.01)

