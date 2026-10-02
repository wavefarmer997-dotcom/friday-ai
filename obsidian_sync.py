r"""
Friday Obsidian Sync Module
บันทึกประวัติการสนทนาและซิงค์ความจำลง Obsidian Vault (D:\ob\WIKI) แบบอัตโนมัติ Real-time
พร้อมระบบ Git Auto-Commit & Auto-Push ขึ้น GitHub อัตโนมัติทุกครั้งที่เขียนเสร็จ
"""

import os
import glob
import shutil
import threading
import subprocess
from datetime import datetime
from typing import List, Dict, Any, Optional

import platform

# ตรวจสอบ OS: บน Linux/Cloud (Render) ให้ fallback เป็น ./obsidian_vault
_is_windows = platform.system() == "Windows"
DEFAULT_VAULT_PATH = r"D:\ob\WIKI" if _is_windows else os.path.join(os.path.dirname(__file__), "obsidian_vault")



def safe_log(msg: str):
    """พิมพ์ log อย่างปลอดภัย ไม่ให้ติดปัญหา Windows charmap/cp1252 UnicodeEncodeError"""
    try:
        print(msg)
    except Exception:
        try:
            print(msg.encode("ascii", errors="replace").decode("ascii"))
        except Exception:
            pass



def find_git_binary() -> Optional[str]:
    """ค้นหาไฟล์ executable ของ Git ทั้งจาก PATH และ GitHub Desktop"""
    git_on_path = shutil.which("git")
    if git_on_path:
        return git_on_path

    candidates = [
        os.path.expandvars(r"%LOCALAPPDATA%\GitHubDesktop\app-*\resources\app\git\cmd\git.exe"),
        r"C:\Program Files\Git\cmd\git.exe",
        r"C:\Program Files (x86)\Git\cmd\git.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Git\cmd\git.exe"),
    ]
    for pattern in candidates:
        matches = glob.glob(pattern)
        if matches:
            return matches[-1]
    return None


def get_windows_github_credentials() -> tuple[str, str]:
    """ดึงข้อมูลล็อกอิน GitHub (Username, OAuth Token) จาก Environment Variables หรือ Windows Credential Manager ของ GitHub Desktop"""
    # 1. ตรวจสอบจาก Environment Variables ก่อน (เหมาะสำหรับโฮสติ้ง Render / Docker / Linux)
    env_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    env_user = os.environ.get("GITHUB_USER") or os.environ.get("GH_USER") or ""
    if env_token:
        return env_user, env_token

    # 2. ถ้าไม่ได้อยู่บน Windows ให้ข้ามการเรียก Windows Credential Manager
    if os.name != 'nt':
        return "", ""

    try:
        import ctypes
        import ctypes.wintypes

        class CREDENTIAL(ctypes.Structure):
            _fields_ = [
                ('Flags', ctypes.wintypes.DWORD),
                ('Type', ctypes.wintypes.DWORD),
                ('TargetName', ctypes.wintypes.LPWSTR),
                ('Comment', ctypes.wintypes.LPWSTR),
                ('LastWritten', ctypes.wintypes.FILETIME),
                ('CredentialBlobSize', ctypes.wintypes.DWORD),
                ('CredentialBlob', ctypes.POINTER(ctypes.c_byte)),
                ('Persist', ctypes.wintypes.DWORD),
                ('AttributeCount', ctypes.wintypes.DWORD),
                ('Attributes', ctypes.c_void_p),
                ('TargetAlias', ctypes.wintypes.LPWSTR),
                ('UserName', ctypes.wintypes.LPWSTR),
            ]

        advapi32 = ctypes.windll.advapi32
        count = ctypes.wintypes.DWORD()
        pcreds = ctypes.POINTER(ctypes.POINTER(CREDENTIAL))()

        for pattern in ('GitHub*', 'git:https://github.com*'):
            if advapi32.CredEnumerateW(pattern, 0, ctypes.byref(count), ctypes.byref(pcreds)):
                for i in range(count.value):
                    cred = pcreds[i].contents
                    if cred.CredentialBlob and cred.CredentialBlobSize > 0:
                        blob = ctypes.string_at(cred.CredentialBlob, cred.CredentialBlobSize)
                        token = blob.decode('utf-8', errors='ignore').strip()
                        user = cred.UserName or ""
                        if token.startswith(('gho_', 'ghp_', 'github_pat_')) or len(token) >= 20:
                            advapi32.CredFree(pcreds)
                            return user, token
                advapi32.CredFree(pcreds)
    except Exception as e:
        safe_log(f"[ObsidianSync] Credential lookup warning: {e}")
    return "", ""



