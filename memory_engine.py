"""
Friday Memory Engine
ระบบจัดเก็บและจัดการความจำของบอท Friday
- Short-Term Memory: ประวัติการสนทนาล่าสุด
- Long-Term Memory: บันทึกข้อเท็จจริง ความชอบ และข้อมูลส่วนตัวของผู้ใช้ (SQLite)
"""

import sqlite3
import re
import os
from datetime import datetime
from typing import List, Dict, Optional, Any

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "memory.db")


class MemoryEngine:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """สร้างตารางสำหรับเก็บข้อมูลความจำและบทสนทนาถ้ายังไม่มี"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # ตาราง Long-Term Memory
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL DEFAULT 'general',
                    key_concept TEXT NOT NULL,
                    content TEXT NOT NULL,
                    importance INTEGER DEFAULT 3,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # ตาราง Short-Term Conversation History
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL DEFAULT 'default',
                    role TEXT NOT NULL,
                    message TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # ตาราง Key-Value Settings
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            conn.commit()

    # ==================== Long-Term Memory ====================

    def save_memory(self, category: str, key_concept: str, content: str, importance: int = 3) -> int:
        """บันทึกหรืออัปเดตความจำระยะยาว"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # เช็คว่ามี key_concept นี้หรือยัง
            cursor.execute("SELECT id FROM memories WHERE key_concept = ?", (key_concept,))
            existing = cursor.fetchone()
            if existing:
                cursor.execute("""
                    UPDATE memories 
                    SET category = ?, content = ?, importance = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (category, content, importance, existing['id']))
                conn.commit()
                return existing['id']
            else:
                cursor.execute("""
                    INSERT INTO memories (category, key_concept, content, importance)
                    VALUES (?, ?, ?, ?)
                """, (category, key_concept, content, importance))
                conn.commit()
                return cursor.lastrowid

    def get_all_memories(self) -> List[Dict[str, Any]]:
        """ดึงรายการความจำทั้งหมด"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM memories ORDER BY importance DESC, updated_at DESC")
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def delete_memory(self, memory_id: int) -> bool:
        """ลบข้อมูลความจำตาม ID"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            conn.commit()
            return cursor.rowcount > 0

    def clear_all_memories(self) -> None:
        """ล้างความจำทั้งหมด"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM memories")
            conn.commit()

    def search_memories(self, query: str) -> List[Dict[str, Any]]:
        """ค้นหาความจำที่ตรงกับข้อความคำค้นหา"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            search_param = f"%{query}%"
            cursor.execute("""
                SELECT * FROM memories 
                WHERE key_concept LIKE ? OR content LIKE ? OR category LIKE ?
                ORDER BY importance DESC
            """, (search_param, search_param, search_param))
            return [dict(r) for r in cursor.fetchall()]

    def format_memories_for_prompt(self) -> str:
        """แปลงความจำทั้งหมดเป็นแฟ้มประวัติเชิงลึก (User Dossier) สำหรับใส่ใน System Prompt ของ Friday"""
        memories = self.get_all_memories()
        if not memories:
            return "ยังไม่มีข้อมูลความจำระยะยาวเกี่ยวกับผู้ใช้ในขณะนี้"

        lines = ["=== 🧠 แฟ้มข้อมูลความจำระยะยาวเกี่ยวกับผู้ใช้ (User Dossier) ==="]
        lines.append("Friday ต้องนำข้อมูลเหล่านี้มาเชื่อมโยงในการสนทนาอย่างแนบเนียน แสดงความใส่ใจ เสมือนผู้ช่วยที่รู้จักคุณเป็นอย่างดี:")
        
        category_map = {
            'profile': '👤 ข้อมูลตัวตน/ชื่อ',
            'preference': '❤️ สิ่งที่ชอบ/ไม่ชอบ/รสนิยม',
            'work': '💼 การงาน/ทักษะ/โปรเจกต์',
            'instruction': '📌 ข้อตกลง/คำสั่งพิเศษที่ต้องปฏิบัติตาม',
            'general': '💡 ข้อมูลสำคัญอื่นๆ'
        }
        
        # จัดกลุ่มความจำตามหมวดหมู่
        grouped = {}
        for m in memories:
            cat = m['category']
            grouped.setdefault(cat, []).append(m)
            
        for cat, items in grouped.items():
            cat_title = category_map.get(cat, '📝 บันทึก')
            lines.append(f"\n[{cat_title}]")
            for item in items:
                lines.append(f"• {item['key_concept']}: {item['content']}")
                
        lines.append("\n=============================================================")
        return "\n".join(lines)

    # ==================== Auto-Memory Extraction ====================

    def auto_extract_and_remember(self, user_text: str) -> List[Dict[str, str]]:
        """
        ตรวจจับข้อมูลสำคัญจากข้อความของผู้ใช้โดยอัตโนมัติแล้วบันทึกลงความจำ
        รองรับการบอกชื่อ, ความชอบ, อาชีพ, การเรียน, โปรเจกต์, ทักษะ, คำสั่งพิเศษ
        """
        extracted = []
        text = user_text.strip()

        # 1. การบอกชื่อ
        is_question = bool(re.search(r'(?:ชื่อ\s*(?:อะไร|ใคร)|ไหม|มั้ย|หรือเปล่า|หรือไม่|รึเปล่า|\?)', text))
        if not is_question:
            name_match = re.search(r'(?:ผม|ฉัน|เรา|หนู|กู)?\s*(?:ชื่อ|เรียกผมว่า|เรียกฉันว่า|เรียกเราว่า)\s*([A-Za-zก-๙]+(?:\s+[A-Za-zก-๙]+)?)', text)
            if name_match:
                name = name_match.group(1).strip()
                name = re.split(r'\s+(?:ชอบ|ไม่ชอบ|ทำงาน|เป็น|อายุ|อยู่|และ|ครับ|ค่ะ|นะ)', name)[0].strip()
                name = re.sub(r'(?:ครับ|ค่ะ|นะ|จ๊ะ|จ้า|เน้อ|อะ)$', '', name).strip()
                if 2 <= len(name) <= 25 and name not in ["อะไร", "ใคร", "ไหน", "อะไรนะ"]:
                    self.save_memory("profile", "ชื่อผู้ใช้", name, importance=5)
                    extracted.append({"key": "ชื่อผู้ใช้", "value": name, "category": "profile"})

        # 2. สิ่งที่ชอบ
        like_match = re.search(r'(?:ผม|ฉัน|เรา|หนู)?\s*ชอบ(?:\s*กิน|\s*ดื่ม|\s*ทำ|\s*ดู)?\s*([^.,!?\n]+)', text)
        if like_match and not re.search(r'(?:ไหม|มั้ย|หรือเปล่า|หรือไม่)', text):
            like_item = like_match.group(1).strip()
            like_item = re.sub(r'(?:มาก|ที่สุด|เลย|ครับ|ค่ะ|นะ).*$', '', like_item).strip()
            if 2 <= len(like_item) <= 40:
                self.save_memory("preference", f"สิ่งที่ชอบ ({like_item})", f"ผู้ใช้ชอบ {like_item}", importance=4)
                extracted.append({"key": f"สิ่งที่ชอบ ({like_item})", "value": f"ชอบ {like_item}", "category": "preference"})

        # 3. สิ่งที่ไม่ชอบ
        dislike_match = re.search(r'(?:ผม|ฉัน|เรา|หนู)?\s*(?:ไม่ชอบ|เกลียด)\s*([^.,!?\n]+)', text)
        if dislike_match and not re.search(r'(?:ไหม|มั้ย|หรือเปล่า|หรือไม่)', text):
            dislike_item = dislike_match.group(1).strip()
            dislike_item = re.sub(r'(?:มาก|ที่สุด|เลย|ครับ|ค่ะ|นะ).*$', '', dislike_item).strip()
            if 2 <= len(dislike_item) <= 40:
                self.save_memory("preference", f"สิ่งที่ไม่ชอบ ({dislike_item})", f"ผู้ใช้ไม่ชอบ {dislike_item}", importance=4)
                extracted.append({"key": f"สิ่งที่ไม่ชอบ ({dislike_item})", "value": f"ไม่ชอบ {dislike_item}", "category": "preference"})

        # 4. อาชีพ / การทำงาน / ทักษะ
        job_match = re.search(r'(?:ผม|ฉัน|เรา)?\s*(?:ทำงานเป็น|เป็น|ทำอาชีพ)\s*([A-Za-zก-๙\s]{2,30})', text)
        if job_match and not re.search(r'(?:ไหม|มั้ย|หรือเปล่า|หิว|เหนื่อย)', text):
            job = job_match.group(1).strip()
            job = re.sub(r'(?:ครับ|ค่ะ|นะ).*$', '', job).strip()
            if 2 <= len(job) <= 30 and job not in ["คน", "อะไร", "ใคร"]:
                self.save_memory("work", "อาชีพ/การทำงาน", job, importance=4)
                extracted.append({"key": "อาชีพ/การทำงาน", "value": job, "category": "work"})

        # 5. โปรเจกต์ที่กำลังทำ หรือแพลนงาน
        project_match = re.search(r'(?:กำลังทำ|พัฒนา|สร้าง|เขียนโปรเจกต์|โปรเจกต์|กำลังเรียน|ศึกษา)\s*([^.,!?\n]+)', text)
        if project_match and not re.search(r'(?:ไหม|มั้ย|หรือเปล่า|หรือไม่)', text):
            proj = project_match.group(1).strip()
            proj = re.sub(r'(?:อยู่|ครับ|ค่ะ|นะ).*$', '', proj).strip()
            if 3 <= len(proj) <= 50:
                self.save_memory("work", f"โปรเจกต์/การเรียน ({proj[:15]})", f"กำลังทำหรือสนใจ: {proj}", importance=4)
                extracted.append({"key": "โปรเจกต์/การเรียน", "value": proj, "category": "work"})

        # 6. คำสั่งพิเศษ / ช่วยจำไว้ว่า
        explicit_remember = re.search(r'(?:ช่วยจำว่า|จำไว้ว่า|อย่าลืมว่า|บันทึกว่า|บอกไว้ก่อนว่า)\s*(.+)', text)
        if explicit_remember:
            fact = explicit_remember.group(1).strip()
            fact = re.sub(r'(?:ด้วยนะ|ด้วย|ครับ|ค่ะ|นะ).*$', '', fact).strip()
            if len(fact) >= 3:
                self.save_memory("instruction", f"ข้อมูลที่ขอให้จำ: {fact[:15]}...", fact, importance=5)
                extracted.append({"key": "ข้อความเตือนความจำ", "value": fact, "category": "instruction"})

        return extracted

    # ==================== Short-Term Conversation History ====================

    def add_message(self, session_id: str, role: str, message: str) -> int:
        """บันทึกข้อความลงประวัติการสนทนา"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO conversation_history (session_id, role, message)
                VALUES (?, ?, ?)
            """, (session_id, role, message))
            conn.commit()
            return cursor.lastrowid

    def get_recent_history(self, session_id: str = "default", limit: int = 12) -> List[Dict[str, str]]:
        """ดึงประวัติการสนทนาล่าสุดตามลำดับเวลา"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT role, message, timestamp FROM conversation_history
                WHERE session_id = ?
                ORDER BY id DESC LIMIT ?
            """, (session_id, limit))
            rows = cursor.fetchall()
            # กลับลำดับให้เก่าสุดขึ้นก่อน
            return [{"role": r["role"], "message": r["message"], "timestamp": r["timestamp"]} for r in reversed(rows)]

    def clear_history(self, session_id: str = "default") -> None:
        """ล้างประวัติการสนทนาของเซสชัน"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM conversation_history WHERE session_id = ?", (session_id,))
            conn.commit()

    # ==================== Settings Store ====================

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """อ่านค่าคอนฟิก"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row['value'] if row else default

    def set_setting(self, key: str, value: str) -> None:
        """บันทึกค่าคอนฟิก"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """, (key, value))
            conn.commit()
