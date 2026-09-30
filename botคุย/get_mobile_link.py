"""
Friday Mobile Connector
สร้าง QR Code และลิงก์สำหรับเปิดใช้งานบนมือถือ Android ทันที
"""

import socket
import sys
import os

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

import qrcode

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def print_qr_banner(url):
    print("=" * 60)
    print("       FRIDAY AI - ANDROID & MOBILE CONNECTOR")
    print("=" * 60)
    print(f"\n[*] Link for Mobile (Same Wi-Fi network):\n")
    print(f"👉 {url}\n")
    print("[*] Scan QR Code with Android camera or Chrome to open:\n")
    
    qr = qrcode.QRCode()
    qr.add_data(url)
    qr.print_ascii(invert=True)
    
    print("\n" + "=" * 60)
    print("How to Install as App on Android:")
    print("1. Open the link above in Google Chrome on your Android phone")
    print("2. Tap 'Install App' button on top, or Chrome menu (3 dots) > 'Add to Home screen'")
    print("3. Friday AI app will be installed on your Home screen!")
    print("=" * 60)

if __name__ == "__main__":
    ip = get_local_ip()
    port = 8000
    mobile_url = f"http://{ip}:{port}"
    print_qr_banner(mobile_url)
