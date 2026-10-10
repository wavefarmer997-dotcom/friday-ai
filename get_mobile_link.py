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
    
    apk_url = f"http://{ip}:8000/download/Friday-AI.apk"
    print("📱 ดาวน์โหลดแอป Android แท้ (.apk) ติดตั้งลงมือถือโดยตรง:")
    print(f"👉 {apk_url}")
    print("   (หรือผ่าน GitHub: https://github.com/wavefarmer997-dotcom/friday-ai/releases/latest)\n")

    print("[📷 สแกน QR Code นี้ด้วยกล้องมือถือเพื่อเข้าใช้งานทันที]:\n")
    qr = qrcode.QRCode(box_size=1, border=1)
    qr.add_data(http_url)
    qr.print_ascii(invert=True)

    print("\n" + "=" * 64)
    print("💡 วิธีใช้งานแอป Friday บนมือถือ Android:")
    print("----------------------------------------------------------------")
    print("✨ แนะนำที่สุด (แอป Android แท้):")
    print(f"   - เปิดลิงก์: {apk_url} บนมือถือเพื่อดาวน์โหลด Friday-AI.apk")
    print("   - แตะติดตั้งไฟล์ APK ลงเครื่อง จะได้แอป Friday AI ใช้งานเต็มจอ")
    print("   - ไมโครโฟนและเสียงคุยสดใช้งานได้ 100% ทันทีโดยไม่ต้องเปิดเบราว์เซอร์!")
    print("\n🌐 หากเข้าใช้งานผ่านเว็บเบราว์เซอร์มือถือ:")
    print(f"   - เข้าผ่าน HTTP: {http_url}")
    print("=" * 64 + "\n")

if __name__ == "__main__":
    print_mobile_banner()
