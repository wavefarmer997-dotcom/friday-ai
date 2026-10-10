"""
Friday Chatbot Backend Server
FastAPI Web Server + WebSocket Real-time Streaming + SQLite Memory Management
"""

import os
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from memory_engine import MemoryEngine
from ai_service import AIService
from obsidian_sync import ObsidianSync
from video_project_service import VideoProjectService
from dotenv import load_dotenv

ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(ENV_PATH)

def persist_settings_to_env(engine: MemoryEngine):
    """บันทึกคอนฟิกปัจจุบันลงไฟล์ .env ถาวร เพื่อสำรองข้อมูลและแชร์กับมือถือ 100%"""
    try:
        keys_to_export = [
            ("API_KEY", engine.get_setting("api_key", "")),
            ("POLLINATIONS_API_KEY", engine.get_setting("pollinations_api_key", "")),
            ("API_PROVIDER", engine.get_setting("api_provider", "openai")),
            ("MODEL_NAME", engine.get_setting("model_name", "qwen/qwen3.8-27b")),
            ("OPENAI_BASE_URL", engine.get_setting("openai_base_url", "https://api.groq.com/openai/v1")),
            ("OBSIDIAN_VAULT_PATH", engine.get_setting("obsidian_vault_path", r"D:\ob\WIKI")),
            ("OBSIDIAN_SYNC_ENABLED", engine.get_setting("obsidian_sync_enabled", "true")),
            ("GITHUB_SYNC_ENABLED", engine.get_setting("github_sync_enabled", "true")),
            ("GITHUB_REMOTE_URL", engine.get_setting("github_remote_url", "")),
        ]
        lines = [
            "# Friday AI Environment Configuration & API Keys",
            "# ไฟล์นี้บันทึกและซิงค์ API Key ของเครื่องหลักกับโทรศัพท์มือถืออัตโนมัติ",
            ""
        ]
        for env_k, val in keys_to_export:
            if val:
                lines.append(f"{env_k}={val}")
        with open(ENV_PATH, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except Exception as e:
        print(f"[ENV] Failed to persist .env: {e}")

def sync_env_and_db(engine: MemoryEngine):
    """ซิงค์ค่าระหว่างไฟล์ .env และ SQLite Database เพื่อให้ API Key ไม่สูญหายและแชร์กับมือถือ 100%"""
    env_map = {
        "api_key": os.getenv("API_KEY"),
        "pollinations_api_key": os.getenv("POLLINATIONS_API_KEY"),
        "api_provider": os.getenv("API_PROVIDER"),
        "model_name": os.getenv("MODEL_NAME"),
        "openai_base_url": os.getenv("OPENAI_BASE_URL"),
        "obsidian_vault_path": os.getenv("OBSIDIAN_VAULT_PATH"),
        "github_remote_url": os.getenv("GITHUB_REMOTE_URL"),
    }
    for k, v in env_map.items():
        if v and not engine.get_setting(k):
            engine.set_setting(k, v)
    persist_settings_to_env(engine)

app = FastAPI(title="Friday - Real-time AI Assistant with Memory")

# เริ่มต้นระบบความจำ บริการ AI บริการสร้างโปรเจกต์วิดีโอ และระบบซิงค์ Obsidian Vault
memory_engine = MemoryEngine()
sync_env_and_db(memory_engine)
ai_service = AIService(memory_engine)
video_service = VideoProjectService()

import platform as _platform
_on_cloud = _platform.system() != "Windows"  # บน Render/Linux ปิด Obsidian sync อัตโนมัติ

obsidian_sync = ObsidianSync(
    vault_path=memory_engine.get_setting("obsidian_vault_path", r"D:\ob\WIKI") if not _on_cloud else os.path.join(os.path.dirname(__file__), "obsidian_vault"),
    enabled=False if _on_cloud else (memory_engine.get_setting("obsidian_sync_enabled", "true").lower() in ("true", "1", "yes")),
    github_sync_enabled=False if _on_cloud else (memory_engine.get_setting("github_sync_enabled", "true").lower() in ("true", "1", "yes")),
    github_remote_url=memory_engine.get_setting("github_remote_url", "")
)

# ซิงค์ข้อมูลความจำที่มีอยู่ลง Obsidian ในช่วงเริ่มต้นระบบ
try:
    obsidian_sync.sync_memories(memory_engine.get_all_memories())
except Exception as e:
    print(f"[Obsidian] Initial sync error: {e}")

# ตรวจหาตำแหน่งโฟลเดอร์ static อัตโนมัติ (รองรับทั้ง root และ subfolder)
possible_static_dirs = [
    os.path.join(os.path.dirname(__file__), "static"),
    os.path.join(os.path.dirname(__file__), "botคุย", "static"),
    os.path.join(os.getcwd(), "static"),
    os.path.join(os.getcwd(), "botคุย", "static"),
]
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
for p in possible_static_dirs:
    if os.path.exists(os.path.join(p, "index.html")):
        STATIC_DIR = p
        break

os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "css"), exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "js"), exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.api_route("/", methods=["GET", "HEAD"])
async def serve_index():
    for p in possible_static_dirs:
        index_file = os.path.join(p, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
    return {
        "message": "Friday server is running. UI is initializing...",
        "debug_cwd": os.getcwd(),
        "debug_dirs": os.listdir(os.getcwd()) if os.path.exists(os.getcwd()) else []
    }

@app.api_route("/health", methods=["GET", "HEAD"])
async def health_check():
    return {"status": "ok", "app": "Friday AI"}


# ==================== Natural Female Voice TTS API ====================
from fastapi.responses import Response
import io
import re

@app.get("/api/tts")
async def get_female_speech(text: str):
    try:
        # ลบ Thinking Box, HTML Tags, Markdown Images, Links, Code Blocks
        clean_text = re.sub(r'<details[\s\S]*?</details>', '', text, flags=re.IGNORECASE)
        clean_text = re.sub(r'<div[\s\S]*?</div>', '', clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r'<[^>]+>', '', clean_text)
        clean_text = re.sub(r'!\[.*?\]\(.*?\)', '', clean_text)
        clean_text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', clean_text)
        clean_text = re.sub(r'```[\s\S]*?```', '', clean_text)
        clean_text = re.sub(r'`([^`]+)`', r'\1', clean_text)
        clean_text = re.sub(r'[*_#`~>•|\-]', ' ', clean_text)
        
        # ลบ Emojis และ Unicode Symbols ทุกชนิด
        emoji_pattern = re.compile(
            r'[\U00010000-\U0010ffff]|[\u2600-\u27bf]|[\u2300-\u23ff]|[\u2b50-\u2b55]|[\ufe00-\ufe0f\u200d]',
            flags=re.UNICODE
        )
        clean_text = emoji_pattern.sub('', clean_text)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        
        # รองรับความยาวสูงสุด 3,000 ตัวอักษร
        clean_text = clean_text[:3000].strip()
        if not clean_text:
            return Response(status_code=400)
        
        # 1. ใช้เสียงผู้หญิงไทยระดับ AI Neural (th-TH-PremwadeeNeural) นุ่มนวล สมจริงที่สุด
        try:
            import edge_tts
            communicate = edge_tts.Communicate(clean_text, "th-TH-PremwadeeNeural")
            audio_data = bytearray()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data.extend(chunk["data"])
            if len(audio_data) > 500:
                return Response(content=bytes(audio_data), media_type="audio/mpeg")
        except Exception as edge_err:
            print(f"[EdgeTTS] Fallback: {edge_err}")

        # 2. Fallback สำรองด้วย gTTS
        from gtts import gTTS
        fp = io.BytesIO()
        tts = gTTS(text=clean_text, lang='th')
        tts.write_to_fp(fp)
        fp.seek(0)
        return Response(content=fp.read(), media_type="audio/mpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Image Generation API ====================

class ImageGenRequest(BaseModel):
    prompt: str
    style: Optional[str] = "photorealistic"
    aspect_ratio: Optional[str] = "1:1"
    model: Optional[str] = "flux"

@app.post("/api/generate-image")
async def api_generate_image(item: ImageGenRequest):
    if not item.prompt.strip():
        raise HTTPException(status_code=400, detail="กรุณาระบุ Prompt สำหรับสร้างรูปภาพ")
    try:
        result = await ai_service.generate_image(
            prompt=item.prompt,
            style=item.style or "photorealistic",
            aspect_ratio=item.aspect_ratio or "1:1",
            model=item.model or "turbo"
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/image-proxy")
async def api_image_proxy(url: str):
    """Proxy สำหรับดึงภาพจากภายนอกเพื่อป้องกัน CORS และ Mixed Content ในเบราว์เซอร์"""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
            r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200:
                return Response(content=r.content, media_type=r.headers.get("content-type", "image/jpeg"))
            raise HTTPException(status_code=r.status_code, detail="Remote image fetch failed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Video Project & Editing APIs (CapCut & Premiere Pro) ====================

class VideoPlanRequest(BaseModel):
    prompt: str
    aspect_ratio: Optional[str] = "9:16"
    target_duration: Optional[float] = 30.0

class VideoCreateRequest(BaseModel):
    platform: str  # "capcut", "premiere", or "both"
    project_name: str
    aspect_ratio: Optional[str] = "9:16"
    scenes: List[Dict[str, Any]]
    generate_voiceover: Optional[bool] = True
    voice: Optional[str] = "th-TH-PremwadeeNeural"

class VideoOpenRequest(BaseModel):
    action: str  # "folder", "capcut", "premiere", "alightmotion"
    target_path: Optional[str] = None

@app.get("/api/video/status")
async def get_video_status():
    """ตรวจสอบสถานะของ CapCut, Premiere Pro และ Alight Motion บนเครื่อง"""
    env = video_service.detect_environment()
    capcut_drafts = video_service.list_capcut_drafts()
    prem_projects = video_service.list_premiere_projects()
    am_projects = video_service.list_alightmotion_projects()
    return {
        "status": "ok",
        "environment": env,
        "capcut_draft_count": len(capcut_drafts),
        "premiere_project_count": len(prem_projects),
        "alightmotion_project_count": len(am_projects),
        "alightmotion_count": len(am_projects)
    }

@app.get("/api/video/drafts")
async def get_video_drafts():
    """ดึงรายชื่อโปรเจกต์ CapCut, Premiere Pro และ Alight Motion ในเครื่อง"""
    return {
        "capcut_drafts": video_service.list_capcut_drafts()[:15],
        "premiere_projects": video_service.list_premiere_projects()[:15],
        "alightmotion_projects": video_service.list_alightmotion_projects()[:15]
    }

@app.post("/api/video/plan")
async def plan_video_project(req: VideoPlanRequest):
    """วางโครงสร้างคลิป Storyboard, Scene Timecodes, เสียงพากย์ จาก Prompt"""
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="กรุณาระบุหัวข้อหรือไอเดียคลิป")
    plan = video_service.plan_quick_storyboard(req.prompt, aspect_ratio=req.aspect_ratio or "9:16")
    return plan

@app.post("/api/video/create")
async def create_video_project(req: VideoCreateRequest):
    """สร้างโปรเจกต์ลง CapCut PC, Adobe Premiere Pro และ/หรือ Alight Motion"""
    if not req.project_name.strip():
        raise HTTPException(status_code=400, detail="กรุณาระบุชื่อโปรเจกต์")
    if not req.scenes:
        raise HTTPException(status_code=400, detail="กรุณาระบุอย่างน้อย 1 ฉากสำหรับตัดต่อ")

    results = {}
    plat = req.platform.lower()

    if plat in ("capcut", "both", "all"):
        try:
            cap_res = await video_service.create_capcut_project(
                project_name=req.project_name,
                aspect_ratio=req.aspect_ratio or "9:16",
                scenes=req.scenes,
                generate_voiceover=req.generate_voiceover if req.generate_voiceover is not None else True,
                voice=req.voice or "th-TH-PremwadeeNeural"
            )
            results["capcut"] = cap_res
        except Exception as e:
            results["capcut"] = {"status": "error", "message": str(e)}

    if plat in ("premiere", "both", "all"):
        try:
            prem_res = await video_service.create_premiere_project(
                project_name=req.project_name,
                aspect_ratio=req.aspect_ratio or "16:9",
                scenes=req.scenes,
                generate_voiceover=req.generate_voiceover if req.generate_voiceover is not None else True,
                voice=req.voice or "th-TH-PremwadeeNeural"
            )
            results["premiere"] = prem_res
        except Exception as e:
            results["premiere"] = {"status": "error", "message": str(e)}

    if plat in ("alightmotion", "alight", "all"):
        try:
            am_res = await video_service.create_alight_motion_project(
                project_name=req.project_name,
                aspect_ratio=req.aspect_ratio or "9:16",
                scenes=req.scenes,
                generate_voiceover=req.generate_voiceover if req.generate_voiceover is not None else True,
                voice=req.voice or "th-TH-PremwadeeNeural"
            )
            results["alightmotion"] = am_res
        except Exception as e:
            results["alightmotion"] = {"status": "error", "message": str(e)}

    return {
        "status": "success",
        "platform": req.platform,
        "results": results
    }

@app.get("/api/video/download-alightmotion/{project_name}")
async def download_alight_motion_xml(project_name: str):
    """ดาวน์โหลดไฟล์ Alight Motion Project Package XML สำหรับนำเข้าแอปบนมือถือ/แท็บเล็ต"""
    clean_name = video_service._sanitize_name(project_name)
    xml_path = os.path.join(video_service.base_export_dir, "alightmotion", clean_name, f"{clean_name}.xml")
    if not os.path.exists(xml_path):
        raise HTTPException(status_code=404, detail="ไม่พบไฟล์โปรเจกต์ Alight Motion XML")
    return FileResponse(
        xml_path,
        media_type="application/xml",
        filename=f"{clean_name}.xml",
        headers={"Content-Disposition": f'attachment; filename="{clean_name}.xml"'}
    )

@app.post("/api/video/open")
async def open_video_target(req: VideoOpenRequest):
    """เปิดโฟลเดอร์โปรเจกต์ใน Explorer หรือสั่งเปิด CapCut / Premiere Pro"""
    action = req.action.lower()
    success = False
    msg = ""

    if action == "folder" and req.target_path:
        success = video_service.open_folder(req.target_path)
        msg = "เปิดโฟลเดอร์ใน Windows Explorer แล้ว" if success else "ไม่พบโฟลเดอร์ปลายทาง"
    elif action == "capcut":
        success = video_service.launch_capcut()
        msg = "เปิดโปรแกรม CapCut เรียบร้อยแล้ว" if success else "ไม่พบตัวรันโปรแกรม CapCut"
    elif action == "premiere":
        success = video_service.launch_premiere(req.target_path)
        msg = "เปิดโปรแกรม Adobe Premiere Pro เรียบร้อยแล้ว" if success else "ไม่พบตัวรันโปรแกรม Premiere Pro"
    elif action == "alightmotion":
        am_dir = os.path.join(video_service.base_export_dir, "alightmotion")
        success = video_service.open_folder(req.target_path or am_dir)
        msg = "เปิดโฟลเดอร์โปรเจกต์ Alight Motion เรียบร้อยแล้ว" if success else "ไม่พบโฟลเดอร์ Alight Motion"
    else:
        raise HTTPException(status_code=400, detail="Action ไม่ถูกต้อง")

    return {"status": "success" if success else "failed", "message": msg}

# ==================== REST APIs: Mobile Connectivity ====================

@app.get("/api/mobile/info")
async def get_mobile_info():
    """ดึงข้อมูล IP, Port และ URL สำหรับเชื่อมต่อใช้งานบนมือถือ"""
    from ssl_helper import get_local_ip, ensure_ssl_certificates
    local_ip = get_local_ip()
    cert_path, key_path = ensure_ssl_certificates()
    has_ssl = bool(cert_path and os.path.exists(cert_path) and key_path and os.path.exists(key_path))
    return {
        "local_ip": local_ip,
        "http_port": 8000,
        "http_url": f"http://{local_ip}:8000",
        "https_port": 8443,
        "https_url": f"https://{local_ip}:8443",
        "has_ssl": has_ssl,
        "chrome_flags_url": "chrome://flags/#unsafely-treat-insecure-origin-as-secure"
    }

@app.get("/api/mobile/qr")
async def get_mobile_qr(url: Optional[str] = None):
    """สร้าง QR Code Image (PNG) แบบไดนามิกสำหรับสแกนเข้าใช้งานบนมือถือ"""
    import io
    import qrcode
    from ssl_helper import get_local_ip

    target = url
    if not target:
        local_ip = get_local_ip()
        target = f"http://{local_ip}:8000"

    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(target)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0f172a", back_color="#ffffff")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")

@app.get("/download/Friday-AI.apk")
async def download_friday_apk():
    """เสิร์ฟไฟล์ติดตั้ง Android APK สำหรับติดตั้งลงโทรศัพท์มือถือโดยตรง"""
    from fastapi.responses import RedirectResponse
    possible_paths = [
        os.path.join(os.path.dirname(__file__), "Friday-AI.apk"),
        os.path.join(os.path.dirname(__file__), "static", "downloads", "Friday-AI.apk"),
        os.path.join(os.path.dirname(__file__), "android", "app", "build", "outputs", "apk", "debug", "app-debug.apk"),
        os.path.join(os.path.dirname(__file__), "android", "app", "build", "outputs", "apk", "release", "app-release.apk"),
    ]
    for p in possible_paths:
        if os.path.exists(p):
            return FileResponse(p, media_type="application/vnd.android.package-archive", filename="Friday-AI.apk")
    
    # หากยังไม่มีไฟล์ในเครื่อง ให้พาไปยังหน้า GitHub Releases เพื่อดาวน์โหลด
    return RedirectResponse(url="https://github.com/wavefarmer997-dotcom/friday-ai/releases/latest")

# ==================== REST APIs: Memory Management ====================

class MemoryCreate(BaseModel):
    category: str = "general"
    key_concept: str
    content: str
    importance: int = 3

@app.get("/api/memories")
async def get_memories():
    return {"memories": memory_engine.get_all_memories()}

@app.post("/api/memories")
async def add_memory(item: MemoryCreate):
    mem_id = memory_engine.save_memory(
        category=item.category,
        key_concept=item.key_concept,
        content=item.content,
        importance=item.importance
    )
    all_mems = memory_engine.get_all_memories()
    obsidian_sync.sync_memories(all_mems)
    return {"status": "success", "id": mem_id, "memories": all_mems}

@app.delete("/api/memories/{memory_id}")
async def delete_memory(memory_id: int):
    deleted = memory_engine.delete_memory(memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")
    all_mems = memory_engine.get_all_memories()
    obsidian_sync.sync_memories(all_mems)
    return {"status": "success", "deleted_id": memory_id, "memories": all_mems}

@app.post("/api/memories/clear")
async def clear_memories():
    memory_engine.clear_all_memories()
    obsidian_sync.sync_memories([])
    return {"status": "success", "memories": []}

# ==================== REST APIs: History & Settings ====================

@app.get("/api/history")
async def get_history(session_id: str = "default"):
    history = memory_engine.get_recent_history(session_id=session_id, limit=30)
    return {"history": history}

@app.post("/api/history/clear")
async def clear_history(session_id: str = "default"):
    memory_engine.clear_history(session_id=session_id)
    return {"status": "success"}

class SettingsUpdate(BaseModel):
    api_provider: Optional[str] = None
    api_key: Optional[str] = None
    model_name: Optional[str] = None
    openai_base_url: Optional[str] = None
    temperature: Optional[str] = None
    custom_persona: Optional[str] = None
    pollinations_api_key: Optional[str] = None
    obsidian_sync_enabled: Optional[bool] = None
    obsidian_vault_path: Optional[str] = None
    github_sync_enabled: Optional[bool] = None
    github_remote_url: Optional[str] = None

@app.get("/api/settings")
async def get_settings():
    raw_key = memory_engine.get_setting("api_key", "")
    masked_key = (raw_key[:4] + "..." + raw_key[-4:]) if len(raw_key) > 8 else ("*" * len(raw_key))
    pol_key = memory_engine.get_setting("pollinations_api_key", "")
    masked_pol_key = (pol_key[:4] + "..." + pol_key[-4:]) if len(pol_key) > 8 else ("*" * len(pol_key))
    obs_enabled = memory_engine.get_setting("obsidian_sync_enabled", "true").lower() in ("true", "1", "yes")
    obs_path = memory_engine.get_setting("obsidian_vault_path", r"D:\ob\WIKI")
    gh_enabled = memory_engine.get_setting("github_sync_enabled", "true").lower() in ("true", "1", "yes")
    gh_url = memory_engine.get_setting("github_remote_url", obsidian_sync.get_remote_url())

    git_info = obsidian_sync.get_git_info()

    return {
        "api_provider": memory_engine.get_setting("api_provider", "gemini"),
        "has_api_key": bool(raw_key.strip()),
        "masked_api_key": masked_key,
        "model_name": memory_engine.get_setting("model_name", "gemini-3.8-flash"),
        "openai_base_url": memory_engine.get_setting("openai_base_url", "https://api.openai.com/v1"),
        "temperature": memory_engine.get_setting("temperature", "0.7"),
        "custom_persona": memory_engine.get_setting("custom_persona", ""),
        "has_pollinations_key": bool(pol_key.strip()),
        "masked_pollinations_key": masked_pol_key,
        "obsidian_sync_enabled": obs_enabled,
        "obsidian_vault_path": obs_path,
        "obsidian_available": obsidian_sync.is_available(),
        "github_sync_enabled": gh_enabled,
        "github_remote_url": gh_url,
        "git_info": git_info,
        "api_key_synced": bool(raw_key.strip()),
        "shared_with_mobile": True,
        "saved_to_env": os.path.exists(ENV_PATH)
    }

@app.post("/api/settings")
async def update_settings(settings: SettingsUpdate):
    if settings.api_provider is not None:
        memory_engine.set_setting("api_provider", settings.api_provider)
    if settings.api_key is not None and settings.api_key.strip():
        memory_engine.set_setting("api_key", settings.api_key.strip())
    if settings.model_name is not None:
        memory_engine.set_setting("model_name", settings.model_name)
    if settings.openai_base_url is not None:
        memory_engine.set_setting("openai_base_url", settings.openai_base_url)
    if settings.temperature is not None:
        memory_engine.set_setting("temperature", settings.temperature)
    if settings.custom_persona is not None:
        memory_engine.set_setting("custom_persona", settings.custom_persona)
    if settings.pollinations_api_key is not None and settings.pollinations_api_key.strip():
        memory_engine.set_setting("pollinations_api_key", settings.pollinations_api_key.strip())
    if settings.obsidian_sync_enabled is not None:
        memory_engine.set_setting("obsidian_sync_enabled", "true" if settings.obsidian_sync_enabled else "false")
        obsidian_sync.enabled = settings.obsidian_sync_enabled
    if settings.obsidian_vault_path is not None:
        clean_path = settings.obsidian_vault_path.strip()
        memory_engine.set_setting("obsidian_vault_path", clean_path)
        obsidian_sync.vault_path = clean_path
    if settings.github_sync_enabled is not None:
        memory_engine.set_setting("github_sync_enabled", "true" if settings.github_sync_enabled else "false")
        obsidian_sync.github_sync_enabled = settings.github_sync_enabled
    if settings.github_remote_url is not None:
        clean_gh_url = settings.github_remote_url.strip()
        memory_engine.set_setting("github_remote_url", clean_gh_url)
        obsidian_sync.set_remote_url(clean_gh_url)
    
    # ซิงค์ค่าล่าสุดลง .env ถาวร
    persist_settings_to_env(memory_engine)
    return {"status": "success", "synced_to_env": True, "shared_with_mobile": True}

@app.post("/api/obsidian/sync-now")
async def api_obsidian_sync_now():
    try:
        mems = memory_engine.get_all_memories()
        mem_ok = obsidian_sync.sync_memories(mems)
        return {
            "status": "success" if mem_ok else "failed",
            "vault_path": obsidian_sync.vault_path,
            "is_available": obsidian_sync.is_available(),
            "synced_memories": len(mems)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/obsidian/git-push")
async def api_obsidian_git_push():
    try:
        from datetime import datetime
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        success = obsidian_sync._git_commit_and_push(f"Manual push from Friday UI ({now_str})")
        git_info = obsidian_sync.get_git_info()
        return {
            "status": "success" if success else "failed",
            "message": obsidian_sync.last_git_status,
            "git_info": git_info
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== WebSocket: Real-time Streaming ====================

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    session_id = "default"
    
    try:
        while True:
            data_text = await websocket.receive_text()
            data = json.loads(data_text)
            msg_type = data.get("type", "message")
            
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue
            
            if msg_type == "message":
                user_message = data.get("content", "").strip()
                session_id = data.get("session_id", "default")
                images = data.get("images", [])  # list of {name, mime_type, data}
                attachments = data.get("attachments", [])  # list of {type, name, files, ...}
                
                # หากผู้ใช้ไม่ได้พิมพ์ข้อความมา แต่มีการแนบรูปภาพหรือโฟลเดอร์ ให้ตั้ง prompt อัตโนมัติ
                if not user_message:
                    if images and attachments:
                        user_message = "ช่วยดูและวิเคราะห์รูปภาพรวมถึงโฟลเดอร์ไฟล์ที่แนบมานี้ให้หน่อยค่ะ"
                    elif images:
                        user_message = "ช่วยดูและวิเคราะห์รูปภาพที่แนบมานี้ให้หน่อยค่ะ"
                    elif attachments:
                        user_message = "ช่วยดูโครงสร้างและเนื้อหาไฟล์ในโฟลเดอร์นี้ แล้วสรุป/อธิบายการทำงานให้หน่อยค่ะ"
                    else:
                        continue

                # 1. บันทึกข้อความผู้ใช้ลงประวัติการสนทนา (รวมแท็กบอกแนบไฟล์/รูปเพื่อ Context ในความจำ)
                history_label = user_message
                if images:
                    history_label += f" [📷 แนบ {len(images)} รูปภาพ]"
                if attachments:
                    att_names = ", ".join([a.get("name", "folder") for a in attachments])
                    history_label += f" [📁 แนบ {att_names}]"
                memory_engine.add_message(session_id, "user", history_label)

                # 2. วิเคราะห์ข้อมูลสำคัญเพื่อจดจำอัตโนมัติ (Auto-Extract Fact)
                new_memories = memory_engine.auto_extract_and_remember(user_message)
                if new_memories:
                    # ซิงค์ความจำลง Obsidian Vault ทันที
                    obsidian_sync.sync_memories(memory_engine.get_all_memories())
                    # ส่งแจ้งเตือนว่าบอทบันทึกความจำใหม่แล้ว
                    await websocket.send_json({
                        "type": "memory_learned",
                        "items": new_memories,
                        "all_memories": memory_engine.get_all_memories()
                    })

                # 3. เริ่มต้นสตรีมมิ่งคำตอบกลับแบบ Real-time
                await websocket.send_json({"type": "stream_start"})
                
                full_reply = ""
                async for chunk in ai_service.generate_stream(user_message, session_id, images=images, attachments=attachments):
                    full_reply += chunk
                    await websocket.send_json({
                        "type": "stream_chunk",
                        "chunk": chunk
                    })
                
                # 4. บันทึกคำตอบของบอทลงประวัติการสนทนา
                memory_engine.add_message(session_id, "assistant", full_reply)

                # 4.1 บันทึกบทสนทนาลงใน Obsidian Vault (Chats/YYYY-MM-DD.md) แบบ Real-time ทันที
                obsidian_sync.log_chat_exchange(session_id, history_label, full_reply)

                # 5. สิ้นสุดการสตรีม
                await websocket.send_json({
                    "type": "stream_end",
                    "full_reply": full_reply
                })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
