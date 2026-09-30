"""
Friday AI Service
โมดูลสำหรับประมวลผลการตอบกลับแบบ Real-time Streaming
- รองรับ Google Gemini API (gemini-2.5-flash, gemini-1.5-flash)
- รองรับ OpenAI / Local Ollama Compatible endpoints
- มี Smart Interactive Fallback Engine สำหรับโต้ตอบและทดสอบระบบความจำได้ทันทีแม้ยังไม่ใส่ API Key
"""

import os
import json
import asyncio
import httpx
import urllib.parse
import random
import re
import base64
from typing import AsyncGenerator, Dict, List, Any
from memory_engine import MemoryEngine

FRIDAY_SYSTEM_PROMPT = """คุณคือ "Friday" (F.R.I.D.A.Y.) ผู้ช่วย AI ส่วนตัวอัจฉริยะระดับสูง
บุคลิกภาพและความสามารถ:
- ฉลาด มีไหวพริบ มีความรู้เชิงลึกรอบด้าน สุภาพ และเป็นกันเองกับผู้ใช้อย่างจริงใจ
- ตอบคำถามอย่างละเอียด ลึกซึ้ง มีโครงสร้างชัดเจน (ใช้ Markdown, หัวข้อ, บูลเล็ต, ตาราง, โค้ด) พร้อมคำอธิบายเหตุผลและข้อเสนอแนะเชิงกลยุทธ์
- เมื่อผู้ใช้ถามคำถามที่ซับซ้อน หรือต้องการการคิดวิเคราะห์เชิงลึก ให้เริ่มต้นคำตอบด้วยกระบวนการคิดในแท็ก:
<details class="thinking-box">
<summary>🧠 กระบวนการคิดวิเคราะห์ของ Friday</summary>

- ระบุประเด็นสำคัญและสมมติฐาน
- วิเคราะห์แง่มุมต่างๆ และข้อมูลที่เกี่ยวข้อง
- สรุปแนวทางคำตอบที่ดีที่สุด

</details>

- มีระบบความจำอัจฉริยะ (Memory System) จดจำชื่อ รสนิยม โปรเจกต์ และข้อมูลส่วนตัวของผู้ใช้ได้อย่างแม่นยำ
- เมื่อผู้ใช้ถามเรื่องที่เคยบันทึกไว้ ให้เชื่อมโยงและนำมาตอบอย่างเป็นธรรมชาติ เสมือนผู้ช่วยที่รู้ใจ

{memories_context}
"""

