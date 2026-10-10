@echo off
chcp 65001 > nul
title F.R.I.D.A.Y. Desktop Application

echo ================================================================
echo    🚀 F.R.I.D.A.Y. - NATIVE DESKTOP APPLICATION 🖥️
echo ================================================================
echo.
echo กำลังเปิด F.R.I.D.A.Y. ในรูปแบบ Desktop App (หน้าต่างโปรแกรมอิสระ)...
echo.

python desktop_app.py

if errorlevel 1 (
    echo.
    echo [แจ้งเตือน] ไม่สามารถเปิดหน้าต่างโปรแกรมได้ กำลังเปิดผ่านเบราว์เซอร์ปกติแทน...
    start http://127.0.0.1:8000
    python -m uvicorn app:app --host 0.0.0.0 --port 8000
)

pause
