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
import time
from typing import AsyncGenerator, Dict, List, Any
from memory_engine import MemoryEngine
from video_project_service import VideoProjectService

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
- มีความสามารถในการมองเห็นและวิเคราะห์รูปภาพ (Multimodal Vision) สามารถอธิบายสิ่งที่อยู่ในภาพ ตอบคำถาม ถอดข้อความ และวิเคราะห์รูปภาพหรือโค้ดที่แนบมาได้อย่างละเอียด
- มีระบบสร้างและปรับแต่งรูปภาพ AI (Image Generation Engine) ในตัว สามารถสร้างภาพ วาดภาพ และนำภาพมาดัดแปลง (Remix) ได้อย่างยอดเยี่ยม
- มีสตูดิโอตัดต่อวิดีโออัจฉริยะ (Video Editing Studio) รองรับทั้ง CapCut PC, Adobe Premiere Pro และ Alight Motion โดยตรง สามารถวิเคราะห์และวางโครงสร้าง Storyboard, คำนวณ Timecodes, สังเคราะห์เสียงพากย์ และสร้างไฟล์โปรเจกต์ (XML, JSX, SRT, CapCut Drafts, Alight Motion XML) บันทึกลงเครื่องคอมพิวเตอร์ของผู้ใช้ได้จริง

