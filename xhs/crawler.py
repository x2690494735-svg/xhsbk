import asyncio
import json
import os
import sys
import yaml
from pathlib import Path
from playwright.async_api import async_playwright


class Crawler:

    def __init__(self, config_path: str = "config.yaml"):
        with open(config_path, "r", encoding="utf-8") as f:
            self.cfg = yaml.safe_load(f)
        self.keywords = self.cfg["keywords"]
        self.max_notes = self.cfg["crawler"]["max_notes"]
        self.timeout = self.cfg["crawler"]["timeout"]
        self.headless = self.cfg["crawler"]["headless"]
        self.api_notes: list[dict] = []

        frozen = getattr(sys, "frozen", False)
        base = os.path.dirname(sys.executable) if frozen else os.path.dirname(config_path)
        self.state_file = str(Path(base) / self.cfg["crawler"]["user_data_dir"] / "state.json")
        Path(self.state_file).parent.mkdir(parents=True, exist_ok=True)

    async def run(self) -> list[dict]:
        all_notes: list[dict] = []

        async with async_playwright() as p:
            browser = await self._launch(p)
            context = await self._create_context(browser)
            page = await context.new_page()
            page.on("response", self._on_response)

            await self._wait_for_login(page)
            self._save_state(context)

            for kw in self.keywords:
                print(f"搜索关键词: {kw}")
                notes = await self._search(page, kw)
                all_notes.extend(notes)
                print(f"  -> {len(notes)} 条")

            need_content = [n for n in all_notes if n.get("url") and not n.get("desc")]
            if need_content:
                print(f"采集正文中（共 {len(need_content)} 篇，同页调API）...")
                for i, n in enumerate(need_content):
                    try:
                        desc = await self._fetch_detail(page, n["url"])
                        if desc:
                            n["desc"] = desc
                            print(f"  [{i+1}/{len(need_content)}] {n['title'][:25]}... OK")
                    except Exception:
                        pass
                    await asyncio.sleep(1.5)

            self._save_state(context)
            await browser.close()

        return all_notes

    async def _launch(self, browser_type):
        channels = ["chrome", "msedge", None]
        last_error = None
        for ch in channels:
            try:
                args = {
                    "headless": self.headless,
                    "args": [
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--window-position=100,50",
                        "--window-size=1200,800",
                    ],
                }
                if ch:
                    args["channel"] = ch
                browser = await browser_type.chromium.launch(**args)
                print(f"使用浏览器: {ch or 'chromium'}")
                return browser
            except Exception as e:
                last_error = e
                continue
        raise last_error or RuntimeError("未找到可用浏览器")

    async def _create_context(self, browser):
        loaded = self.state_file if os.path.exists(self.state_file) else None
        if loaded:
            print(f"加载登录态: {self.state_file}")
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            storage_state=loaded,
        )
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
        return context

    def _save_state(self, context):
        try:
            st = context.storage_state()
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(st, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    async def _wait_for_login(self, page):
        await page.bring_to_front()
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
                    break

    async def _search(self, page, keyword: str) -> list[dict]:
        await page.bring_to_front()
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

    async def _fetch_detail(self, page, url: str) -> str:
        nid = url.rstrip("/").rsplit("/", 1)[-1]
        if not nid:
            return ""

        js = """
            async (noteId) => {
                const endpoints = [
                    `/api/sns/web/v1/feed?source_note_id=${noteId}`,
                    `/api/sns/web/v1/note/${noteId}`,
                ];
                for (const ep of endpoints) {
                    try {
                        const resp = await fetch(ep, {credentials:'include'});
                        if (!resp.ok) continue;
                        const data = await resp.json();
                        if (!data.success && data.code !== 0) continue;
                        const item = data.data?.items?.[0] || data.data;
                        const nc = item?.note_card || item?.noteCard || item;
                        const desc = nc?.desc || nc?.display_content || nc?.note_desc || '';
                        if (desc) return desc;
                    } catch(e) {}
                }
                return '';
            }
        """
        try:
            result = await page.evaluate(js, nid)
            return (result or "")[:3000]
        except Exception:
            return ""

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
                    desc = (
                        nc.get("desc")
                        or nc.get("display_content")
                        or nc.get("note_desc")
                        or ""
                    )
                    self.api_notes.append({
                        "title": nc.get("display_title", ""),
                        "url": f"https://www.xiaohongshu.com/explore/{nid}" if nid else "",
                        "author": nc.get("user", {}).get("nickname", ""),
                        "likes": int(nc.get("interact_info", {}).get("liked_count", 0)),
                        "collects": int(nc.get("interact_info", {}).get("collected_count", 0)),
                        "comments": int(nc.get("interact_info", {}).get("comment_count", 0)),
                        "cover": nc.get("cover", {}).get("url_default", ""),
                        "desc": desc,
                    })
            except Exception:
                pass
