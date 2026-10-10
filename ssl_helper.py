"""
Friday SSL & Mobile Connectivity Helper
สร้างใบรับรองความปลอดภัย SSL (Self-signed) อัตโนมัติ เพื่อให้โทรศัพท์มือถือ (Android/iOS)
สามารถเข้าใช้งานไมโครโฟน, การคุยด้วยเสียงแบบ Real-time, และติดตั้ง PWA ได้ 100%
"""

import os
import sys
import socket
import datetime
import ipaddress

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

def get_local_ip() -> str:
    """ดึง IP Address ของเครื่องคอมพิวเตอร์ในวงแลน / Wi-Fi"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def ensure_ssl_certificates(base_dir: str = None) -> tuple:
    """
    ตรวจสอบและสร้างไฟล์ ssl_cert.pem และ ssl_key.pem อัตโนมัติ
    คืนค่า (cert_path, key_path)
    """
    if not base_dir:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
    cert_path = os.path.join(base_dir, "ssl_cert.pem")
    key_path = os.path.join(base_dir, "ssl_key.pem")
    
    # หากมีไฟล์อยู่แล้ว ตรวจสอบว่าใช้งานได้
    if os.path.exists(cert_path) and os.path.exists(key_path):
        return cert_path, key_path
        
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        local_ip = get_local_ip()
        print(f"[*] Generating local SSL certificate for IP: {local_ip}...")
        
        # 1. สร้าง RSA Private Key
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        
        # 2. ตั้งชื่อ Subject และ Issuer
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "TH"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Friday AI Assistant"),
            x509.NameAttribute(NameOID.COMMON_NAME, local_ip),
        ])
        
        # 3. กำหนด SANs (Subject Alternative Names) รองรับทั้ง localhost, 127.0.0.1, และ Local IP
        san_list = [
            x509.DNSName("localhost"),
            x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
        ]
        try:
            san_list.append(x509.IPAddress(ipaddress.ip_address(local_ip)))
        except Exception:
            pass

        now = datetime.datetime.now(datetime.timezone.utc)
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + datetime.timedelta(days=730))  # 2 ปี
            .add_extension(x509.SubjectAlternativeName(san_list), critical=False)
            .sign(key, hashes.SHA256())
        )
        
        # บันทึก Key
        with open(key_path, "wb") as f:
            f.write(key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ))
            
        # บันทึก Cert
        with open(cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
            
        print(f"[+] SSL certificate generated: {cert_path}")
        return cert_path, key_path
    except Exception as e:
        print(f"[-] Failed to generate SSL certificate: {e}")
        return None, None

if __name__ == "__main__":
    c, k = ensure_ssl_certificates()
    print("Cert:", c)
    print("Key:", k)
