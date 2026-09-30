"""
Friday Chatbot Backend Server
FastAPI Web Server + WebSocket Real-time Streaming + SQLite Memory Management
"""

import os
import json
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from memory_engine import MemoryEngine
from ai_service import AIService

app = FastAPI(title="Friday - Real-time AI Assistant with Memory")

# เริ่มต้นระบบความจำและบริการ AI
memory_engine = MemoryEngine()
ai_service = AIService(memory_engine)

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

@app.get("/")
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
    return {"status": "success", "id": mem_id, "memories": memory_engine.get_all_memories()}

@app.delete("/api/memories/{memory_id}")
async def delete_memory(memory_id: int):
    deleted = memory_engine.delete_memory(memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"status": "success", "deleted_id": memory_id, "memories": memory_engine.get_all_memories()}

@app.post("/api/memories/clear")
async def clear_memories():
    memory_engine.clear_all_memories()
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

@app.get("/api/settings")
async def get_settings():
    raw_key = memory_engine.get_setting("api_key", "")
    masked_key = (raw_key[:4] + "..." + raw_key[-4:]) if len(raw_key) > 8 else ("*" * len(raw_key))
    pol_key = memory_engine.get_setting("pollinations_api_key", "")
    masked_pol_key = (pol_key[:4] + "..." + pol_key[-4:]) if len(pol_key) > 8 else ("*" * len(pol_key))
    return {
        "api_provider": memory_engine.get_setting("api_provider", "gemini"),
        "has_api_key": bool(raw_key.strip()),
        "masked_api_key": masked_key,
        "model_name": memory_engine.get_setting("model_name", "gemini-2.5-flash"),
        "openai_base_url": memory_engine.get_setting("openai_base_url", "https://api.openai.com/v1"),
        "temperature": memory_engine.get_setting("temperature", "0.7"),
        "custom_persona": memory_engine.get_setting("custom_persona", ""),
        "has_pollinations_key": bool(pol_key.strip()),
        "masked_pollinations_key": masked_pol_key
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
    return {"status": "success"}

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
                
                if not user_message:
                    continue

                # 1. บันทึกข้อความผู้ใช้ลงประวัติการสนทนา
                memory_engine.add_message(session_id, "user", user_message)

                # 2. วิเคราะห์ข้อมูลสำคัญเพื่อจดจำอัตโนมัติ (Auto-Extract Fact)
                new_memories = memory_engine.auto_extract_and_remember(user_message)
                if new_memories:
                    # ส่งแจ้งเตือนว่าบอทบันทึกความจำใหม่แล้ว
                    await websocket.send_json({
                        "type": "memory_learned",
                        "items": new_memories,
                        "all_memories": memory_engine.get_all_memories()
                    })

                # 3. เริ่มต้นสตรีมมิ่งคำตอบกลับแบบ Real-time
                await websocket.send_json({"type": "stream_start"})
                
                full_reply = ""
                async for chunk in ai_service.generate_stream(user_message, session_id):
                    full_reply += chunk
                    await websocket.send_json({
                        "type": "stream_chunk",
                        "chunk": chunk
                    })
                
                # 4. บันทึกคำตอบของบอทลงประวัติการสนทนา
                memory_engine.add_message(session_id, "assistant", full_reply)

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
