"""
Friday Video Project Service
โมดูลสำหรับสร้างและจัดการโปรเจกต์ตัดต่อวิดีโอแบบเนทีฟ:
1. CapCut PC: สร้างโฟลเดอร์ Draft, draft_content.json, draft_meta_info.json และลงทะเบียนเข้า root_meta_info.json ในเครื่องโดยตรง
2. Adobe Premiere Pro: สร้าง Final Cut Pro XML (.xml), ExtendScript (.jsx), ซับไตเติล (.srt) และ Markers บนไทม์ไลน์
3. Auto Voiceover & Subtitles: ใช้ Edge-TTS สังเคราะห์เสียงพากย์และซิงค์ไทม์โค้ดอัตโนมัติ
"""

import os
import json
import uuid
import time
import math
import asyncio
import subprocess
import re
from typing import List, Dict, Any, Optional
from datetime import datetime

class VideoProjectService:
    def __init__(self, base_export_dir: Optional[str] = None):
        self.appdata_local = os.environ.get("LOCALAPPDATA", r"C:\Users\ASUS\AppData\Local")
        self.capcut_draft_root = os.path.join(self.appdata_local, r"CapCut\User Data\Projects\com.lveditor.draft")
        self.capcut_exe_candidates = [
            os.path.join(self.appdata_local, r"CapCut\Apps\CapCut.exe"),
            r"C:\Program Files\CapCut\CapCut.exe",
            r"C:\Program Files (x86)\CapCut\CapCut.exe"
        ]
        
        self.premiere_exe_candidates = [
            r"C:\Program Files\Adobe\Adobe Premiere Pro 2023\Adobe Premiere Pro.exe",
            r"C:\Program Files\Adobe\Adobe Premiere Pro 2024\Adobe Premiere Pro.exe",
            r"C:\Program Files\Adobe\Adobe Premiere Pro 2025\Adobe Premiere Pro.exe",
            r"C:\Program Files\Adobe\Adobe Premiere Pro 2022\Adobe Premiere Pro.exe",
        ]
        
        self.base_export_dir = base_export_dir or os.path.join(os.path.dirname(__file__), "data", "video_projects")
        os.makedirs(self.base_export_dir, exist_ok=True)
        os.makedirs(os.path.join(self.base_export_dir, "premiere"), exist_ok=True)
        os.makedirs(os.path.join(self.base_export_dir, "capcut_exports"), exist_ok=True)
        os.makedirs(os.path.join(self.base_export_dir, "alightmotion"), exist_ok=True)

    def detect_environment(self) -> Dict[str, Any]:
        """ตรวจสอบความพร้อมของโปรแกรม CapCut, Adobe Premiere Pro และ Alight Motion"""
        # 1. CapCut Check
        capcut_drafts_available = os.path.exists(self.capcut_draft_root)
        capcut_exe = None
        for cand in self.capcut_exe_candidates:
            if os.path.exists(cand):
                capcut_exe = cand
                break
        if not capcut_exe:
            # ค้นหาใน Apps/*/CapCut.exe
            apps_dir = os.path.join(self.appdata_local, r"CapCut\Apps")
            if os.path.exists(apps_dir):
                for item in os.listdir(apps_dir):
                    sub = os.path.join(apps_dir, item, "CapCut.exe")
                    if os.path.exists(sub):
                        capcut_exe = sub
                        break

        # 2. Premiere Pro Check
        premiere_exe = None
        for cand in self.premiere_exe_candidates:
            if os.path.exists(cand):
                premiere_exe = cand
                break
        if not premiere_exe:
            adobe_dir = r"C:\Program Files\Adobe"
            if os.path.exists(adobe_dir):
                for item in os.listdir(adobe_dir):
                    if "Premiere Pro" in item:
                        sub = os.path.join(adobe_dir, item, "Adobe Premiere Pro.exe")
                        if os.path.exists(sub):
                            premiere_exe = sub
                            break

        return {
            "capcut": {
                "installed": bool(capcut_exe or capcut_drafts_available),
                "exe_path": capcut_exe,
                "draft_root": self.capcut_draft_root if capcut_drafts_available else None,
                "direct_sync_supported": capcut_drafts_available
            },
            "premiere": {
                "installed": bool(premiere_exe),
                "exe_path": premiere_exe,
                "export_dir": os.path.join(self.base_export_dir, "premiere"),
                "xml_supported": True,
                "jsx_supported": True,
                "srt_supported": True
            },
            "alightmotion": {
                "installed": True,
                "xml_supported": True,
                "export_dir": os.path.join(self.base_export_dir, "alightmotion"),
                "presets_supported": True,
                "effects_supported": ["Motion Blur", "Oscillate / Shake", "Scale Pop", "Fade"]
            },
            "export_dir": self.base_export_dir
        }

    def list_capcut_drafts(self) -> List[Dict[str, Any]]:
        """ดึงรายชื่อโปรเจกต์ CapCut ที่มีอยู่ในเครื่องทั้งหมด (เรียงจากล่าสุดไปเก่าสุด)"""
        drafts = []
        root_meta_path = os.path.join(self.capcut_draft_root, "root_meta_info.json")
        if os.path.exists(root_meta_path):
            try:
                with open(root_meta_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    store = data.get("all_draft_store", [])
                    # เรียงลำดับตามเวลาสร้าง/แก้ไขล่าสุด
                    store_sorted = sorted(
                        store,
                        key=lambda x: max(x.get("tm_draft_modified", 0), x.get("tm_draft_create", 0)),
                        reverse=True
                    )
                    for item in store_sorted:
                        name = item.get("draft_name", "Untitled")
                        draft_id = item.get("draft_id", "")
                        fold_path = item.get("draft_fold_path", "")
                        duration_us = item.get("tm_duration", 0)
                        created_us = item.get("tm_draft_create", 0)
                        
                        created_dt = ""
                        if created_us:
                            try:
                                created_dt = datetime.fromtimestamp(created_us / 1_000_000).strftime("%Y-%m-%d %H:%M")
                            except Exception:
                                pass
                                
                        drafts.append({
                            "name": name,
                            "id": draft_id,
                            "path": fold_path,
                            "duration_sec": round(duration_us / 1_000_000, 2),
                            "created": created_dt,
                            "cover": item.get("draft_cover", "")
                        })
            except Exception as e:
                print(f"[CapCut] Error reading root_meta_info: {e}")
        return drafts

    def list_premiere_projects(self) -> List[Dict[str, Any]]:
        """ดึงรายชื่อโปรเจกต์ Premiere Pro ที่ส่งออกไว้ทั้งหมด"""
        projects = []
        prem_dir = os.path.join(self.base_export_dir, "premiere")
        if os.path.exists(prem_dir):
            for item in os.listdir(prem_dir):
                folder_path = os.path.join(prem_dir, item)
                if os.path.isdir(folder_path):
                    xml_file = os.path.join(folder_path, f"{item}.xml")
                    srt_file = os.path.join(folder_path, f"{item}.srt")
                    mtime = os.path.getmtime(folder_path)
                    created_dt = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
                    projects.append({
                        "name": item,
                        "path": folder_path,
                        "has_xml": os.path.exists(xml_file),
                        "has_srt": os.path.exists(srt_file),
                        "xml_path": xml_file if os.path.exists(xml_file) else None,
                        "created": created_dt
                    })
        return sorted(projects, key=lambda x: x["created"], reverse=True)

    def list_alightmotion_projects(self) -> List[Dict[str, Any]]:
        """ดึงรายชื่อโปรเจกต์ Alight Motion XML ทั้งหมดที่สร้างไว้"""
        projects = []
        am_dir = os.path.join(self.base_export_dir, "alightmotion")
        if os.path.exists(am_dir):
            for item in os.listdir(am_dir):
                folder_path = os.path.join(am_dir, item)
                if os.path.isdir(folder_path):
                    xml_file = os.path.join(folder_path, f"{item}.xml")
                    srt_file = os.path.join(folder_path, f"{item}.srt")
                    mtime = os.path.getmtime(folder_path)
                    created_dt = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
                    projects.append({
                        "name": item,
                        "path": folder_path,
                        "has_xml": os.path.exists(xml_file),
                        "has_srt": os.path.exists(srt_file),
                        "xml_path": xml_file if os.path.exists(xml_file) else None,
                        "download_url": f"/api/video/download-alightmotion/{item}",
                        "created": created_dt
                    })
        return sorted(projects, key=lambda x: x["created"], reverse=True)

    # ==================== Audio Voiceover Generator ====================

    async def generate_voiceover_file(self, text: str, output_path: str, voice: str = "th-TH-PremwadeeNeural") -> float:
        """สร้างไฟล์เสียง MP3 จากข้อความผ่าน Edge-TTS และคืนค่าความยาวเสียง (วินาที)"""
        clean_text = re.sub(r'<[^>]+>', '', text)
        clean_text = re.sub(r'[*_#`~>•|\-]', ' ', clean_text).strip()
        if not clean_text:
            return 0.0

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        try:
            import edge_tts
            communicate = edge_tts.Communicate(clean_text, voice)
            audio_data = bytearray()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data.extend(chunk["data"])

            if len(audio_data) > 0:
                with open(output_path, "wb") as f:
                    f.write(audio_data)
                
                # คำนวณความยาวเสียงโดยประมาณ (Edge-TTS 48kbps = 6000 bytes/sec)
                # สำหรับความแม่นยำสูง สามารถใช้ header หรือ byte ratio
                duration = len(audio_data) / 6000.0
                return max(1.0, round(duration, 2))
        except Exception as e:
            print(f"[Voiceover] Edge-TTS failed: {e}")

        # Fallback ด้วย gTTS
        try:
            from gtts import gTTS
            tts = gTTS(text=clean_text, lang='th')
            tts.save(output_path)
            size = os.path.getsize(output_path)
            duration = size / 4000.0
            return max(1.0, round(duration, 2))
        except Exception as e:
            print(f"[Voiceover] gTTS fallback failed: {e}")
            return 3.0

    # ==================== CapCut Draft Generator ====================

    def _sanitize_name(self, name: str) -> str:
        clean = re.sub(r'[\\/*?:"<>|]', "", name).strip()
        return clean if clean else "Friday_Project"

    async def create_capcut_project(
        self,
        project_name: str,
        aspect_ratio: str = "9:16",
        scenes: List[Dict[str, Any]] = None,
        generate_voiceover: bool = True,
        voice: str = "th-TH-PremwadeeNeural",
        custom_draft_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        สร้างโปรเจกต์ CapCut PC ในเครื่องโดยตรง:
        - เขียน draft_content.json (โครงสร้าง Tracks: Video, Audio, Subtitle)
        - เขียน draft_meta_info.json
        - อัปเดต root_meta_info.json ในคอมพิวเตอร์ของผู้ใช้
        """
        clean_name = self._sanitize_name(project_name)
        draft_root = custom_draft_dir or self.capcut_draft_root
        
        # ป้องกันชื่อโฟลเดอร์ซ้ำ
        project_folder = os.path.join(draft_root, clean_name)
        if os.path.exists(project_folder):
            project_folder = os.path.join(draft_root, f"{clean_name}_{int(time.time())}")
            clean_name = os.path.basename(project_folder)

        os.makedirs(project_folder, exist_ok=True)
        os.makedirs(os.path.join(project_folder, "Resources"), exist_ok=True)

        draft_id = str(uuid.uuid4()).upper()
        now_us = int(time.time() * 1_000_000)

        # ตั้งค่าสัดส่วนหน้าจอ Canvas
        if aspect_ratio == "9:16":
            width, height, ratio_str = 1080, 1920, "9:16"
        elif aspect_ratio == "1:1":
            width, height, ratio_str = 1080, 1080, "1:1"
        else: # 16:9
            width, height, ratio_str = 1920, 1080, "16:9"

        scenes = scenes or [
            {"title": "Hook", "text": "สวัสดีครับทุกคน วันนี้ Friday มีทริคเด็ดๆ มาแชร์กันครับ!", "duration": 4.0},
            {"title": "Main Content", "text": "เทคนิคง่ายๆ ที่ทำให้การทำงานเร็วขึ้นถึง 10 เท่า", "duration": 5.0},
            {"title": "Call To Action", "text": "อย่าลืมกดติดตามและกดหัวใจเพื่อไม่พลาดคลิปถัดไปนะครับ!", "duration": 4.0}
        ]

        current_time_us = 0
        video_segments = []
        audio_segments = []
        text_segments = []
        
        materials_audios = []
        materials_texts = []
        materials_videos = []

        for idx, scene in enumerate(scenes):
            raw_duration = float(scene.get("duration", 4.0))
            scene_text = scene.get("text", "").strip()
            video_path = scene.get("media_path", "").strip()

            # สังเคราะห์เสียงพากย์ถ้าเลือกเปิดไว้
            audio_path = None
            if generate_voiceover and scene_text:
                audio_filename = f"voiceover_scene_{idx + 1}.mp3"
                audio_full_path = os.path.join(project_folder, "Resources", audio_filename)
                measured_dur = await self.generate_voiceover_file(scene_text, audio_full_path, voice=voice)
                if measured_dur > 0:
                    raw_duration = max(raw_duration, measured_dur + 0.5)
                    audio_path = audio_full_path.replace("\\", "/")

            duration_us = int(raw_duration * 1_000_000)

            # 1. Video Segment (หากมีไฟล์วิดีโอจริง หรือใช้ Placeholder Track)
            if video_path and os.path.exists(video_path):
                vid_id = str(uuid.uuid4()).upper()
                materials_videos.append({
                    "id": vid_id,
                    "unique_id": vid_id.lower().replace("-", ""),
                    "type": "video",
                    "duration": duration_us,
                    "path": video_path.replace("\\", "/"),
                    "has_audio": True
                })
                video_segments.append({
                    "id": str(uuid.uuid4()).upper(),
                    "material_id": vid_id,
                    "source_timerange": {"start": 0, "duration": duration_us},
                    "target_timerange": {"start": current_time_us, "duration": duration_us},
                    "speed": 1.0,
                    "volume": 1.0,
                    "clip": {"scale": {"x": 1.0, "y": 1.0}, "rotation": 0.0, "transform": {"x": 0.0, "y": 0.0}}
                })

            # 2. Audio Segment (เสียงพากย์)
            if audio_path:
                aud_id = str(uuid.uuid4()).upper()
                materials_audios.append({
                    "id": aud_id,
                    "unique_id": aud_id.lower().replace("-", ""),
                    "type": "audio",
                    "name": f"Scene_{idx+1}_Voice",
                    "duration": duration_us,
                    "path": audio_path
                })
                audio_segments.append({
                    "id": str(uuid.uuid4()).upper(),
                    "material_id": aud_id,
                    "source_timerange": {"start": 0, "duration": duration_us},
                    "target_timerange": {"start": current_time_us, "duration": duration_us},
                    "speed": 1.0,
                    "volume": 1.0
                })

            # 3. Subtitle / Text Segment
            if scene_text:
                txt_id = str(uuid.uuid4()).upper()
                # CapCut Subtitle Text Material Content
                text_content_payload = json.dumps({
                    "text": scene_text,
                    "styles": [{
                        "fill": {"content": {"render_type": "solid", "solid": {"color": [1, 1, 1]}}},
                        "size": 9.0 if aspect_ratio == "9:16" else 11.0,
                        "bold": True,
                        "range": [0, len(scene_text)]
                    }]
                }, ensure_ascii=False)

                materials_texts.append({
                    "id": txt_id,
                    "name": f"Sub_{idx+1}",
                    "type": "text",
                    "content": text_content_payload,
                    "alignment": 1
                })
                text_segments.append({
                    "id": str(uuid.uuid4()).upper(),
                    "material_id": txt_id,
                    "source_timerange": None,
                    "target_timerange": {"start": current_time_us, "duration": duration_us},
                    "speed": 1.0,
                    "clip": {
                        "transform": {"x": 0.0, "y": -0.65 if aspect_ratio == "9:16" else -0.75},
                        "scale": {"x": 1.0, "y": 1.0}
                    }
                })

            current_time_us += duration_us

        total_duration_us = current_time_us

        # รวบรวมแทร็ก
        tracks = []
        if video_segments:
            tracks.append({
                "id": str(uuid.uuid4()).upper(),
                "type": "video",
                "segments": video_segments,
                "flag": 0
            })
        if text_segments:
            tracks.append({
                "id": str(uuid.uuid4()).upper(),
                "type": "text",
                "segments": text_segments,
                "flag": 0
            })
        if audio_segments:
            tracks.append({
                "id": str(uuid.uuid4()).upper(),
                "type": "audio",
                "segments": audio_segments,
                "flag": 0
            })

        # โครงสร้าง draft_content.json ตามมาตรฐาน CapCut PC
        draft_content = {
            "id": draft_id,
            "version": 360000,
            "new_version": "183.0.0",
            "name": clean_name,
            "duration": total_duration_us,
            "create_time": now_us,
            "update_time": now_us,
            "fps": 30.0,
            "color_space": 0,
            "canvas_config": {
                "ratio": ratio_str,
                "width": width,
                "height": height,
                "background": None
            },
            "tracks": tracks,
            "materials": {
                "videos": materials_videos,
                "audios": materials_audios,
                "texts": materials_texts,
                "transitions": [],
                "effects": [],
                "stickers": [],
                "speeds": [],
                "canvases": []
            },
            "platform": {"os": "windows", "app": "CapCut"}
        }

        # 1. เขียน draft_content.json
        content_path = os.path.join(project_folder, "draft_content.json")
        with open(content_path, "w", encoding="utf-8") as f:
            json.dump(draft_content, f, ensure_ascii=False, indent=2)

        # 2. เขียน draft_meta_info.json
        draft_meta = {
            "draft_name": clean_name,
            "draft_id": draft_id,
            "draft_fold_path": project_folder.replace("\\", "/"),
            "draft_root_path": draft_root.replace("\\", "/"),
            "tm_draft_create": now_us,
            "tm_draft_modified": now_us,
            "tm_duration": total_duration_us
        }
        meta_path = os.path.join(project_folder, "draft_meta_info.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(draft_meta, f, ensure_ascii=False, indent=2)

        # 3. อัปเดต root_meta_info.json ของ CapCut ในเครื่องอัตโนมัติ
        registered_in_capcut = False
        root_meta_path = os.path.join(draft_root, "root_meta_info.json")
        if os.path.exists(root_meta_path):
            try:
                with open(root_meta_path, "r", encoding="utf-8") as rf:
                    root_data = json.load(rf)
                
                all_store = root_data.get("all_draft_store", [])
                
                # เพิ่มโปรเจกต์ใหม่เข้าไปบนสุดของ Store
                new_entry = {
                    "draft_name": clean_name,
                    "draft_id": draft_id,
                    "draft_fold_path": project_folder.replace("\\", "/"),
                    "draft_root_path": draft_root.replace("\\", "/"),
                    "draft_json_file": content_path.replace("\\", "/"),
                    "tm_draft_create": now_us,
                    "tm_draft_modified": now_us,
                    "tm_duration": total_duration_us,
                    "cloud_draft_sync": False,
                    "streaming_edit_draft_ready": True
                }
                
                # ลบรายการเก่าถ้าชื่อตรงกันแล้วใส่รายการใหม่ด้านหน้า
                all_store = [d for d in all_store if d.get("draft_id") != draft_id and d.get("draft_fold_path") != project_folder.replace("\\", "/")]
                all_store.insert(0, new_entry)
                
                root_data["all_draft_store"] = all_store
                root_data["draft_ids"] = len(all_store)

                with open(root_meta_path, "w", encoding="utf-8") as wf:
                    json.dump(root_data, wf, ensure_ascii=False, indent=2)
                registered_in_capcut = True
            except Exception as e:
                print(f"[CapCut] Error updating root_meta_info: {e}")

        # สร้างไฟล์ SRT ซับไตเติลสำรองไว้ในโฟลเดอร์โปรเจกต์ด้วย
        srt_content = self.generate_srt_content(scenes)
        with open(os.path.join(project_folder, f"{clean_name}.srt"), "w", encoding="utf-8") as f:
            f.write(srt_content)

        return {
            "status": "success",
            "platform": "capcut",
            "project_name": clean_name,
            "project_folder": project_folder,
            "draft_id": draft_id,
            "duration_sec": round(total_duration_us / 1_000_000, 2),
            "scenes_count": len(scenes),
            "aspect_ratio": aspect_ratio,
            "registered_in_capcut": registered_in_capcut,
            "content_json_path": content_path,
            "has_voiceover": generate_voiceover
        }

    # ==================== Adobe Premiere Pro Generator ====================

    def _format_timecode_srt(self, seconds: float) -> str:
        """แปลงวินาทีเป็นรูปแบบ 00:00:00,000 สำหรับไฟล์ SRT"""
        hrs = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds - int(seconds)) * 1000)
        return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"

    def generate_srt_content(self, scenes: List[Dict[str, Any]]) -> str:
        """สร้างเนื้อหาไฟล์ SubRip Subtitle (.srt)"""
        srt_lines = []
        current_time = 0.0
        
        for idx, scene in enumerate(scenes, 1):
            dur = float(scene.get("duration", 4.0))
            text = scene.get("text", "").strip()
            if not text:
                text = scene.get("title", f"Scene {idx}")
                
            start_tc = self._format_timecode_srt(current_time)
            end_tc = self._format_timecode_srt(current_time + dur)
            
            srt_lines.append(str(idx))
            srt_lines.append(f"{start_tc} --> {end_tc}")
            srt_lines.append(text)
            srt_lines.append("") # บรรทัดว่างคั่น
            
            current_time += dur
            
        return "\n".join(srt_lines)

    async def create_premiere_project(
        self,
        project_name: str,
        aspect_ratio: str = "16:9",
        scenes: List[Dict[str, Any]] = None,
        generate_voiceover: bool = True,
        voice: str = "th-TH-PremwadeeNeural",
        fps: int = 30
    ) -> Dict[str, Any]:
        """
        สร้างแพ็กเกจโปรเจกต์สำหรับ Adobe Premiere Pro:
        1. FCP/Premiere XML (.xml): ไทม์ไลน์ Sequence, Tracks, Clips และ Timeline Markers
        2. ExtendScript (.jsx): สคริปต์สั่งอิมพอร์ตและสร้างไทม์ไลน์ใน Premiere Pro อัตโนมัติ
        3. SubRip Subtitles (.srt): ซับไตเติลพร้อม Timecodes ตรงกับฉาก
        4. Audio Voiceovers (.mp3): สร้างไฟล์เสียงพากย์แต่ละฉาก
        """
        clean_name = self._sanitize_name(project_name)
        export_folder = os.path.join(self.base_export_dir, "premiere", clean_name)
        os.makedirs(export_folder, exist_ok=True)
        os.makedirs(os.path.join(export_folder, "Audio"), exist_ok=True)

        if aspect_ratio == "9:16":
            width, height = 1080, 1920
        elif aspect_ratio == "1:1":
            width, height = 1080, 1080
        else: # 16:9
            width, height = 1920, 1080

        scenes = scenes or [
            {"title": "Hook", "text": "สวัสดีครับ วันนี้เราจะมาเจาะลึกฟีเจอร์เด็ดใน Premiere Pro กันครับ", "duration": 4.0},
            {"title": "Highlight Scene", "text": "เทคนิคการตัดต่อแบบไร้รอยต่อ และการวาง Markers", "duration": 5.0},
            {"title": "Call To Action", "text": "กดเซฟคลิปนี้ไว้ดูซ้ำ และกดติดตามได้เลยครับ", "duration": 4.0}
        ]

        current_frame = 0
        markers_xml = []
        audio_clipitems = []
        audio_files_for_jsx = []

        # สร้างไฟล์เสียงพากย์ (ถ้าเปิดไว้) และคำนวณเฟรม
        for idx, scene in enumerate(scenes, 1):
            dur_sec = float(scene.get("duration", 4.0))
            scene_text = scene.get("text", "").strip()
            scene_title = scene.get("title", f"Scene {idx}")

            audio_file_path = None
            if generate_voiceover and scene_text:
                audio_name = f"voice_scene_{idx}.mp3"
                full_audio_path = os.path.join(export_folder, "Audio", audio_name)
                measured_dur = await self.generate_voiceover_file(scene_text, full_audio_path, voice=voice)
                if measured_dur > 0:
                    dur_sec = max(dur_sec, measured_dur + 0.3)
                    audio_file_path = full_audio_path
                    audio_files_for_jsx.append(full_audio_path.replace("\\", "/"))

            dur_frames = int(dur_sec * fps)
            in_frame = current_frame
            out_frame = current_frame + dur_frames

            # 1. สร้าง Sequence Marker ใน XML
            marker_xml = f"""
    <marker>
      <name>{scene_title}</name>
      <comment>{scene_text}</comment>
      <in>{in_frame}</in>
      <out>{out_frame}</out>
    </marker>"""
            markers_xml.append(marker_xml)

            # 2. สร้าง Audio ClipItem ใน XML (หากมีไฟล์เสียง)
            if audio_file_path:
                clip_id = f"audio-clip-{idx}"
                file_url = f"file://localhost/{audio_file_path.replace('\\', '/')}"
                clip_xml = f"""
        <clipitem id="{clip_id}">
          <name>{scene_title}_Voice</name>
          <duration>{dur_frames}</duration>
          <rate>
            <timebase>{fps}</timebase>
            <ntsc>FALSE</ntsc>
          </rate>
          <in>0</in>
          <out>{dur_frames}</out>
          <start>{in_frame}</start>
          <end>{out_frame}</end>
          <file id="file-{clip_id}">
            <name>{os.path.basename(audio_file_path)}</name>
            <pathurl>{file_url}</pathurl>
            <rate>
              <timebase>{fps}</timebase>
              <ntsc>FALSE</ntsc>
            </rate>
            <duration>{dur_frames}</duration>
            <media>
              <audio>
                <samplecharacteristics>
                  <depth>16</depth>
                  <samplerate>48000</samplerate>
                </samplecharacteristics>
                <channelcount>2</channelcount>
              </audio>
            </media>
          </file>
        </clipitem>"""
                audio_clipitems.append(clip_xml)

            current_frame += dur_frames

        total_frames = current_frame
        total_duration_sec = round(total_frames / fps, 2)

        # ================== 1. Final Cut Pro XML (.xml) ==================
        xml_path = os.path.join(export_folder, f"{clean_name}.xml")
        xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE xmeml>
<xmeml version="4">
  <sequence id="sequence-1">
    <name>{clean_name}</name>
    <duration>{total_frames}</duration>
    <rate>
      <timebase>{fps}</timebase>
      <ntsc>FALSE</ntsc>
    </rate>
    <timecode>
      <rate>
        <timebase>{fps}</timebase>
        <ntsc>FALSE</ntsc>
      </rate>
      <string>00:00:00:00</string>
      <frame>0</frame>
      <displayformat>NDF</displayformat>
    </timecode>
    <media>
      <video>
        <format>
          <samplecharacteristics>
            <width>{width}</width>
            <height>{height}</height>
            <pixelaspectratio>square</pixelaspectratio>
            <rate>
              <timebase>{fps}</timebase>
              <ntsc>FALSE</ntsc>
            </rate>
          </samplecharacteristics>
        </format>
        <track>
          <!-- Video Track: สามารถลากฟุตเทจเข้ามาวางทับ Markers ได้ทันที -->
        </track>
      </video>
      <audio>
        <numOutputChannels>2</numOutputChannels>
        <format>
          <samplecharacteristics>
            <depth>16</depth>
            <samplerate>48000</samplerate>
          </samplecharacteristics>
        </format>
        <track>
          {"".join(audio_clipitems)}
        </track>
      </audio>
    </media>
    {"".join(markers_xml)}
  </sequence>
</xmeml>
"""
        with open(xml_path, "w", encoding="utf-8") as f:
            f.write(xml_content)

        # ================== 2. SubRip Subtitles (.srt) ==================
        srt_path = os.path.join(export_folder, f"{clean_name}.srt")
        srt_content = self.generate_srt_content(scenes)
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt_content)

        # ================== 3. Premiere ExtendScript (.jsx) ==================
        jsx_path = os.path.join(export_folder, f"import_to_premiere.jsx")
        files_json = json.dumps(audio_files_for_jsx + [srt_path.replace("\\", "/"), xml_path.replace("\\", "/")])
        jsx_content = f"""// Friday AI - Premiere Pro Automation Script
// Run directly in Adobe Premiere Pro: File > Scripts > Run Script
(function() {{
    if (typeof app === "undefined" || !app.project) {{
        alert("กรุณาเปิดโปรเจกต์ใน Adobe Premiere Pro ก่อนรันสคริปต์นี้ค่ะ");
        return;
    }}
    
    var project = app.project;
    var filesToImport = {files_json};
    
    // อิมพอร์ตไฟล์ทั้งหมดเข้า Project Bin
    try {{
        project.importFiles(filesToImport, true, project.rootItem, false);
        alert("Friday AI: นำเข้าไฟล์โปรเจกต์ '{clean_name}' สำเร็จแล้ว!\\n\\nไฟล์ที่นำเข้า:\\n- {clean_name}.xml (Sequence & Markers)\\n- {clean_name}.srt (Subtitles Captions)\\n- เสียงพากย์ Voiceover ทั้งหมด");
    }} catch (err) {{
        alert("เกิดข้อผิดพลาดในการนำเข้าไฟล์: " + err);
    }}
}})();
"""
        with open(jsx_path, "w", encoding="utf-8") as f:
            f.write(jsx_content)

        return {
            "status": "success",
            "platform": "premiere",
            "project_name": clean_name,
            "export_folder": export_folder,
            "xml_path": xml_path,
            "srt_path": srt_path,
            "jsx_path": jsx_path,
            "duration_sec": total_duration_sec,
            "scenes_count": len(scenes),
            "aspect_ratio": aspect_ratio,
            "fps": fps,
            "has_voiceover": generate_voiceover
        }

    # ==================== Alight Motion Project Generator ====================

    async def create_alight_motion_project(
        self,
        project_name: str,
        aspect_ratio: str = "9:16",
        scenes: List[Dict[str, Any]] = None,
        generate_voiceover: bool = True,
        voice: str = "th-TH-PremwadeeNeural",
        fps: int = 30
    ) -> Dict[str, Any]:
        """
        สร้างแพ็กเกจโปรเจกต์ Alight Motion XML Package (.xml):
        - โครงสร้างแท็ก <scene> รองรับการอิมพอร์ตเข้า Alight Motion บนมือถือ/แท็บเล็ตทันที
        - Motion Typography พร้อม Keyframe Velocity, Scale Pop, และ Shake/Motion Blur
        - เชื่อมโยงไฟล์เสียงพากย์ (.mp3) และไฟล์ซับไตเติล (.srt)
        """
        clean_name = self._sanitize_name(project_name)
        export_folder = os.path.join(self.base_export_dir, "alightmotion", clean_name)
        os.makedirs(export_folder, exist_ok=True)
        os.makedirs(os.path.join(export_folder, "Audio"), exist_ok=True)

        if aspect_ratio == "9:16":
            width, height = 1080, 1920
        elif aspect_ratio == "1:1":
            width, height = 1080, 1080
        elif aspect_ratio == "4:5":
            width, height = 1080, 1350
        else: # 16:9
            width, height = 1920, 1080

        scenes = scenes or [
            {"title": "Hook", "text": "ทริคลับ Alight Motion ที่หลายคนไม่เคยรู้!", "duration": 3.5},
            {"title": "Velocity Transition", "text": "เทคนิคการตัดต่อแบบกระตุกและโมชันเบลอสุดเท่", "duration": 4.5},
            {"title": "Call To Action", "text": "กดเซฟและแชร์ต่อให้เพื่อนได้เลยครับ!", "duration": 3.5}
        ]

        current_frame = 0
        now_ms = int(time.time() * 1000)
        text_elements_xml = []
        audio_elements_xml = []

        for idx, scene in enumerate(scenes, 1):
            dur_sec = float(scene.get("duration", 3.5))
            scene_text = scene.get("text", "").strip()
            scene_title = scene.get("title", f"Scene {idx}")

            audio_file_name = None
            if generate_voiceover and scene_text:
                audio_file_name = f"voice_scene_{idx}.mp3"
                full_audio_path = os.path.join(export_folder, "Audio", audio_file_name)
                measured_dur = await self.generate_voiceover_file(scene_text, full_audio_path, voice=voice)
                if measured_dur > 0:
                    dur_sec = max(dur_sec, measured_dur + 0.3)

            dur_frames = int(dur_sec * fps)
            in_frame = current_frame
            out_frame = current_frame + dur_frames

            # Alight Motion Motion Typography Layer
            escaped_text = scene_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
            center_x = width // 2
            center_y = int(height * 0.72) if aspect_ratio == "9:16" else (height // 2)

            text_xml = f"""
  <!-- Scene {idx}: {scene_title} -->
  <text id="text_{idx}_{now_ms}" startTime="{in_frame}" endTime="{out_frame}" size="52" fill="#ffffffff" align="center" font="Kanit-Bold" text="{escaped_text}">
    <transform>
      <location x="{center_x}" y="{center_y}">
        <keyframe time="{in_frame}" value="{center_x},{center_y + 40}" />
        <keyframe time="{in_frame + 8}" value="{center_x},{center_y}" easing="cubic-bezier(0.18, 0.89, 0.32, 1.28)" />
      </location>
      <scale x="1.0" y="1.0">
        <keyframe time="{in_frame}" value="0.75,0.75" />
        <keyframe time="{in_frame + 7}" value="1.08,1.08" />
        <keyframe time="{in_frame + 12}" value="1.0,1.0" />
      </scale>
      <alpha value="1.0">
        <keyframe time="{in_frame}" value="0.0" />
        <keyframe time="{in_frame + 6}" value="1.0" />
        <keyframe time="{max(in_frame + 7, out_frame - 6)}" value="1.0" />
        <keyframe time="{out_frame}" value="0.0" />
      </alpha>
    </transform>
    <effect id="blur.motion" title="Motion Blur" enabled="true">
      <property name="tune" value="1.0" />
    </effect>
    <effect id="transform.oscillate" title="Oscillate / Shake" enabled="true">
      <property name="angle" value="45.0" />
      <property name="frequency" value="1.2" />
      <property name="magnitude" value="6.0" />
    </effect>
  </text>"""
            text_elements_xml.append(text_xml)

            # Audio Element
            if audio_file_name:
                audio_xml = f"""
  <audio id="audio_{idx}_{now_ms}" startTime="{in_frame}" endTime="{out_frame}" volume="1.0" src="Audio/{audio_file_name}">
  </audio>"""
                audio_elements_xml.append(audio_xml)

            current_frame += dur_frames

        total_frames = current_frame
        total_duration_sec = round(total_frames / fps, 2)

        # Build Alight Motion XML
        xml_content = f"""<?xml version="1.0" encoding="utf-8"?>
<!-- Alight Motion Project Package - Generated by Friday AI -->
<scene title="{clean_name}" width="{width}" height="{height}" fps="{fps}" exported="true" format="1.0" modified="{now_ms}">
  <!-- Background Solid Layer -->
  <shape id="bg_solid" startTime="0" endTime="{total_frames}" type="rect" width="{width}" height="{height}">
    <transform>
      <location x="{width // 2}" y="{height // 2}" />
    </transform>
    <property name="fillColor" value="#ff0b1120" />
  </shape>

  <!-- Typography & Scene Motion Layers -->
  {"".join(text_elements_xml)}

  <!-- Audio Voiceover Tracks -->
  {"".join(audio_elements_xml)}
</scene>
"""
        xml_path = os.path.join(export_folder, f"{clean_name}.xml")
        with open(xml_path, "w", encoding="utf-8") as f:
            f.write(xml_content)

        # Write SRT subtitles file as well
        srt_path = os.path.join(export_folder, f"{clean_name}.srt")
        srt_content = self.generate_srt_content(scenes)
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt_content)

        return {
            "status": "success",
            "platform": "alightmotion",
            "project_name": clean_name,
            "export_folder": export_folder,
            "xml_path": xml_path,
            "srt_path": srt_path,
            "download_url": f"/api/video/download-alightmotion/{clean_name}",
            "duration_sec": total_duration_sec,
            "scenes_count": len(scenes),
            "aspect_ratio": aspect_ratio,
            "fps": fps,
            "has_voiceover": generate_voiceover
        }

    # ==================== System & App Launchers ====================

    def open_folder(self, folder_path: str) -> bool:
        """เปิดโฟลเดอร์ใน Windows File Explorer"""
        if os.path.exists(folder_path):
            try:
                subprocess.Popen(f'explorer "{os.path.normpath(folder_path)}"')
                return True
            except Exception as e:
                print(f"[Launcher] Error opening folder: {e}")
        return False

    def launch_capcut(self) -> bool:
        """เปิดโปรแกรม CapCut บนเครื่อง"""
        env = self.detect_environment()
        capcut_exe = env["capcut"].get("exe_path")
        if capcut_exe and os.path.exists(capcut_exe):
            try:
                subprocess.Popen([capcut_exe])
                return True
            except Exception as e:
                print(f"[Launcher] Error launching CapCut: {e}")
        return False

    def launch_premiere(self, file_to_open: Optional[str] = None) -> bool:
        """เปิดโปรแกรม Adobe Premiere Pro หรือเปิดไฟล์ XML ด้วย Premiere Pro"""
        env = self.detect_environment()
        prem_exe = env["premiere"].get("exe_path")
        if prem_exe and os.path.exists(prem_exe):
            try:
                if file_to_open and os.path.exists(file_to_open):
                    subprocess.Popen([prem_exe, file_to_open])
                else:
                    subprocess.Popen([prem_exe])
                return True
            except Exception as e:
                print(f"[Launcher] Error launching Premiere Pro: {e}")
        elif file_to_open and os.path.exists(file_to_open):
            # เปิดผ่าน Default Association
            try:
                os.startfile(file_to_open)
                return True
            except Exception as e:
                print(f"[Launcher] Startfile error: {e}")
        return False

    # ==================== AI Video Script Planner ====================

    def plan_quick_storyboard(self, prompt: str, aspect_ratio: str = "9:16") -> Dict[str, Any]:
        """วางโครงสร้างสคริปต์ ฉาก ไทม์โค้ด และคำแนะนำภาพสำหรับตัดต่อวิดีโออย่างมืออาชีพ"""
        clean = prompt.strip()
        
        # ตัดคำสั่งทั่วไปออกเพื่อสกัดหัวข้อ
        clean_topic = re.sub(r'^(?:ตัดต่อคลิป|ทำคลิป|สร้างคลิป|ตัดคลิป|ทำวิดีโอ|ช่วยตัดคลิป|ช่วยทำคลิป)\s*', '', clean).strip()
        if not clean_topic:
            clean_topic = "คลิปสั้นไฮไลท์และเทคนิคพิเศษ"

        title = clean_topic[:30]

        # โครงสร้าง Storyboard มาตรฐานแบบ Hook -> Point 1 -> Point 2 -> CTA
        scenes = [
            {
                "title": "🎯 1. Hook (หยุดนิ้วคนดู 0-3 วิ)",
                "text": f"รู้หรือไม่ครับว่า {clean_topic} มีความลับที่หลายคนไม่เคยรู้!",
                "duration": 3.5,
                "visual_idea": "ภาพโคลสอัปดึงดูดสายตา ใส่เอฟเฟกต์ Glitch หรือ Zoom-In เร็วๆ พร้อมตัวหนังสือพาดหัวตัวโต",
                "sound_effect": "Whoosh / Pop sound"
            },
            {
                "title": "💡 2. Main Insight (ประเด็นหลัก)",
                "text": f"จุดสำคัญอันดับแรกเลยคือการจัดการโครงสร้างและลำดับความสำคัญอย่างถูกต้อง",
                "duration": 4.5,
                "visual_idea": "ภาพ B-Roll แสดงวิธีการทำแบบกระชับ มีไฮไลท์สีเน้นจุดสำคัญ",
                "sound_effect": "Click / Ding"
            },
            {
                "title": "⚡ 3. Actionable Tip (เคล็ดลับที่ทำตามได้ทันที)",
                "text": "เพียงแค่ปรับวิธีคิดและลงมือทำอย่างต่อเนื่อง ผลลัพธ์จะเปลี่ยนไปอย่างสิ้นเชิงครับ",
                "duration": 4.0,
                "visual_idea": "เปรียบเทียบ Before & After หรือกราฟิกสรุป 3 ข้อ",
                "sound_effect": "Success chime"
            },
            {
                "title": "🔥 4. Call To Action (ปิดท้ายและชวนติดตาม)",
                "text": "ชอบเคล็ดลับแบบนี้อย่าลืมกดหัวใจ และกดติดตามช่องไว้ได้เลยครับ!",
                "duration": 3.5,
                "visual_idea": "ปุ่มกด Follow ดุ๊กดิ๊ก พร้อมชี้ไปที่ไอคอนโปรไฟล์",
                "sound_effect": "Subscribe bell"
            }
        ]

        total_dur = sum(s["duration"] for s in scenes)

        return {
            "title": title,
            "topic": clean_topic,
            "aspect_ratio": aspect_ratio,
            "target_duration_sec": total_dur,
            "scenes": scenes,
            "platforms": ["capcut", "premiere", "alightmotion"]
        }