class AIService:
    def __init__(self, memory_engine: MemoryEngine):
        self.memory = memory_engine

    def build_system_prompt(self, extra_context: str = "") -> str:
        memories_text = self.memory.format_memories_for_prompt()
        custom_persona = self.memory.get_setting("custom_persona", "")
        base_prompt = custom_persona if custom_persona.strip() else FRIDAY_SYSTEM_PROMPT
        prompt = base_prompt.replace("{memories_context}", memories_text)
        if extra_context:
            prompt += f"\n\n{extra_context}"
        return prompt

    def is_image_request(self, text: str) -> tuple[bool, str]:
        """ตรวจสอบว่าผู้ใช้ต้องการให้สร้างรูปภาพหรือไม่ และดึง Prompt ออกมา"""
        clean = text.strip()
        lower = clean.lower()
        
        # คำสั่งแบบ slash: /image, /draw, /img, /pic
        if lower.startswith(("/image", "/draw", "/img", "/pic")):
            parts = clean.split(maxsplit=1)
            prompt = parts[1] if len(parts) > 1 else ""
            return True, prompt
            
        # คีย์เวิร์ดสร้างภาพในภาษาไทย ครอบคลุม "เจน...", "วาด...", "สร้างรูป...", "ขอภาพ..."
        patterns = [
            r'^(?:ช่วย|อยากให้)?\s*(?:วาดรูป|วาดภาพ|สร้างภาพ|สร้างรูป|เจนรูป|gen\s*รูป|เจนภาพ|gen\s*ภาพ|ทำรูป|ทำภาพ|ขอรูป|ขอภาพ|เสกรูป|อยากได้รูป|เจน|gen|วาด|draw)\s*(.+)',
            r'(.+)\s*(?:ช่วยวาดรูปให้หน่อย|ช่วยสร้างภาพให้หน่อย|gen\s*รูปให้ที|วาดให้ดูหน่อย|วาดให้หน่อย|สร้างให้หน่อย|เจนให้หน่อย|วาดที)$',
        ]
        
        for pat in patterns:
            m = re.search(pat, clean, re.IGNORECASE)
            if m:
                prompt = m.group(1).strip()
                prompt = re.sub(r'^(รูป|ภาพ|ตัว|เป็น|ของ)\s*', '', prompt).strip()
                prompt = re.sub(r'^(ให้หน่อย|ให้ที|หน่อย|ที|ของ|เป็น)\s*', '', prompt).strip()
                prompt = re.sub(r'\s*(ให้หน่อย|ให้ที|หน่อย|ที|ด้วยนะ|ด้วย|ครับ|ค่ะ|นะ|จ้า|จ๊ะ)$', '', prompt).strip()
                if prompt and len(prompt) >= 2:
                    return True, prompt
                
        return False, ""

    def is_search_request(self, text: str) -> tuple[bool, str]:
        """ตรวจสอบว่าคำถามต้องการค้นหาข้อมูลสดบนอินเทอร์เน็ตหรือไม่"""
        clean = text.strip()
        lower = clean.lower()
        
        if lower.startswith(("/search", "/web", "ค้นหา", "หาข้อมูล", "เสิร์ช", "เช็คข่าว", "เช็คราคา", "ค้นข้อมูล")):
            parts = clean.split(maxsplit=1)
            query = parts[1] if len(parts) > 1 else clean
            return True, query
            
        live_keywords = [
            "ข่าว", "ล่าสุด", "วันนี้", "เมื่อวาน", "ราคา", "สภาพอากาศ", "อัปเดต", "update",
            "ใครคือ", "นายก", "เลือกตั้ง", "หุ้น", "ทองคำ", "น้ำมัน", "2026", "2025"
        ]
        if any(k in clean for k in live_keywords) and len(clean) >= 4:
            return True, clean
            
        return False, ""

    async def translate_to_english(self, text: str) -> str:
        """แปลข้อความเป็นภาษาอังกฤษเพื่อส่งให้ Diffusion Model สร้างภาพได้คมชัดที่สุด"""
        clean = text.strip()
        if re.match(r'^[a-zA-Z0-9\s,.-_]+$', clean):
            return clean

        # Tier 1: MyMemory Translation API (แม่นยำ รวดเร็ว และไม่มี 429 block)
        try:
            q = urllib.parse.quote(clean)
            url = f"https://api.mymemory.translated.net/get?q={q}&langpair=th|en"
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                if res.status_code == 200:
                    data = res.json()
                    translated = data.get("responseData", {}).get("translatedText", "")
                    if translated and not translated.startswith("MYMEMORY WARNING"):
                        return translated.strip()
        except Exception:
            pass

        # Tier 2: Lingva API
        try:
            q = urllib.parse.quote(clean)
            url = f"https://lingva.ml/api/v1/th/en/{q}"
            async with httpx.AsyncClient(timeout=4.0) as client:
                res = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                if res.status_code == 200:
                    data = res.json()
                    translated = data.get("translation", "")
                    if translated:
                        return translated.strip()
        except Exception:
            pass

        # Tier 3: Keyword mapping fallback
        keyword_map = {
            "แมว": "cat", "สุนัข": "dog", "หมา": "dog", "อวกาศ": "space astronaut",
            "หุ่นยนต์": "robot cyborg", "ไซเบอร์พังก์": "cyberpunk neon", "นีออน": "neon glowing",
            "ซามูไร": "samurai warrior", "มังกร": "dragon", "สาวสวย": "beautiful woman",
            "อนิเมะ": "anime", "เมือง": "futuristic city", "รถ": "futuristic flying car",
            "แฟนตาซี": "fantasy magic", "ป่า": "mystical forest", "ทะเล": "ocean sea"
        }
        translated_words = []
        for th, en in keyword_map.items():
            if th in clean:
                translated_words.append(en)
        if translated_words:
            return ", ".join(translated_words)

        return clean

    async def generate_image(self, prompt: str, style: str = "photorealistic", aspect_ratio: str = "1:1", model: str = "turbo") -> dict:
        """สร้างรูปภาพผ่าน Pollinations.ai (Turbo / Flux.1) หรือ OpenAI DALL-E 3 พร้อมบันทึกภาพลงเครื่องเพื่อความเสถียรสูงสุด"""
        clean_prompt = prompt.strip()
        english_prompt = await self.translate_to_english(clean_prompt)
        
        style_modifiers = {
            "photorealistic": "masterpiece, ultra-realistic photograph, 8k resolution, cinematic lighting, photorealistic, sharp focus, octane render, 35mm lens photography",
            "anime": "anime aesthetic, masterpiece anime artwork, vibrant colors, studio ghibli and makoto shinkai style, highly detailed, expressive",
            "cyberpunk": "cyberpunk style, neon glow, futuristic cityscape, moody atmospheric lighting, high-tech, cinematic 8k, volumetric rays",
            "3d_pixar": "3D Pixar and Disney animation render style, cute, expressive character, 4k 3D digital art, smooth shading, octane render",
            "fantasy": "epic fantasy digital art, ethereal lighting, mystical atmosphere, highly detailed concept art, trending on artstation",
            "watercolor": "beautiful watercolor painting, artistic brush strokes, soft pastel colors, elegant illustration, textured paper"
        }
        
        modifier = style_modifiers.get(style, style_modifiers["photorealistic"])
        enhanced_prompt = f"{english_prompt}, {modifier}"
        
        # ปรับขนาดภาพที่เหมาะสมกับโมเดล ให้โหลดได้รวดเร็วและคมชัด
        dimensions = {
            "1:1": (800, 800),
            "16:9": (1024, 576),
            "9:16": (576, 1024),
            "4:3": (800, 600),
            "3:4": (600, 800)
        }
        width, height = dimensions.get(aspect_ratio, (800, 800))
        
        # ตรวจสอบว่าผู้ใช้เลือก DALL-E 3 และมี OpenAI Key หรือไม่
        api_provider = self.memory.get_setting("api_provider", "")
        api_key = self.memory.get_setting("api_key", "").strip()
        
        if model.lower() in ["dall-e-3", "dalle3", "dall-e"] and api_provider == "openai" and api_key:
            try:
                base_url = self.memory.get_setting("openai_base_url", "https://api.openai.com/v1").rstrip("/")
                dalle_size = "1024x1024"
                if aspect_ratio == "16:9":
                    dalle_size = "1792x1024"
                elif aspect_ratio == "9:16":
                    dalle_size = "1024x1792"
                
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(
                        f"{base_url}/images/generations",
                        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                        json={
                            "model": "dall-e-3",
                            "prompt": enhanced_prompt[:1000],
                            "n": 1,
                            "size": dalle_size,
                            "quality": "standard"
                        }
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        dalle_url = data["data"][0]["url"]
                        return {
                            "status": "success",
                            "image_url": dalle_url,
                            "original_prompt": clean_prompt,
                            "english_prompt": english_prompt,
                            "enhanced_prompt": enhanced_prompt,
                            "style": style,
                            "aspect_ratio": aspect_ratio,
                            "model": "dall-e-3",
                            "seed": random.randint(100000, 9999999)
                        }
            except Exception:
                pass

        # Pollinations.ai (Turbo / Flux) - ใช้งานผ่าน Pollinations API Key เพื่อความเสถียรและเร็วสูงสุด
        polli_key = self.memory.get_setting("pollinations_api_key", "sk_zqNt4xDL8G4AxLWLxactNyRfKZFKGzvL").strip()
        seed = random.randint(100000, 9999999)
        encoded_prompt = urllib.parse.quote(enhanced_prompt)
        polli_model = "flux" if model.lower() in ["flux", "flux_pro", "flux-pro"] else "turbo"
        key_param = f"&key={polli_key}" if polli_key else ""
        remote_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&model={polli_model}&nologo=true&seed={seed}{key_param}"
        
        # บันทึกไฟล์ภาพลงเครื่อง (Local Cache) ใน static/generated_images
        local_filename = f"friday_{seed}.jpg"
        local_dir = os.path.join(os.path.dirname(__file__), "static", "generated_images")
        os.makedirs(local_dir, exist_ok=True)
        local_filepath = os.path.join(local_dir, local_filename)
        local_url = f"/static/generated_images/{local_filename}"

        # 1. ลองใช้ Pollinations Official API (v1/images/generations) พร้อมคีย์ของผู้ใช้ (เสถียร & คุณภาพสูง คืนค่า Base64)
        if polli_key:
            try:
                gen_url = "https://gen.pollinations.ai/v1/images/generations"
                async with httpx.AsyncClient(timeout=45.0) as client:
                    resp = await client.post(
                        gen_url,
                        headers={
                            "Authorization": f"Bearer {polli_key}",
                            "Content-Type": "application/json",
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) FridayAssistant/2.5"
                        },
                        json={
                            "prompt": enhanced_prompt,
                            "model": "flux",
                            "width": width,
                            "height": height,
                            "seed": seed,
                            "response_format": "b64_json"
                        }
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        b64_str = data.get("data", [{}])[0].get("b64_json", "")
                        if b64_str:
                            img_bytes = base64.b64decode(b64_str)
                            with open(local_filepath, "wb") as f:
                                f.write(img_bytes)
                            return {
                                "status": "success",
                                "image_url": local_url,
                                "remote_url": local_url,
                                "original_prompt": clean_prompt,
                                "english_prompt": english_prompt,
                                "enhanced_prompt": enhanced_prompt,
                                "style": style,
                                "aspect_ratio": aspect_ratio,
                                "model": "flux",
                                "seed": seed
                            }
            except Exception as e:
                print(f"[ImageGen] v1 API fallback: {e}")

        final_url = local_url
        req_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        if polli_key:
            req_headers["Authorization"] = f"Bearer {polli_key}"

        try:
            # ดึงภาพจากเซิร์ฟเวอร์ Pollinations มาเก็บไว้ในเครื่อง
            async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
                r = await client.get(remote_url, headers=req_headers)
                if r.status_code == 200 and len(r.content) > 1000:
                    with open(local_filepath, "wb") as f:
                        f.write(r.content)
                    final_url = local_url
                else:
                    final_url = f"/api/image-proxy?url={urllib.parse.quote(remote_url)}"
        except Exception:
            # หากดาวน์โหลดชั่วคราวเกินเวลา ให้ใช้ proxy endpoint เป็นหลัก
            final_url = f"/api/image-proxy?url={urllib.parse.quote(remote_url)}"
        
        return {
            "status": "success",
            "image_url": final_url,
            "remote_url": remote_url,
            "original_prompt": clean_prompt,
            "english_prompt": english_prompt,
            "enhanced_prompt": enhanced_prompt,
            "style": style,
            "aspect_ratio": aspect_ratio,
            "model": polli_model,
            "seed": seed
        }

    async def generate_stream(self, message: str, session_id: str = "default") -> AsyncGenerator[str, None]:
        """
        สร้างคำตอบแบบ Real-time streaming
        คืนค่า chunk ข้อความทีละ token
        """
        # 1. ตรวจสอบว่าผู้ใช้ต้องการสร้างรูปภาพหรือไม่
        is_img, img_prompt = self.is_image_request(message)
        if is_img and img_prompt:
            yield "🎨 รับทราบค่ะ! Friday กำลังออกแบบและสร้างภาพให้คุณสักครู่นะคะ... ✨\n\n"
            try:
                img_data = await self.generate_image(img_prompt, model="turbo")
                img_url = img_data["image_url"]
                enh_prompt = img_data.get("english_prompt", img_prompt)
                seed = img_data.get("seed", 12345)
                
                yield f"![{img_prompt}]({img_url})\n\n"
                yield f"<div class=\"image-action-bar\">\n"
                yield f"  <a href=\"{img_url}\" target=\"_blank\" class=\"image-btn download-btn\" download=\"friday_{seed}.jpg\" onclick=\"window.downloadImageDirect(event, '{img_url}', 'friday_{seed}.jpg')\"><i class=\"fa-solid fa-download\"></i> ดาวน์โหลดรูปภาพ</a>\n"
                yield f"  <button type=\"button\" onclick=\"window.openImageLightbox('{img_url}', '{img_prompt}')\" class=\"image-btn zoom-btn\"><i class=\"fa-solid fa-expand\"></i> ขยายดูภาพเต็ม</button>\n"
                yield f"  <button type=\"button\" onclick=\"window.useAsPromptTemplate('{img_prompt}')\" class=\"image-btn remix-btn\"><i class=\"fa-solid fa-wand-magic-sparkles\"></i> แต่งภาพต่อในสตูดิโอ</button>\n"
                yield f"</div>\n\n"
                yield f"✨ **สไตล์ Prompt:** *{enh_prompt}*\n\n"
                yield "หากต้องการปรับเปลี่ยนสไตล์ ท่าทาง บรรยากาศ หรือสัดส่วน สามารถสั่ง Friday หรือเปิด **สตูดิโอสร้างภาพ 🎨** ได้เลยนะคะ!"
            except Exception as e:
                yield f"⚠️ ขออภัยค่ะ เกิดข้อผิดพลาดในการสร้างภาพ: {str(e)}"
            return

        # 2. ตรวจสอบว่าคำถามต้องค้นหาข้อมูลสดบนอินเทอร์เน็ตหรือไม่
        search_context = ""
        is_search, search_q = self.is_search_request(message)
        if is_search and search_q:
            yield f"🔍 *Friday กำลังค้นหาข้อมูลสดล่าสุดเกี่ยวกับ \"{search_q}\"...*\n\n"
            try:
                from web_search import search_duckduckgo, format_search_results_for_prompt
                search_results = await search_duckduckgo(search_q, max_results=4)
                if search_results:
                    search_context = format_search_results_for_prompt(search_q, search_results)
            except Exception as e:
                print(f"[WebSearch] Error: {e}")

        api_provider = self.memory.get_setting("api_provider", "gemini")
        api_key = self.memory.get_setting("api_key", "").strip()

        # หากมี API Key และเลือก Gemini
        if api_provider == "gemini" and api_key:
            async for chunk in self._stream_gemini(message, api_key, session_id, extra_context=search_context):
                yield chunk
        # หากมี API Key และเลือก OpenAI / Groq / Compatible
        elif api_provider == "openai" and api_key:
            async for chunk in self._stream_openai(message, api_key, session_id, extra_context=search_context):
                yield chunk
        # Fallback โหมดอัจฉริยะ: ใช้งานได้ทันที จำข้อมูลได้จริง
        else:
            async for chunk in self._stream_smart_fallback(message, session_id):
                yield chunk

    async def _stream_gemini(self, message: str, api_key: str, session_id: str, extra_context: str = "") -> AsyncGenerator[str, None]:
        """เรียกใช้งาน Gemini API แบบ Streaming ผ่าน HTTP Server-Sent Events (รองรับ Context สูงสุด 1,000,000 Tokens)"""
        model = self.memory.get_setting("model_name", "gemini-2.5-flash")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse&key={api_key}"
        
        system_instruction = self.build_system_prompt(extra_context=extra_context)
        history = self.memory.get_recent_history(session_id, limit=20)
        
        contents = []
        for h in history:
            role = "user" if h["role"] == "user" else "model"
            contents.append({
                "role": role,
                "parts": [{"text": h["message"]}]
            })
        contents.append({
            "role": "user",
            "parts": [{"text": message}]
        })

        payload = {
            "system_instruction": {
                "parts": [{"text": system_instruction}]
            },
            "contents": contents,
            "generationConfig": {
                "temperature": float(self.memory.get_setting("temperature", "0.7")),
                "maxOutputTokens": 8192,
            }
        }

        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                async with client.stream("POST", url, json=payload, headers={"Content-Type": "application/json"}) as response:
                    if response.status_code != 200:
                        err_text = await response.aread()
                        yield f"⚠️ เกิดข้อผิดพลาดจาก Gemini API (รหัส {response.status_code}): {err_text.decode('utf-8', errors='ignore')}"
                        return
                    
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:].strip()
                            if data_str:
                                try:
                                    data = json.loads(data_str)
                                    candidates = data.get("candidates", [])
                                    if candidates:
                                        parts = candidates[0].get("content", {}).get("parts", [])
                                        for part in parts:
                                            text_chunk = part.get("text", "")
                                            if text_chunk:
                                                yield text_chunk
                                except json.JSONDecodeError:
                                    continue
        except Exception as e:
            yield f"⚠️ การเชื่อมต่อขัดข้อง: {str(e)}"

    async def _stream_openai(self, message: str, api_key: str, session_id: str, extra_context: str = "") -> AsyncGenerator[str, None]:
        """เรียกใช้งาน OpenAI หรือ OpenAI-compatible API แบบ Streaming (รองรับ Groq, Ollama, DeepSeek)"""
        base_url = self.memory.get_setting("openai_base_url", "https://api.openai.com/v1").rstrip("/")
        model = self.memory.get_setting("model_name", "openai/gpt-oss-120b")
        url = f"{base_url}/chat/completions"

        system_instruction = self.build_system_prompt(extra_context=extra_context)
        history = self.memory.get_recent_history(session_id, limit=20)

        messages = [{"role": "system", "content": system_instruction}]
        for h in history:
            messages.append({"role": h["role"], "content": h["message"]})
        messages.append({"role": "user", "content": message})

        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "temperature": float(self.memory.get_setting("temperature", "0.7")),
            "max_tokens": 8192
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) FridayAssistant/2.5"
        }

        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                async with client.stream("POST", url, json=payload, headers=headers) as response:
                    if response.status_code != 200:
                        err_text = await response.aread()
                        yield f"⚠️ เกิดข้อผิดพลาดจาก API (รหัส {response.status_code}): {err_text.decode('utf-8', errors='ignore')}"
                        return

                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:].strip()
                            if data_str == "[DONE]":
                                break
                            try:
                                data = json.loads(data_str)
                                delta = data.get("choices", [{}])[0].get("delta", {})
                                chunk = delta.get("content", "")
                                if chunk:
                                    yield chunk
                            except json.JSONDecodeError:
                                continue
        except Exception as e:
            yield f"⚠️ การเชื่อมต่อขัดข้อง: {str(e)}"

    async def _stream_smart_fallback(self, message: str, session_id: str) -> AsyncGenerator[str, None]:
        """
        โหมด Smart Assistant ประจำตัว Friday พร้อมระบบจำข้อเท็จจริง
        ตอบโต้แบบเรียลไทม์จำลอง token streaming ได้ทันทีโดยไม่ต้องรอ API Key
        """
        text = message.strip()
        lower_text = text.lower()
        memories = self.memory.get_all_memories()

        # ตรวจสอบว่ามีข้อมูลผู้ใช้ในความจำหรือไม่
        user_name = None
        for m in memories:
            if m["key_concept"] == "ชื่อผู้ใช้":
                user_name = m["content"]
                break

        # ตรวจสอบการถามความจำ
        memory_queries = ["จำอะไรได้", "จำผมได้ไหม", "รู้จักผมไหม", "ผมชื่ออะไร", "ฉันชื่ออะไร", "ชอบอะไร", "ทำงานอะไร", "ข้อมูลของผม", "ความจำ"]
        is_memory_query = any(q in text for q in memory_queries)

        response_text = ""

        if is_memory_query:
            if not memories:
                greeting = f"สวัสดีค่ะ {user_name}!" if user_name else "สวัสดีค่ะคุณผู้ใช้!"
                response_text = f"{greeting} ดิฉัน Friday นะคะ ขณะนี้ยังไม่มีบันทึกข้อมูลส่วนตัวในหน่วยความจำเลยค่ะ คุณสามารถบอกชื่อ สิ่งที่ชอบ หรือข้อมูลสำคัญให้ดิฉันช่วยจำได้ทันทีเลยนะคะ เช่น 'ผมชื่อก้อง ชอบดื่มอเมริกาโน่เย็น' ค่ะ ✨"
            else:
                prefix = f"แน่นอนค่ะคุณ {user_name}! " if user_name else "แน่นอนค่ะ! "
                response_text = f"{prefix}Friday จำข้อมูลที่คุณเคยบันทึกไว้ได้ดังนี้ค่ะ:\n\n"
                for m in memories:
                    response_text += f"• **{m['key_concept']}**: {m['content']}\n"
                response_text += "\nคุณสามารถสั่งให้จำเพิ่มเติม หรือแก้ไขผ่านแผง 'ความจำของบอท' ทางด้านขวาได้ตลอดเวลาเลยนะคะ"
        
        elif any(w in text for w in ["สวัสดี", "หวัดดี", "hello", "hi"]):
            greeting = f"สวัสดีค่ะคุณ {user_name}! " if user_name else "สวัสดีค่ะ! "
            response_text = f"{greeting}ดิฉัน Friday ผู้ช่วยส่วนตัวของคุณ พร้อมให้บริการแล้วค่ะ มีอะไรให้ Friday ช่วยเหลือวันนี้ไหมคะ? (สามารถพิมพ์บอกข้อมูลให้ Friday จำ หรือคลิกไอคอนฟันเฟืองเพื่อใส่ Gemini API Key สำหรับการสนทนาขั้นสูงได้ตลอดเวลาค่ะ)"

        elif any(w in text for w in ["เป็นใคร", "คือใคร", "ทำอะไรได้", "แนะนำตัว"]):
            response_text = (
                "ดิฉันชื่อ **Friday** ค่ะ! เป็นระบบผู้ช่วยปัญญาประดิษฐ์อัจฉริยะที่ถูกออกแบบมาเพื่อ:\n"
                "1. ⚡ **ตอบโต้แบบเรียลไทม์:** ส่งข้อมูลคำตอบแบบไหลลื่นฉับไวทันที\n"
                "2. 🧠 **ระบบความจำถาวร:** จดจำชื่อ ข้อมูลส่วนตัว ความชอบ และคำขอของคุณได้ตลอดเวลาแม้จะปิดโปรแกรมไป\n"
                "3. 🎙️ **รองรับการพูดคุยด้วยเสียง:** รองรับทั้งการสั่งงานด้วยเสียง (STT) และให้ดิฉันออกเสียงตอบกลับ (TTS)\n"
                "4. 🔑 **เชื่อมต่อ Model ชั้นนำ:** รองรับ Google Gemini 2.5 Flash เพื่อการสนทนาที่ฉลาดล้ำลึก\n\n"
                "วันนี้มีสิ่งไหนให้ Friday ช่วยดูแลไหมคะ?"
            )

        else:
            # ตรวจสอบว่าในข้อความมีการพูดถึงสิ่งที่จำได้หรือไม่
            related = []
            for m in memories:
                if m["content"] in text or m["key_concept"] in text:
                    related.append(m)

            user_title = f"คุณ {user_name}" if user_name else "คุณ"
            if related:
                rel_info = " และ ".join([f"{r['key_concept']} ({r['content']})" for r in related])
                response_text = f"รับทราบค่ะ{user_title}! Friday เชื่อมโยงข้อมูลเกี่ยวกับ {rel_info} จากหน่วยความจำเรียบร้อยแล้วค่ะ สำหรับเรื่อง \"{text}\" ดิฉันพร้อมช่วยประสานงานและจัดการให้อย่างเต็มที่เลยค่ะ!"
            else:
                response_text = (
                    f"รับทราบค่ะ{user_title}! เรื่อง \"{text}\" Friday บันทึกบริบทการสนทนาไว้เรียบร้อยแล้วค่ะ\n\n"
                    f"💡 *คำแนะนำ:* หากต้องการสนทนาตอบคำถามเชิงลึก แต่งโค้ด หรือวิเคราะห์ข้อมูล คุณสามารถใส่ **Gemini API Key** ฟรีได้ที่เมนู ⚙️ ตั้งค่า เพื่อปลดล็อกพลังความคิดสูงสุดของ Gemini 2.5 Flash ได้ทันทีค่ะ!"
                )

        # จำลองการ Streaming คำตอบทีละคำ/ตัวอักษร
        chunk_size = 3
        for i in range(0, len(response_text), chunk_size):
            yield response_text[i:i+chunk_size]
            await asyncio.sleep(0.015)
