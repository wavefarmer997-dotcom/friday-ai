"""
Friday Mobile Real-time Connector
สร้าง QR Code และลิงก์สำหรับเชื่อมต่อใช้งานบนมือถือ (Android & iOS) แบบเรียลไทม์
พร้อมคำแนะนำสำหรับเปิดใช้งานไมโครโฟนและการคุยด้วยเสียง 100%
"""

import sys
import os

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

import qrcode
from ssl_helper import get_local_ip, ensure_ssl_certificates

def print_mobile_banner():
    ip = get_local_ip()
    http_url = f"http://{ip}:8000"
    https_url = f"https://{ip}:8443"

    cert_path, key_path = ensure_ssl_certificates()

    print("=" * 64)
    print("    🚀 F.R.I.D.A.Y. AI - MOBILE REAL-TIME CONNECTOR 📱")
    print("=" * 64)
    print(f"\n[📡 IP เครื่องของคุณในวง Wi-Fi]: {ip}\n")
    print("🌐 ลิงก์เข้าใช้งานหลัก (HTTP ปกติ):")
    print(f"👉 {http_url}\n")
    if cert_path and os.path.exists(cert_path):
        print("🔒 ลิงก์ปลอดภัยสำหรับคุยด้วยเสียง/เปิดไมค์ (HTTPS):")
        print(f"👉 {https_url}\n")
    
    print("[📷 สแกน QR Code นี้ด้วยกล้องมือถือเพื่อเข้าใช้งานทันที]:\n")
    qr = qrcode.QRCode(box_size=1, border=1)
    qr.add_data(http_url)
    qr.print_ascii(invert=True)

    print("\n" + "=" * 64)
    print("💡 วิธีทำให้ไมโครโฟน & การคุยด้วยเสียงใช้งานได้ 100% บนมือถือ:")
    print("----------------------------------------------------------------")
    print("1. บน Google Chrome (Android):")
    print(f"   - เปิดลิงก์: {http_url}")
    print("   - เปิดแท็บใหม่พิมพ์: chrome://flags")
    print("   - ค้นหา: Insecure origins treated as secure")
    print(f"   - ใส่: {http_url} แล้วเลือก Enabled > กด Relaunch")
    print("   - ไมค์และการคุยด้วยเสียงสดจะทำงานได้เต็มประสิทธิภาพทันที!")
    print("\n2. หรือเปิดผ่าน HTTPS:")
    print(f"   - เข้า {https_url} (กด Advanced > Proceed)")
    print("\n3. ติดตั้งเป็นแอปเต็มหน้าจอ (PWA):")
    print("   - แตะเมนู 3 จุด (⋮) ใน Chrome > 'เพิ่มลงในหน้าจอหลัก'")
    print("=" * 64 + "\n")

if __name__ == "__main__":
    print_mobile_banner()
