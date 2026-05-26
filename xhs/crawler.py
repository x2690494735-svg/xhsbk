import asyncio
import json
import os
import sys
import yaml
from pathlib import Path
from playwright.async_api import async_playwright, Browser, Page, BrowserContext

_browser: Browser | None = None
_page: Page | None = None
_context: BrowserContext | None = None
_pw = None
_state_path = None
_active_crawler: "Crawler | None" = None


async def _ensure_browser(config_path: str = "config.yaml"):
    global _browser, _page, _pw, _context, _state_path, _active_crawler

    if _page and not _page.is_closed():
        return _page

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(config_path)
    user_dir = Path(base) / cfg["crawler"]["user_data_dir"]
    user_dir.mkdir(parents=True, exist_ok=True)
    _state_path = str(user_dir / "state.json")

    _pw = await async_playwright().start()

    channels = ["chrome", "msedge", None]
    for ch in channels:
        try:
            launch_args = {
                "headless": cfg["crawler"]["headless"],
                "args": ["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            }
            if ch:
                launch_args["channel"] = ch
            _browser = await _pw.chromium.launch(**launch_args)
            print(f"使用浏览器: {ch or 'chromium'}")
            break
        except Exception:
            continue
    else:
        raise RuntimeError("未找到可用浏览器")

    loaded_state = None
    if Path(_state_path).exists():
        loaded_state = _state_path
        print(f"加载登录态: {_state_path}")

    _context = await _browser.new_context(
        viewport={"width": 1440, "height": 900},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        storage_state=loaded_state,
    )
    await _context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
    _page = await _context.new_page()

    async def _handler(response):
        if _active_crawler:
            await _active_crawler._on_response(response)

    _page.on("response", _handler)
    return _page


def _save_state():
    if _context and _state_path:
        st = _context.storage_state()
        with open(_state_path, "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False, indent=2)


async def navigate_to(url: str, config_path: str = "config.yaml"):
    page = await _ensure_browser(config_path)
    await page.goto(url, timeout=30000)


class Crawler:

    def __init__(self, config_path: str = "config.yaml"):
        with open(config_path, "r", encoding="utf-8") as f:
            self.cfg = yaml.safe_load(f)
        self.keywords = self.cfg["keywords"]
        self.max_notes = self.cfg["crawler"]["max_notes"]
        self.timeout = self.cfg["crawler"]["timeout"]
        self.api_notes: list[dict] = []

    async def run(self) -> list[dict]:
        global _active_crawler
        all_notes: list[dict] = []
        page = await _ensure_browser()
        _active_crawler = self

        await self._wait_for_login(page)
        _save_state()

        for kw in self.keywords:
            print(f"搜索关键词: {kw}")
            notes = await self._search(page, kw)
            all_notes.extend(notes)
            print(f"  -> {len(notes)} 条")

        _save_state()
        return all_notes

    async def _wait_for_login(self, page):
        await page.goto("https://www.xiaohongshu.com/explore", timeout=self.timeout * 1000)
        await asyncio.sleep(2)
        btn = await page.query_selector(".login-btn, .login-container, [class*=login]")
        if btn:
            print("请在弹出的浏览器窗口中扫码登录小红书")
            print("等待登录中（最长 120 秒）...")
            for _ in range(120):
                await asyncio.sleep(1)
                if not await page.query_selector(".login-btn, .login-container, [class*=login]"):
                    print("登录成功")
                    _save_state()
                    break

    async def _search(self, page, keyword: str) -> list[dict]:
        self.api_notes = []
        search_url = f"https://www.xiaohongshu.com/search_result?keyword={keyword}&source=web_search_result_notes"
        await page.goto(search_url, timeout=self.timeout * 1000)
        await asyncio.sleep(3)
        for _ in range(3):
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await asyncio.sleep(1.5)
        notes = list(self.api_notes[: self.max_notes])
        for n in notes:
            n["keyword"] = keyword
        return notes

    async def _on_response(self, response):
        url = response.url
        if "/api/sns/web/v1/search/notes" in url and response.ok:
            try:
                body = await response.json()
                items = body.get("data", {}).get("items", [])
                for item in items:
                    nc = item.get("note_card", {}) or item.get("noteCard", {})
                    if not nc:
                        continue
                    fid = item.get("id", "")
                    nid = nc.get("note_id") or nc.get("noteId") or fid
                    self.api_notes.append({
                        "title": nc.get("display_title", ""),
                        "url": f"https://www.xiaohongshu.com/explore/{nid}" if nid else "",
                        "author": nc.get("user", {}).get("nickname", ""),
                        "likes": int(nc.get("interact_info", {}).get("liked_count", 0)),
                        "collects": int(nc.get("interact_info", {}).get("collected_count", 0)),
                        "comments": int(nc.get("interact_info", {}).get("comment_count", 0)),
                        "cover": nc.get("cover", {}).get("url_default", ""),
                    })
            except Exception:
                pass
