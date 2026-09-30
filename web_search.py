"""
Friday Live Web Search Engine
โมดูลค้นหาข้อมูลสดบนอินเทอร์เน็ตแบบเรียลไทม์ (Multi-engine DuckDuckGo Fallback)
- ทำงานรวดเร็ว (< 1.5 วินาที)
- ไม่ต้องใช้ API Key ภายนอก (ฟรี 100%)
- รองรับ DuckDuckGo HTML + DuckDuckGo Lite + Instant Answer API
- ดึง Snippets, หัวข้อข่าว, และลิงก์อ้างอิงส่งต่อไปให้ AI สรุปเชิงลึก
"""

import httpx
import urllib.parse
import re
import asyncio
from html import unescape
from typing import List, Dict, Any, Optional

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

async def _search_ddg_html(query: str, max_results: int = 4) -> List[Dict[str, str]]:
    url = "https://html.duckduckgo.com/html/"
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "th-TH,th;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    results = []
    async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as client:
        resp = await client.post(url, data={"q": query}, headers=headers)
        if resp.status_code == 200:
            html = resp.text
            snippet_matches = re.findall(r'<a class="result__snippet[^"]*"[^>]*>(.*?)</a>', html, re.DOTALL)
            title_matches = re.findall(r'<a class="result__url"[^>]*href="([^"]*)"[^>]*>(.*?)</a>', html, re.DOTALL)
            heading_matches = re.findall(r'<a class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>', html, re.DOTALL)

            count = min(len(snippet_matches), max_results)
            for i in range(count):
                raw_snippet = snippet_matches[i] if i < len(snippet_matches) else ""
                clean_snippet = re.sub(r'<[^>]+>', '', raw_snippet).strip()
                clean_snippet = unescape(clean_snippet)

                link = ""
                title = ""
                if i < len(heading_matches):
                    link = heading_matches[i][0]
                    title = re.sub(r'<[^>]+>', '', heading_matches[i][1]).strip()
                    title = unescape(title)
                elif i < len(title_matches):
                    link = title_matches[i][0]
                    title = re.sub(r'<[^>]+>', '', title_matches[i][1]).strip()

                if "/l/?kh=-1&uddg=" in link:
                    parsed = urllib.parse.parse_qs(urllib.parse.urlparse(link).query)
                    if "uddg" in parsed:
                        link = parsed["uddg"][0]

                if clean_snippet and len(clean_snippet) > 8:
                    results.append({
                        "title": title or f"ข้อมูลที่เกี่ยวข้อง {i+1}",
                        "snippet": clean_snippet,
                        "url": link
                    })
    return results

async def _search_ddg_lite(query: str, max_results: int = 4) -> List[Dict[str, str]]:
    url = "https://lite.duckduckgo.com/lite/"
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "th-TH,th;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    results = []
    async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
        resp = await client.post(url, data={"q": query}, headers=headers)
        if resp.status_code == 200:
            html = resp.text
            # Rows in lite: class="result-link" and class="result-snippet"
            links = re.findall(r'<a[^>]+class="result-link"[^>]+href="([^"]*)"[^>]*>(.*?)</a>', html, re.DOTALL)
            snippets = re.findall(r'<td[^>]+class="result-snippet"[^>]*>(.*?)</td>', html, re.DOTALL)
            count = min(len(links), len(snippets), max_results)
            for i in range(count):
                url_match = links[i][0]
                title = re.sub(r'<[^>]+>', '', links[i][1]).strip()
                snippet = re.sub(r'<[^>]+>', '', snippets[i]).strip()
                if "/l/?kh=-1&uddg=" in url_match:
                    parsed = urllib.parse.parse_qs(urllib.parse.urlparse(url_match).query)
                    if "uddg" in parsed:
                        url_match = parsed["uddg"][0]
                if snippet:
                    results.append({
                        "title": unescape(title),
                        "snippet": unescape(snippet),
                        "url": url_match
                    })
    return results

async def _search_ddg_instant(query: str) -> List[Dict[str, str]]:
    url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json&no_html=1&skip_disambig=1"
    async with httpx.AsyncClient(timeout=4.0) as client:
        resp = await client.get(url, headers={"User-Agent": USER_AGENT})
        if resp.status_code == 200:
            data = resp.json()
            abstract = data.get("AbstractText", "")
            heading = data.get("Heading", query)
            url_res = data.get("AbstractURL", "")
            if abstract:
                return [{
                    "title": heading or query,
                    "snippet": abstract,
                    "url": url_res
                }]
    return []

async def search_duckduckgo(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    ค้นหาข้อมูลสดบนอินเทอร์เน็ตแบบเรียลไทม์ มีระบบ Fallback อัตโนมัติ
    คืนค่ารายการ dict: title, snippet, url
    """
    clean_query = query.strip()
    if not clean_query:
        return []

    # 1. ลอง HTML Engine ก่อน
    try:
        results = await _search_ddg_html(clean_query, max_results=max_results)
        if results:
            return results
    except Exception as e:
        print(f"[WebSearch] HTML search failed: {e}")

    # 2. ลอง Lite Engine
    try:
        results = await _search_ddg_lite(clean_query, max_results=max_results)
        if results:
            return results
    except Exception as e:
        print(f"[WebSearch] Lite search failed: {e}")

    # 3. ลอง Instant Answer API
    try:
        results = await _search_ddg_instant(clean_query)
        if results:
            return results
    except Exception as e:
        print(f"[WebSearch] Instant API failed: {e}")

    return []

def format_search_results_for_prompt(query: str, results: List[Dict[str, str]]) -> str:
    """จัดฟอร์แมตผลการค้นหาเว็บเพื่อเสริมใน System Prompt หรือ Message"""
    if not results:
        return ""
        
    lines = [f"=== ข้อมูลสดจากการค้นหาอินเทอร์เน็ตล่าสุดสำหรับ: '{query}' ==="]
    for idx, r in enumerate(results, 1):
        title = r.get('title', 'แหล่งข้อมูล')
        snippet = r.get('snippet', '')
        url = r.get('url', '')
        link_str = f" (ลิงก์: {url})" if url else ""
        lines.append(f"[{idx}] {title}{link_str}\nสาระสำคัญ: {snippet}")
    lines.append("=============================================================")
    lines.append("คำแนะนำ: นำข้อมูลล่าสุดข้างต้นไปตอบอย่างแม่นยำ ลึกซึ้ง และอ้างอิงแหล่งที่มาด้วยลิงก์ Markdown [ชื่อแหล่งข้อมูล](URL) เมื่อเหมาะสม")
    return "\n\n".join(lines)
