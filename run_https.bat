@echo off
chcp 65001 > nul
title Friday AI Bot - HTTPS Voice Mode for Mobile

echo ========================================================
echo   F.R.I.D.A.Y. - HTTPS Server (Mobile Voice Ready)
echo ========================================================
echo.

cd /d "%~dp0"

set "PATH=C:\Users\ASUS\AppData\Local\Python\bin;C:\Users\ASUS\AppData\Local\Python\pythoncore-3.14-64;C:\Users\ASUS\AppData\Local\Python\pythoncore-3.14-64\Scripts;%PATH%"

python -c "from ssl_helper import ensure_ssl_certificates; ensure_ssl_certificates()"
python get_mobile_link.py

echo [*] Starting Friday HTTPS Server on port 8443...
python -m uvicorn app:app --host 0.0.0.0 --port 8443 --ssl-keyfile ssl_key.pem --ssl-certfile ssl_cert.pem --reload
pause