class ObsidianSync:
    def __init__(
        self,
        vault_path: str = DEFAULT_VAULT_PATH,
        enabled: bool = True,
        github_sync_enabled: bool = True,
        github_remote_url: str = ""
    ):
        self.vault_path = vault_path
        self.enabled = enabled
        self.github_sync_enabled = github_sync_enabled
        self.github_remote_url = github_remote_url
        self.git_bin = find_git_binary()
        self.last_git_status = "กำลังตรวจสอบสถานะ..."
        self.last_git_time = ""
        self._git_lock = threading.Lock()

        # เริ่มต้นตั้งค่า Git ใน Vault ถ้ายังไม่มี
        self._init_git_vault()

    def _get_git_env(self) -> Dict[str, str]:
        """เตรียม Environment Variables สำหรับรัน Git แบบ Background ไม่มีหน้าต่างเด้งกวน"""
        env = os.environ.copy()
        if self.git_bin:
            git_dir = os.path.dirname(self.git_bin)
            env["PATH"] = git_dir + os.pathsep + env.get("PATH", "")
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["GCM_INTERACTIVE"] = "never"
        return env

    def is_available(self) -> bool:
        """ตรวจสอบว่าโฟลเดอร์ Vault มีอยู่จริงและสามารถเข้าถึงได้หรือไม่"""
        try:
            # ถ้าอยู่บน Linux/Render แต่ path เป็นไดรฟ์ Windows (เช่น D:\...) ให้ถือว่าไม่มี
            if os.name != 'nt' and len(self.vault_path) > 1 and self.vault_path[1] == ':':
                return False
            return os.path.exists(self.vault_path) and os.path.isdir(self.vault_path)
        except Exception:
            return False

    def _init_git_vault(self):
        """ตรวจสอบและเริ่มต้นระบบ Git Repo ในโฟลเดอร์ Vault"""
        if not self.git_bin or not self.is_available():
            return


        env = self._get_git_env()
        try:
            git_dir = os.path.join(self.vault_path, ".git")
            if not os.path.exists(git_dir):
                subprocess.run([self.git_bin, "init", "-b", "main", self.vault_path], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, check=True)

            # ตรวจสอบ .gitignore สำหรับ Obsidian
            gitignore_path = os.path.join(self.vault_path, ".gitignore")
            if not os.path.exists(gitignore_path):
                with open(gitignore_path, "w", encoding="utf-8") as f:
                    f.write(".obsidian/workspace.json\n.obsidian/workspace-mobile.json\n.obsidian/cache/\n.trash/\n")

            # ตรวจสอบ user.name และ user.email
            name_check = subprocess.run([self.git_bin, "-C", self.vault_path, "config", "user.name"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
            if not name_check.stdout.strip():
                subprocess.run([self.git_bin, "-C", self.vault_path, "config", "user.name", "Friday Bot"], check=True, env=env)
                subprocess.run([self.git_bin, "-C", self.vault_path, "config", "user.email", "friday@bot.local"], check=True, env=env)

            # ตั้งค่า Remote URL ถ้ามีการระบุ
            if self.github_remote_url:
                self.set_remote_url(self.github_remote_url)
            else:
                current_rem = self.get_remote_url()
                if current_rem:
                    self.github_remote_url = current_rem
            self.last_git_status = "พร้อมใช้งาน"
        except Exception as e:
            safe_log(f"[ObsidianSync] Init git repo warning: {e}")
            self.last_git_status = f"Init warning: {str(e)[:60]}"

    def _get_authenticated_url(self, raw_url: str) -> str:
        """แปลง URL ให้มี Authentication Token จาก Windows Credential Manager เพื่อ push ได้ 100%"""
        clean_url = raw_url.strip()
        if not clean_url:
            return ""
        # ถ้ามี token ฝังอยู่ใน URL อยู่แล้ว
        if "@github.com" in clean_url:
            return clean_url

        user, token = get_windows_github_credentials()
        if token and "github.com" in clean_url:
            # แทนที่ https://github.com/ ด้วย https://user:token@github.com/
            auth_prefix = f"https://{user}:{token}@github.com/" if user else f"https://{token}@github.com/"
            return clean_url.replace("https://github.com/", auth_prefix)
        return clean_url

    def set_remote_url(self, remote_url: str) -> bool:
        """ตั้งค่าหรืออัปเดต GitHub Remote URL (origin)"""
        git = self.git_bin or find_git_binary()
        if not git or not remote_url:
            return False
        clean_url = remote_url.strip()
        auth_url = self._get_authenticated_url(clean_url)
        env = self._get_git_env()
        try:
            remotes = subprocess.run([git, "-C", self.vault_path, "remote"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
            if "origin" in remotes.stdout:
                subprocess.run([git, "-C", self.vault_path, "remote", "set-url", "origin", auth_url], encoding="utf-8", errors="replace", env=env, check=True)
            else:
                subprocess.run([git, "-C", self.vault_path, "remote", "add", "origin", auth_url], encoding="utf-8", errors="replace", env=env, check=True)
            self.github_remote_url = clean_url
            return True
        except Exception as e:
            print(f"[ObsidianSync] Error setting remote: {e}")
            return False

    def get_remote_url(self) -> str:
        """ดึง GitHub Remote URL ปัจจุบัน (ซ่อน Token เพื่อความปลอดภัย)"""
        git = self.git_bin or find_git_binary()
        if not git:
            return ""
        try:
            env = self._get_git_env()
            r = subprocess.run([git, "-C", self.vault_path, "remote", "get-url", "origin"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
            if r.returncode == 0:
                raw = r.stdout.strip()
                # ซ่อน token ออกจาก URL ตอนแสดงผล
                import re
                clean = re.sub(r"https://[^@]+@github\.com", "https://github.com", raw)
                return clean
            return ""
        except Exception:
            return ""

    def get_git_info(self) -> Dict[str, Any]:
        """ตรวจสอบสถานะ Git และ Remote"""
        git = self.git_bin or find_git_binary()
        has_git = bool(git and os.path.exists(os.path.join(self.vault_path, ".git")))
        remote_url = self.get_remote_url() if has_git else ""
        user, token = get_windows_github_credentials()
        return {
            "has_git": has_git,
            "git_path": git or "",
            "has_remote": bool(remote_url),
            "remote_url": remote_url,
            "has_credentials": bool(token),
            "github_sync_enabled": self.github_sync_enabled,
            "last_git_status": self.last_git_status,
            "last_git_time": self.last_git_time
        }

    def push_to_github_background(self, commit_msg: Optional[str] = None):
        """รัน Commit & Push ไปยัง GitHub ใน Background Thread ไม่ให้รบกวนการคุย"""
        if not self.github_sync_enabled:
            return
        t = threading.Thread(target=self._git_commit_and_push, args=(commit_msg,), daemon=True)
        t.start()

    def _git_commit_and_push(self, commit_msg: Optional[str] = None) -> bool:
        """กระบวนการ Git add, commit, และ push ขึ้น GitHub (Thread-safe และไม่ค้าง)"""
        git = self.git_bin or find_git_binary()
        if not git:
            self.last_git_status = "ไม่พบโปรแกรม Git ในเครื่อง"
            return False

        env = self._get_git_env()

        with self._git_lock:
            # ป้องกันปัญหา index.lock ค้าง
            lock_path = os.path.join(self.vault_path, ".git", "index.lock")
            if os.path.exists(lock_path):
                try:
                    os.remove(lock_path)
                except Exception:
                    pass

            try:
                # 1. Add all changes
                subprocess.run([git, "-C", self.vault_path, "add", "-A"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, check=True)

                # 2. Check if changes exist to commit
                st = subprocess.run([git, "-C", self.vault_path, "status", "--porcelain"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                has_new_changes = bool(st.stdout.strip())

                if has_new_changes:
                    msg = commit_msg or f"Auto-sync Friday notes: {now_str}"
                    subprocess.run([git, "-C", self.vault_path, "commit", "-m", msg], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, check=True)
                    self.last_git_time = now_str

                # 3. ตรวจสอบการเชื่อมต่อ Remote
                remotes = subprocess.run([git, "-C", self.vault_path, "remote"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
                if "origin" in remotes.stdout:
                    # ตรวจสอบและอัปเดต URL ด้วย token ล่าสุดถ้ายังไม่มี
                    origin_url = subprocess.run([git, "-C", self.vault_path, "remote", "get-url", "origin"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env).stdout.strip()
                    auth_origin = self._get_authenticated_url(origin_url)
                    if auth_origin and auth_origin != origin_url:
                        subprocess.run([git, "-C", self.vault_path, "remote", "set-url", "origin", auth_origin], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)

                    # 4. Push ขึ้น GitHub
                    push_res = subprocess.run([git, "-C", self.vault_path, "push", "-u", "origin", "main"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=30)
                    if push_res.returncode == 0:
                        if has_new_changes:
                            self.last_git_status = f"อัปโหลดสำเร็จ ({now_str})"
                        else:
                            self.last_git_status = f"ข้อมูลบน GitHub อัปเดตล่าสุดแล้ว ({now_str})"
                        self.last_git_time = now_str
                        safe_log(f"[ObsidianSync] GitHub push succeeded: {self.last_git_status}")
                        return True
                    else:
                        err_msg = (push_res.stderr.strip() or push_res.stdout.strip()).replace("\n", " ")
                        self.last_git_status = f"Push ไม่สำเร็จ: {err_msg[:80]}"
                        safe_log(f"[ObsidianSync] GitHub push failed: {err_msg}")
                        return False
                else:
                    self.last_git_status = "บันทึก Git ในเครื่องสำเร็จ (ยังไม่ได้เชื่อมต่อ Remote GitHub)"
                    return True
            except subprocess.TimeoutExpired:
                self.last_git_status = "Push หมดเวลาเชื่อมต่อ (Network timeout)"
                safe_log("[ObsidianSync] Git push timed out")
                return False
            except Exception as e:
                self.last_git_status = f"Git error: {str(e)[:80]}"
                safe_log(f"[ObsidianSync] Git commit/push error: {e}")
                return False

    def log_chat_exchange(self, session_id: str, user_text: str, assistant_text: str) -> bool:
        """บันทึกคู่คำถาม-คำตอบลงใน Daily Chat note ของ Obsidian (Chats/YYYY-MM-DD.md) และ Push ขึ้น GitHub"""
        if not self.enabled or not self.is_available():
            return False

        try:
            chats_dir = os.path.join(self.vault_path, "Chats")
            os.makedirs(chats_dir, exist_ok=True)


            now = datetime.now()
            date_str = now.strftime("%Y-%m-%d")
            time_str = now.strftime("%H:%M:%S")
            file_path = os.path.join(chats_dir, f"{date_str}.md")

            file_exists = os.path.exists(file_path)

            with open(file_path, "a", encoding="utf-8") as f:
                if not file_exists:
                    # สร้าง Frontmatter และหัวข้อประจำวัน
                    f.write(f"---\n")
                    f.write(f"title: \"บันทึกการสนทนากับ Friday - {date_str}\"\n")
                    f.write(f"date: {date_str}\n")
                    f.write(f"tags:\n")
                    f.write(f"  - chat-log\n")
                    f.write(f"  - friday\n")
                    f.write(f"  - daily-notes\n")
                    f.write(f"---\n\n")
                    f.write(f"# 💬 บันทึกการสนทนากับ Friday ({date_str})\n\n")
                    f.write(f"> [[Memories|🧠 แฟ้มความจำ (Memories)]] • เซสชัน: `{session_id}`\n\n")
                    f.write(f"---\n\n")

                # เพิ่มบล็อกการสนทนาของรอบนี้
                f.write(f"### 🕒 {time_str}\n\n")
                f.write(f"**👤 ผู้ใช้:**\n")
                f.write(f"{user_text.strip()}\n\n")
                f.write(f"**🤖 Friday:**\n")
                f.write(f"{assistant_text.strip()}\n\n")
                f.write(f"---\n\n")

            # อัปโหลดขึ้น GitHub อัตโนมัติหลังเขียนเสร็จ
            self.push_to_github_background(f"Chat log updated: {date_str} {time_str}")
            return True
        except Exception as e:
            safe_log(f"[ObsidianSync] Error writing chat log: {e}")
            return False

    def sync_memories(self, memories: List[Dict[str, Any]]) -> bool:
        """ซิงค์ข้อมูลความจำทั้งหมดจาก SQLite ลง Memories.md ใน Obsidian และ Push ขึ้น GitHub"""
        if not self.enabled or not self.is_available():
            return False

        try:
            file_path = os.path.join(self.vault_path, "Memories.md")

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            category_map = {
                'profile': ('👤 ข้อมูลตัวตน/ชื่อ', 'ข้อมูลพื้นฐาน ชื่อ และตัวตนของผู้ใช้'),
                'preference': ('❤️ สิ่งที่ชอบ/ไม่ชอบ/รสนิยม', 'ความชอบ รสนิยม อาหาร สิ่งที่ถูกใจและไม่ถูกใจ'),
                'work': ('💼 การงาน/ทักษะ/โปรเจกต์', 'งานที่ทำ โปรเจกต์ที่กำลังพัฒนา และทักษะเฉพาะทาง'),
                'instruction': ('📌 ข้อตกลง/คำสั่งพิเศษ', 'สิ่งที่ผู้ใช้กำชับให้จำ หรือแนวทางที่ต้องปฏิบัติตาม'),
                'general': ('💡 ข้อมูลสำคัญอื่นๆ', 'ข้อเท็จจริงและความรู้อื่นๆ ที่ Friday จดจำไว้')
            }

            grouped = {}
            for m in memories:
                cat = m.get('category', 'general')
                grouped.setdefault(cat, []).append(m)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"---\n")
                f.write(f"title: \"Friday User Dossier (แฟ้มความจำ)\"\n")
                f.write(f"updated: {now_str}\n")
                f.write(f"total_memories: {len(memories)}\n")
                f.write(f"tags:\n")
                f.write(f"  - friday\n")
                f.write(f"  - memory\n")
                f.write(f"  - dossier\n")
                f.write(f"---\n\n")
                f.write(f"# 🧠 แฟ้มข้อมูลความจำระยะยาว (Friday Dossier)\n\n")
                f.write(f"> 🔄 อัปเดตล่าสุด: `{now_str}` | จำนวนความจำทั้งหมด: **{len(memories)}** รายการ\n\n")

                if not memories:
                    f.write(f"_ยังไม่มีข้อมูลความจำที่ถูกบันทึกในระบบ_\n\n")
                else:
                    for cat_key, (cat_title, cat_desc) in category_map.items():
                        items = grouped.get(cat_key, [])
                        if items:
                            f.write(f"## {cat_title}\n")
                            f.write(f"_{cat_desc}_\n\n")
                            for item in items:
                                stars = "⭐" * min(max(int(item.get("importance", 3)), 1), 5)
                                f.write(f"- **{item.get('key_concept', '')}**: {item.get('content', '')} `{stars}`\n")
                            f.write(f"\n")

                    # หมวดหมู่อื่นๆ ถ้ามี
                    for cat_key, items in grouped.items():
                        if cat_key not in category_map and items:
                            f.write(f"## 📝 {cat_key.capitalize()}\n\n")
                            for item in items:
                                stars = "⭐" * min(max(int(item.get("importance", 3)), 1), 5)
                                f.write(f"- **{item.get('key_concept', '')}**: {item.get('content', '')} `{stars}`\n")
                            f.write(f"\n")

                f.write(f"---\n")
                f.write(f"> 💡 _ไฟล์นี้ถูกสร้างและซิงค์อัตโนมัติโดย Friday Chatbot_\n")

            # อัปโหลดขึ้น GitHub อัตโนมัติหลังเขียนเสร็จ
            self.push_to_github_background(f"Memories synced: {now_str}")
            return True
        except Exception as e:
            safe_log(f"[ObsidianSync] Error syncing memories: {e}")
            return False
