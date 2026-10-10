@echo off
chcp 65001 > nul
title Friday AI Bot - Assistant

echo ========================================================
echo        F.R.I.D.A.Y. - AI Assistant with Memory
echo ========================================================
echo.

cd /d "%~dp0"

set "PATH=C:\Users\ASUS\AppData\Local\Python\bin;C:\Users\ASUS\AppData\Local\Python\pythoncore-3.14-64;C:\Users\ASUS\AppData\Local\Python\pythoncore-3.14-64\Scripts;%PATH%"

echo [*] Checking dependencies...
python -c "import fastapi, uvicorn" 2>nul
if %errorlevel% neq 0 (
    echo [*] Installing dependencies...
    pip install -r requirements.txt
)

echo [*] Checking SSL for Mobile Voice...
python -c "from ssl_helper import ensure_ssl_certificates; ensure_ssl_certificates()" 2>nul

python get_mobile_link.py

start "" cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:8000"

echo [*] Starting Friday Server on http://0.0.0.0:8000 ...
python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
pause
