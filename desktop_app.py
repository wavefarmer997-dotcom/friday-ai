import os
import sys
import threading
import time
import urllib.request
import webview

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8000
SERVER_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"

def is_server_running():
    try:
        with urllib.request.urlopen(f"{SERVER_URL}/api/settings", timeout=1.5) as res:
            return res.status == 200
    except Exception:
        return False

def start_backend():
    import uvicorn
    import app
    uvicorn.run(app.app, host="0.0.0.0", port=SERVER_PORT, log_level="warning")

def main():
    # 1. Check if backend is already running (e.g. from service or run.bat)
    if not is_server_running():
        print("Starting Friday Backend Engine...")
        t = threading.Thread(target=start_backend, daemon=True)
        t.start()
        # Wait up to 5 seconds for server to be responsive
        for _ in range(25):
            if is_server_running():
                break
            time.sleep(0.2)

    # 2. Launch Native Desktop Window (using WebView2)
    icon_path = os.path.join(os.path.dirname(__file__), "static", "icons", "icon-512.png")
    if not os.path.exists(icon_path):
        icon_path = None

    print("Launching F.R.I.D.A.Y. Desktop Application...")
    window = webview.create_window(
        title="F.R.I.D.A.Y. - AI Digital Partner",
        url=SERVER_URL,
        width=1280,
        height=850,
        min_size=(900, 600),
        resizable=True,
        fullscreen=False,
        easy_drag=False,
        text_select=True,
        confirm_close=False
    )
    
    webview.start(debug=False)

if __name__ == "__main__":
    main()