{memories_context}
"""

class AIService:
    def __init__(self, memory_engine: MemoryEngine):
        self.memory = memory_engine
        self.video_service = VideoProjectService()

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

    def is_video_request(self, text: str) -> tuple[bool, str, str, str]:
        """
        ตรวจสอบว่าผู้ใช้ต้องการให้ช่วยวางแผนหรือตัดต่อคลิปสำหรับ CapCut, Premiere Pro หรือ Alight Motion หรือไม่
        คืนค่า: (is_video, topic, target_platform, aspect_ratio)
        """
        clean = text.strip()
        lower = clean.lower()

        video_keywords = [
            "ตัดต่อ", "ตัดคลิป", "ทำคลิป", "capcut", "cutcap", "premiere",
            "พรีเมียร์", "alight", "alight motion", "อะไลท์", "อะไลท์โมชั่น", "am",
            "คลิปสั้น", "shorts", "reels", "tiktok", "storyboard",
            "สคริปต์คลิป", "สคริปต์วิดีโอ", "ตัดวิดีโอ", "ตัดต่อคริป", "คริป"
        ]

        if not any(k in lower for k in video_keywords):
            return False, "", "all", "9:16"

        # ตรวจสอบแพลตฟอร์ม
        platform = "all"
        is_capcut = "capcut" in lower or "cutcap" in lower
        is_prem = "premiere" in lower or "พรีเมียร์" in lower
        is_am = "alight" in lower or "อะไลท์" in lower or "am " in lower or lower.endswith(" am")

        if is_am and not is_capcut and not is_prem:
            platform = "alightmotion"
        elif is_capcut and not is_prem and not is_am:
            platform = "capcut"
        elif is_prem and not is_capcut and not is_am:
            platform = "premiere"

        # ตรวจสอบสัดส่วน
        aspect_ratio = "9:16" if any(w in lower for w in ["tiktok", "shorts", "reels", "9:16", "แนวตั้ง", "คลิปสั้น"]) else ("16:9" if any(w in lower for w in ["youtube", "16:9", "แนวนอน"]) else ("9:16" if platform in ("capcut", "alightmotion") else "16:9"))

        # สกัดหัวข้อ
        topic = re.sub(r'^(?:อยากให้\s*)?(?:ช่วย|สอน)?\s*(?:เพิ่มฟั้งชั้น|เพิ่มฟังก์ชั่น|เพิ่มฟังก์ชัน|ฟังก์ชัน|ระบบ|แอป|เเอพ)?\s*(?:ตัดต่อคริป|ตัดต่อคลิป|ตัดคลิป|ทำคลิป|สร้างคลิป|ตัดวิดีโอ|ทำวิดีโอ)\s*(?:ในเเอพ|ในแอป|ในโปรแกรม)?\s*(?:cutcap|capcut|premiere|พรีเมียร์|alight\s*motion|alight|อะไลท์โมชั่น|อะไลท์)?\s*(?:เเละ|และ)?\s*(?:cutcap|capcut|premiere|พรีเมียร์|alight\s*motion|alight|อะไลท์โมชั่น|อะไลท์)?\s*(?:เรื่อง|เกี่ยวกับ|หน่อย|ที)?', '', clean, flags=re.IGNORECASE).strip()
        topic = re.sub(r'\s*(?:หน่อย|ที|ให้หน่อย|ให้ที|ครับ|ค่ะ|นะ|ด้วย)$', '', topic).strip()

        if not topic or len(topic) < 2:
            topic = "คลิปวิดีโอแนะนำและไฮไลท์พิเศษ"

        return True, topic, platform, aspect_ratio

    def format_video_card(self, plan: dict) -> str:
        """สร้าง Interactive Video Project Card สำหรับให้ผู้ใช้กดส่งออกไปยัง CapCut PC, Premiere Pro หรือ Alight Motion ได้ใน 1 คลิก"""
        title = plan.get("title", "Project")
        aspect = plan.get("aspect_ratio", "9:16")
        duration = plan.get("target_duration_sec", 15.0)
        scenes = plan.get("scenes", [])
        
        encoded_plan = urllib.parse.quote(json.dumps(plan, ensure_ascii=False))

        rows = []
        for idx, s in enumerate(scenes, 1):
            s_title = s.get("title", f"Scene {idx}")
            s_text = s.get("text", "")
            s_dur = s.get("duration", 4.0)
            v_idea = s.get("visual_idea", "")
            s_fx = s.get("sound_effect", "")
            rows.append(
                f'<div class="storyboard-scene-row">\n'
                f'  <div class="scene-badge"><i class="fa-solid fa-film"></i> {s_title} ({s_dur}s)</div>\n'
                f'  <div class="scene-script"><strong>🎙️ สคริปต์พากย์ & ซับ:</strong> "{s_text}"</div>\n'
                f'  <div class="scene-visual"><strong>👁️ ภาพ & B-Roll:</strong> {v_idea} {f"• 🔊 {s_fx}" if s_fx else ""}</div>\n'
                f'</div>'
            )

        card_html = (
            f'\n\n<div class="video-project-card">\n'
            f'  <div class="video-card-header">\n'
            f'    <div class="video-card-badges">\n'
            f'      <span class="video-tag capcut-tag"><i class="fa-solid fa-scissors"></i> CapCut PC</span>\n'
            f'      <span class="video-tag premiere-tag"><i class="fa-solid fa-film"></i> Premiere Pro</span>\n'
            f'      <span class="video-tag alight-tag"><i class="fa-solid fa-bolt"></i> Alight Motion</span>\n'
            f'      <span class="video-tag ratio-tag"><i class="fa-solid fa-mobile-screen"></i> {aspect}</span>\n'
            f'      <span class="video-tag time-tag"><i class="fa-solid fa-clock"></i> ~{duration:.1f} วินาที</span>\n'
            f'    </div>\n'
            f'    <h4 class="video-card-title">🎬 โครงสร้างโปรเจกต์: {title}</h4>\n'
            f'  </div>\n'
            f'  <div class="video-card-body">\n'
            f'    <div class="storyboard-scenes-list">\n'
            f'      {"".join(rows)}\n'
            f'    </div>\n'
            f'  </div>\n'
            f'  <div class="video-card-actions">\n'
            f'    <button type="button" class="video-btn capcut-btn" onclick="window.createVideoProjectFromChat(\'capcut\', decodeURIComponent(\'{encoded_plan}\'))">\n'
            f'      <i class="fa-solid fa-scissors"></i> บันทึกลง CapCut PC ทันที\n'
            f'    </button>\n'
            f'    <button type="button" class="video-btn premiere-btn" onclick="window.createVideoProjectFromChat(\'premiere\', decodeURIComponent(\'{encoded_plan}\'))">\n'
            f'      <i class="fa-solid fa-film"></i> ส่งออก Premiere Pro (.xml + .jsx)\n'
            f'    </button>\n'
            f'    <button type="button" class="video-btn alight-btn" onclick="window.createVideoProjectFromChat(\'alightmotion\', decodeURIComponent(\'{encoded_plan}\'))">\n'
            f'      <i class="fa-solid fa-bolt"></i> ส่งออก Alight Motion (.xml)\n'
            f'    </button>\n'
            f'    <button type="button" class="video-btn studio-btn" onclick="window.openVideoStudioWithPlan(decodeURIComponent(\'{encoded_plan}\'))">\n'
            f'      <i class="fa-solid fa-sliders"></i> เปิดแต่งต่อใน Studio\n'
            f'    </button>\n'
            f'  </div>\n'
            f'</div>\n\n'
        )
        return card_html

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

    def format_attachments_context(self, attachments: list) -> str:
        """แปลงข้อมูลไฟล์และโฟลเดอร์ที่แนบมาให้อยู่ในรูปแบบ Markdown Context ที่ชัดเจนสำหรับ AI"""
        if not attachments:
            return ""
        
        blocks = []
        for att in attachments:
            att_type = att.get("type", "file")
            if att_type == "folder":
                folder_name = att.get("name", "project")
                file_count = att.get("fileCount", 0)
                total_size = att.get("totalSizeStr", "")
                tree = att.get("tree", "")
                files = att.get("files", [])
                
                block = [
                    f"📁 **[ข้อมูลโฟลเดอร์ที่ผู้ใช้แนบมา: `{folder_name}`]** (มีไฟล์ทั้งหมด {file_count} ไฟล์, ขนาดรวม {total_size})",
                    "**โครงสร้างไฟล์ในโปรเจกต์ (File Tree):**",
                    "```text",
                    tree if tree else "(ไม่มีรายการ tree)",
                    "```",
                    "\n**เนื้อหาของไฟล์ภายในโฟลเดอร์:**"
                ]
                
                for f in files:
                    f_path = f.get("path", f.get("name", "unknown"))
                    f_content = f.get("content", "")
                    ext = f_path.split(".")[-1] if "." in f_path else "text"
                    block.append(f"\n--- [ไฟล์: {f_path}] ---\n```{ext}\n{f_content}\n```")
                
                blocks.append("\n".join(block))
                
            elif att_type == "file":
                f_name = att.get("name", "file")
                f_size = att.get("sizeStr", "")
                f_content = att.get("content", "")
                ext = f_name.split(".")[-1] if "." in f_name else "text"
                block = f"📄 **[ไฟล์ที่ผู้ใช้แนบมา: `{f_name}`]** ({f_size})\n```{ext}\n{f_content}\n```"
                blocks.append(block)
                
        return "\n\n".join(blocks)

    async def describe_image_for_prompt(self, img_obj: dict, api_key: str, api_provider: str) -> str:
        """วิเคราะห์ภาพต้นฉบับอย่างรวดเร็วเพื่อสร้างคำอธิบายส่งต่อให้ Image Generator"""
        try:
            raw_data = img_obj.get("data", "")
            if "," in raw_data:
                raw_data = raw_data.split(",", 1)[1]
            mime_type = img_obj.get("mime_type", "image/jpeg")

            if api_provider == "gemini" and api_key:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
                payload = {
                    "contents": [{
                        "parts": [
                            {"text": "Describe the main subject, clothing, face, pose and colors in this image in 1 concise English sentence for an image generation prompt."},
                            {"inline_data": {"mime_type": mime_type, "data": raw_data}}
                        ]
                    }]
                }
                async with httpx.AsyncClient(timeout=12.0) as client:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        return data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()

            elif api_provider == "openai" and api_key:
                base_url = self.memory.get_setting("openai_base_url", "https://api.groq.com/openai/v1").strip().rstrip("/")
                model = self.memory.get_setting("model_name", "qwen/qwen3.8-27b").strip()
                if "groq.com" in base_url and ("llama" in model or "qwen2.5" in model or not model):
                    model = "qwen/qwen3.8-27b"
                url = f"{base_url}/chat/completions"
                payload = {
                    "model": model,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Describe the main subject, clothing, face, pose and colors in this image in 1 concise English sentence for an image generation prompt."},
                            {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{raw_data}"}}
                        ]
                    }],
                    "max_tokens": 60
                }
                async with httpx.AsyncClient(timeout=12.0) as client:
                    resp = await client.post(url, headers={"Authorization": f"Bearer {api_key}"}, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        return data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        except Exception as e:
            print(f"[DescribeImage] Error: {e}")
        return ""

    async def generate_stream(self, message: str, session_id: str = "default", images: list = None, attachments: list = None) -> AsyncGenerator[str, None]:
        """
        สร้างคำตอบแบบ Real-time streaming
        รองรับทั้งข้อความ, รูปภาพ (Multimodal Vision), การสร้าง/Remix รูปภาพ และไฟล์/โฟลเดอร์โปรเจกต์
        """
        api_provider = self.memory.get_setting("api_provider", "gemini")
        api_key = self.memory.get_setting("api_key", "").strip()

        # ตรวจจับประเภท API Key อัตโนมัติ (Smart Auto-detection) เพื่อป้องกันการเลือก Provider ผิด
        if api_key.startswith("gsk_") and api_provider != "openai":
            api_provider = "openai"
        elif api_key.startswith("AIza") and api_provider != "gemini":
            api_provider = "gemini"
        elif api_key.startswith("sk-ant-") and api_provider != "claude":
            api_provider = "claude"

        # 1. ตรวจสอบว่าผู้ใช้ต้องการสร้างหรือดัดแปลงรูปภาพ (Image Generation / Remix) หรือไม่
        is_img, img_prompt = self.is_image_request(message)
        if is_img and not attachments:
            if images and len(images) > 0:
                yield "🎨 รับทราบค่ะ! Friday กำลังวิเคราะห์รูปภาพต้นฉบับและแปลงภาพใหม่ตามที่คุณสั่งสักครู่นะคะ... ✨\n\n"
                desc = await self.describe_image_for_prompt(images[0], api_key, api_provider)
                if desc:
                    full_gen_prompt = f"{img_prompt}, creative humorous caricature of {desc}, funny meme expression, vibrant lighting, 8k quality masterpiece"
                else:
                    full_gen_prompt = f"{img_prompt}, funny cheeky meme character, comical funny expression, Asian boy thumbs up, vibrant comic style"
            else:
                yield "🎨 รับทราบค่ะ! Friday กำลังออกแบบและสร้างภาพให้คุณสักครู่นะคะ... ✨\n\n"
                full_gen_prompt = img_prompt

            try:
                img_data = await self.generate_image(full_gen_prompt, model="turbo")
                img_url = img_data["image_url"]
                enh_prompt = img_data.get("english_prompt", full_gen_prompt)
                seed = img_data.get("seed", 12345)
                
                yield f"![{img_prompt}]({img_url})\n\n"
                yield f"<div class=\"image-action-bar\">\n"
                yield f"  <a href=\"{img_url}\" target=\"_blank\" class=\"image-btn download-btn\" download=\"friday_{seed}.jpg\" onclick=\"window.downloadImageDirect(event, '{img_url}', 'friday_{seed}.jpg')\"><i class=\"fa-solid fa-download\"></i> ดาวน์โหลดรูปภาพ</a>\n"
                yield f"  <button type=\"button\" onclick=\"window.openImageLightbox('{img_url}', '{img_prompt}')\" class=\"image-btn zoom-btn\"><i class=\"fa-solid fa-expand\"></i> ขยายดูภาพเต็ม</button>\n"
                yield f"  <button type=\"button\" onclick=\"window.useAsPromptTemplate('{img_prompt}')\" class=\"image-btn remix-btn\"><i class=\"fa-solid fa-wand-magic-sparkles\"></i> แต่งภาพต่อในสตูดิโอ</button>\n"
                yield f"</div>\n\n"
                yield f"✨ **สไตล์ Prompt:** *{enh_prompt}*\n\n"
                yield "หากต้องการปรับเปลี่ยนสไตล์ ท่าทาง บรรยากาศ หรือสัดส่วน สามารถสั่ง Friday เพิ่มเติมได้ตลอดนะคะ!"
            except Exception as e:
                yield f"⚠️ ขออภัยค่ะ เกิดข้อผิดพลาดในการสร้างภาพ: {str(e)}"
            return

        # 2. ตรวจสอบว่าผู้ใช้ต้องการให้ตัดต่อคลิป / วางแผนโปรเจกต์ CapCut หรือ Premiere Pro หรือไม่
        is_video, video_topic, video_platform, video_aspect = self.is_video_request(message)
        if is_video and not attachments and not images:
            yield "🎬 **รับทราบค่ะ! Friday ได้เพิ่มฟังก์ชันตัดต่อคลิปสำหรับ CapCut, Adobe Premiere Pro และ Alight Motion เรียบร้อยแล้วค่ะ** ✨\n\n"
            yield "<details class=\"thinking-box\">\n<summary>🧠 แผนการตัดต่อและโครงสร้างคลิปโดย Friday AI</summary>\n\n"
            yield f"- **หัวข้อโปรเจกต์:** {video_topic}\n"
            yield f"- **แพลตฟอร์มปลายทาง:** {video_platform.upper()} (รองรับทั้ง CapCut PC, Premiere Pro XML และ Alight Motion XML Package)\n"
            yield f"- **อัตราส่วนหน้าจอ (Aspect Ratio):** {video_aspect} ({'แนวตั้ง TikTok/Reels/Shorts' if video_aspect == '9:16' else 'แนวนอน YouTube 16:9'})\n"
            yield "- **องค์ประกอบไทม์ไลน์:** แบ่งฉาก Hook (0-3 วิ), เนื้อหาหลัก, ทริคพิเศษ และ CTA พร้อม Motion Keyframe, Velocity, เสียงพากย์ AI และซับไตเติล\n\n"
            yield "</details>\n\n"

            plan = self.video_service.plan_quick_storyboard(video_topic, aspect_ratio=video_aspect)
            card_html = self.format_video_card(plan)
            yield card_html

            yield "### 💡 วิธีใช้งานโปรเจกต์ที่ Friday สร้าง:\n"
            yield "1. **สำหรับ CapCut PC:**\n"
            yield "   - เมื่อกดปุ่ม **\"บันทึกลง CapCut PC ทันที\"** Friday จะสร้างโฟลเดอร์ Draft พร้อมไฟล์ `draft_content.json` ลงทะเบียนเข้า CapCut ในเครื่องคุณโดยตรง\n"
            yield "   - เปิดโปรแกรม CapCut คุณจะพบโปรเจกต์นี้แสดงอยู่ในหน้าแรกพร้อมตัดต่อได้ทันทีค่ะ!\n\n"
            yield "2. **สำหรับ Adobe Premiere Pro:**\n"
            yield "   - เมื่อกดปุ่ม **\"ส่งออก Premiere Pro\"** Friday จะสร้างไฟล์ **Final Cut Pro XML (`.xml`)**, สคริปต์ **ExtendScript (`.jsx`)** และไฟล์ซับไตเติล **`.srt`**\n"
            yield "   - ใน Premiere Pro: ไปที่เมนู `File > Import...` แล้วเลือกไฟล์ `.xml` ลำดับ Sequence และเสียงพากย์จะถูกสร้างลงบนไทม์ไลน์ทันทีค่ะ!\n\n"
            yield "3. **สำหรับ Alight Motion (มือถือ Android/iOS):**\n"
            yield "   - เมื่อกดปุ่ม **\"ส่งออก Alight Motion (.xml)\"** Friday จะสร้างไฟล์ **Alight Motion Scene Package (`.xml`)** ที่มี Kinetic Typography, Keyframe Velocity (scale pop/fade), โมชั่นเบลอ (Motion Blur) และเสียงพากย์\n"
            yield "   - สามารถกดดาวน์โหลดไฟล์ `.xml` ลงมือถือ แล้วกด **Share / Open with Alight Motion** เพื่อ Import เข้าแอปใน 1 วินาทีค่ะ!\n\n"
            yield "คุณสามารถคลิกปุ่มด้านบนเพื่อสั่งสร้างไฟล์ หรือกด **\"เปิดแต่งต่อใน Studio\"** เพื่อปรับแต่งฉากและสคริปต์ก่อนส่งออกได้เลยค่ะ 🚀"
            return

        # 3. ตรวจสอบว่าคำถามต้องค้นหาข้อมูลสดบนอินเทอร์เน็ตหรือไม่
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

        # 3. รวม Context จากไฟล์/โฟลเดอร์ที่แนบมา
        attachments_context = self.format_attachments_context(attachments) if attachments else ""
        context_parts = []
        if search_context:
            context_parts.append(search_context)
        if attachments_context:
            context_parts.append(attachments_context)
        final_context = "\n\n".join(context_parts)

        api_provider = self.memory.get_setting("api_provider", "gemini")
        api_key = self.memory.get_setting("api_key", "").strip()

        # ตรวจจับประเภท API Key อัตโนมัติ (Smart Auto-detection) เพื่อป้องกันการเลือก Provider ผิด
        if api_key.startswith("gsk_") and api_provider != "openai":
            api_provider = "openai"
        elif api_key.startswith("AIza") and api_provider != "gemini":
            api_provider = "gemini"
        elif api_key.startswith("sk-ant-") and api_provider != "claude":
            api_provider = "claude"

        # หากมี API Key และเลือก Gemini
        if api_provider == "gemini" and api_key:
            async for chunk in self._stream_gemini(message, api_key, session_id, extra_context=final_context, images=images):
                yield chunk
        # หากมี API Key และเลือก OpenAI / Groq / Compatible
        elif api_provider == "openai" and api_key:
            async for chunk in self._stream_openai(message, api_key, session_id, extra_context=final_context, images=images):
                yield chunk
        # หากมี API Key และเลือก Claude (Anthropic)
        elif api_provider == "claude" and api_key:
            async for chunk in self._stream_claude(message, api_key, session_id, extra_context=final_context, images=images):
                yield chunk
        # Fallback โหมดอัจฉริยะ: ใช้งานได้ทันที จำข้อมูลได้จริง
        else:
            async for chunk in self._stream_smart_fallback(message, session_id):
                yield chunk

    async def _stream_gemini(self, message: str, api_key: str, session_id: str, extra_context: str = "", images: list = None) -> AsyncGenerator[str, None]:
        """เรียกใช้งาน Gemini API แบบ Streaming ผ่าน HTTP Server-Sent Events (รองรับ Context สูงสุด 1,000,000 Tokens + Multimodal Vision)"""
        model = self.memory.get_setting("model_name", "gemini-3.8-flash")
        if not model:
            model = "gemini-3.8-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse&key={api_key}"
        
        system_instruction = self.build_system_prompt(extra_context=extra_context)
        history = self.memory.get_recent_history(session_id, limit=20)
        
        contents = []
        for h in history:
            msg_text = h.get("message", "")
            # ข้ามข้อความแจ้งเตือน error เพื่อไม่ให้เปลือง Token และไม่รบกวน Context
            if h.get("role") == "assistant" and (msg_text.startswith("⚠️") or "rate_limit_exceeded" in msg_text):
                continue
            role = "user" if h["role"] == "user" else "model"
            contents.append({
                "role": role,
                "parts": [{"text": msg_text}]
            })
        
        user_parts = [{"text": message}]
        if images:
            for img in images:
                raw_data = img.get("data", "")
                if "," in raw_data:
                    raw_data = raw_data.split(",", 1)[1]
                user_parts.append({
                    "inline_data": {
                        "mime_type": img.get("mime_type", "image/jpeg"),
                        "data": raw_data
                    }
                })
        contents.append({
            "role": "user",
            "parts": user_parts
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

        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=90.0) as client:
                    async with client.stream("POST", url, json=payload, headers={"Content-Type": "application/json"}) as response:
                        if response.status_code == 503 or response.status_code == 429:
                            if attempt < max_retries:
                                await asyncio.sleep(1.5 * (attempt + 1))
                                continue
                            else:
                                err_text = await response.aread()
                                yield f"⚠️ เซิร์ฟเวอร์ Google Gemini กำลังมีผู้ใช้งานหนาแน่นชั่วคราว (รหัส 503): กรุณาลองส่งข้อความอีกครั้งในอีกสักครู่นะคะ"
                                return
                        elif response.status_code != 200:
                            raw_err = await response.aread()
                            err_str = raw_err.decode('utf-8', errors='ignore')
                            if response.status_code == 400 and ("API_KEY_INVALID" in err_str or "API key not valid" in err_str):
                                yield "⚠️ **Google Gemini API Key ไม่ถูกต้อง (รหัส 400)**\n\n"
                                if api_key.startswith("gsk_"):
                                    yield "👉 **ตรวจพบว่าคุณใส่ Groq API Key (`gsk_...`) แทนที่จะเป็น Gemini Key**\nระบบได้สลับผู้ให้บริการไปเป็น Groq ให้โดยอัตโนมัติแล้ว กรุณาลองส่งข้อความใหม่อีกครั้งค่ะ ✨\n"
                                else:
                                    yield "👉 กรุณาตรวจสอบ API Key ในหน้า **ตั้งค่า (Settings ⚙️)** โดยสมัครรับ Key ฟรีได้ที่: **[Google AI Studio](https://aistudio.google.com/app/apikey)** ค่ะ"
                            else:
                                yield f"⚠️ เกิดข้อผิดพลาดจาก Gemini API (รหัส {response.status_code}): {err_str}"
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
                        return  # สำเร็จ ออกจาก loop retry
            except Exception as e:
                if attempt < max_retries:
                    await asyncio.sleep(1.5)
                    continue
                yield f"⚠️ การเชื่อมต่อขัดข้อง: {str(e)}"
                return

    async def _stream_openai(self, message: str, api_key: str, session_id: str, extra_context: str = "", images: list = None) -> AsyncGenerator[str, None]:
        """เรียกใช้งาน OpenAI หรือ OpenAI-compatible API แบบ Streaming (รองรับ Groq, Ollama, DeepSeek)"""
        base_url = self.memory.get_setting("openai_base_url", "https://api.groq.com/openai/v1").strip().rstrip("/")
        model = self.memory.get_setting("model_name", "qwen/qwen3.8-27b").strip()
        
        is_groq = "groq.com" in base_url

        # ปรับโมเดล Groq อัตโนมัติหากเป็นโมเดลที่ถูกยกเลิกแล้ว หรือมี Rate Limit OTPM แคบมาก
        if is_groq and ("llama-3.1" in model or "llama-3.3" in model or "qwen2.5" in model or not model):
            model = "qwen/qwen3.8-27b"
            
        url = f"{base_url}/chat/completions"

        # ตรวจสอบเบื้องต้นสำหรับ Groq API Key
        if is_groq and not api_key.startswith("gsk_"):
            yield "⚠️ **API Key ไม่ถูกต้องสำหรับ Groq!**\n\nGroq API Key ต้องขึ้นต้นด้วย **`gsk_`** เสมอค่ะ (Key ที่ใส่อยู่ไม่ใช่ของ Groq)\n\n👉 กรุณาสร้าง Key ใหม่ฟรีที่: **[console.groq.com/keys](https://console.groq.com/keys)** แล้วนำมาใส่ในช่อง **API Key** ในหน้าตั้งค่าค่ะ 🎯"
            return

        system_instruction = self.build_system_prompt(extra_context=extra_context)
        history = self.memory.get_recent_history(session_id, limit=20)

        messages = [{"role": "system", "content": system_instruction}]
        for h in history:
            msg_content = h.get("message", "")
            # ข้ามข้อความแจ้งเตือน error เพื่อไม่ให้เปลือง Token และไม่ให้ AI จำ error ไปตอบ
            if h.get("role") == "assistant" and (msg_content.startswith("⚠️") or "rate_limit_exceeded" in msg_content):
                continue
            messages.append({"role": h["role"], "content": msg_content})
        
        if images:
            user_content = [{"type": "text", "text": message}]
            for img in images:
                raw_data = img.get("data", "")
                mime_type = img.get("mime_type", "image/jpeg")
                if not raw_data.startswith("data:"):
                    data_url = f"data:{mime_type};base64,{raw_data}"
                else:
                    data_url = raw_data
                user_content.append({
                    "type": "image_url",
                    "image_url": {"url": data_url}
                })
            messages.append({"role": "user", "content": user_content})
        else:
            messages.append({"role": "user", "content": message})

        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "temperature": float(self.memory.get_setting("temperature", "0.7")),
        }
        
        # สำหรับ Groq ห้ามใส่ max_tokens=8192 เด็ดขาด เพราะ Free Tier จะนำไปคำนวณหักลบ OTPM (Output Tokens Per Minute) ล่วงหน้าจนติด Error 429
        if not is_groq:
            payload["max_tokens"] = 8192

        headers = {
            "Authorization": f"Bearer {api_key.strip()}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) FridayAssistant/2.5"
        }

        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                async with client.stream("POST", url, json=payload, headers=headers) as response:
                    if response.status_code != 200:
                        err_text = (await response.aread()).decode('utf-8', errors='ignore')
                        
                        # รายการโมเดลสำรองบน Groq เมื่อเกิดข้อผิดพลาด Model Not Found หรือ Rate Limit (429 OTPM)
                        fallback_models = ["qwen/qwen3.8-27b", "openai/gpt-oss-120b", "openai/gpt-oss-20b"]
                        is_rate_limit = response.status_code == 429 or "rate_limit_exceeded" in err_text or "OTPM" in err_text
                        is_model_err = ("model_not_found" in err_text or "model_decommissioned" in err_text or response.status_code in [400, 404])

                        if is_groq and (is_rate_limit or is_model_err):
                            candidate_models = [m for m in fallback_models if m != payload["model"]]
                            for alt_model in candidate_models:
                                alt_payload = dict(payload)
                                alt_payload["model"] = alt_model
                                alt_payload.pop("max_tokens", None)
                                
                                try:
                                    async with client.stream("POST", url, json=alt_payload, headers=headers) as retry_resp:
                                        if retry_resp.status_code == 200:
                                            async for line in retry_resp.aiter_lines():
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
                                            return
                                except Exception:
                                    continue

                        if response.status_code == 429 or "rate_limit_exceeded" in err_text:
                            yield "⚠️ **ขออภัยค่ะ โควตาข้อความของ Groq ชั่วคราวเต็ม (Rate Limit 429)**\n\nบัญชี Free Tier ของ Groq มีการจำกัดปริมาณข้อความต่อนาที (Tokens Per Minute) กรุณารอสักครู่ (ประมาณ 10-20 วินาที) แล้วส่งข้อความใหม่อีกครั้งค่ะ\n\n💡 **แนะนำ:** คุณสามารถสลับไปใช้ **Google Gemini (ฟรีและโควตาสูงกว่า)** ในหน้าตั้งค่า ⚙️ ได้ทันทีค่ะ ✨"
                            return

                        yield f"⚠️ เกิดข้อผิดพลาดจาก API (รหัส {response.status_code}): {err_text}"
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

    async def _stream_claude(self, message: str, api_key: str, session_id: str, extra_context: str = "", images: list = None) -> AsyncGenerator[str, None]:
        """เรียกใช้งาน Anthropic Claude API แบบ Streaming ผ่าน Messages API พร้อม SSE"""
        model = self.memory.get_setting("model_name", "claude-sonnet-4-5")
        if not model or not model.startswith("claude"):
            model = "claude-sonnet-4-5"
        url = "https://api.anthropic.com/v1/messages"

        system_instruction = self.build_system_prompt(extra_context=extra_context)
        history = self.memory.get_recent_history(session_id, limit=20)

        messages = []
        for h in history:
            msg_content = h.get("message", "")
            if h.get("role") == "assistant" and (msg_content.startswith("⚠️") or "rate_limit_exceeded" in msg_content):
                continue
            role = "user" if h["role"] == "user" else "assistant"
            messages.append({"role": role, "content": msg_content})
        
        if images:
            user_content = []
            for img in images:
                raw_data = img.get("data", "")
                if "," in raw_data:
                    raw_data = raw_data.split(",", 1)[1]
                user_content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": img.get("mime_type", "image/jpeg"),
                        "data": raw_data
                    }
                })
            user_content.append({"type": "text", "text": message})
            messages.append({"role": "user", "content": user_content})
        else:
            messages.append({"role": "user", "content": message})

        payload = {
            "model": model,
            "max_tokens": 8192,
            "system": system_instruction,
            "messages": messages,
            "stream": True,
            "temperature": float(self.memory.get_setting("temperature", "0.7")),
        }

        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
            "User-Agent": "FridayAssistant/2.5"
        }

        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                async with client.stream("POST", url, json=payload, headers=headers) as response:
                    if response.status_code == 401:
                        yield "⚠️ Claude API Key ไม่ถูกต้องหรือหมดอายุค่ะ กรุณาตรวจสอบและอัปเดต API Key ในการตั้งค่าใหม่นะคะ"
                        return
                    elif response.status_code == 429:
                        yield "⚠️ Claude API กำลังถูกใช้งานหนาแน่น (Rate Limit) กรุณารอสักครู่แล้วลองใหม่นะคะ"
                        return
                    elif response.status_code != 200:
                        err_text = await response.aread()
                        yield f"⚠️ เกิดข้อผิดพลาดจาก Claude API (รหัส {response.status_code}): {err_text.decode('utf-8', errors='ignore')}"
                        return

                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:].strip()
                            if not data_str:
                                continue
                            try:
                                data = json.loads(data_str)
                                event_type = data.get("type", "")
                                if event_type == "content_block_delta":
                                    delta = data.get("delta", {})
                                    if delta.get("type") == "text_delta":
                                        chunk = delta.get("text", "")
                                        if chunk:
                                            yield chunk
                                elif event_type == "message_stop":
                                    break
                            except json.JSONDecodeError:
                                continue
        except Exception as e:
            yield f"⚠️ การเชื่อมต่อ Claude ขัดข้อง: {str(e)}"

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
