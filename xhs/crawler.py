import asyncio
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

    async def run(self) -> list[dict]:
        all_notes: list[dict] = []

        async with async_playwright() as p:
            browser = await self._launch(p)
            context = await self._create_context(browser)
            page = await context.new_page()
            page.on("response", self._on_response)

            await self._wait_for_login(page)

            for kw in self.keywords:
                print(f"搜索关键词: {kw}")
                notes = await self._search(page, kw)
                all_notes.extend(notes)
                print(f"  -> {len(notes)} 条")

            await browser.close()

        return all_notes

    async def _launch(self, browser_type):
        channels = ["chrome", "msedge", None]
        last_error = None

        for ch in channels:
            try:
                launch_args = {
                    "headless": self.headless,
                    "args": [
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                    ],
                }
                if ch:
                    launch_args["channel"] = ch

                browser = await browser_type.chromium.launch(**launch_args)
                print(f"使用浏览器: {ch or 'chromium'}")
                return browser
            except Exception as e:
                last_error = e
                continue

        raise last_error or RuntimeError("未找到可用浏览器，请安装 Chrome 或 Edge")

    async def _create_context(self, browser):
        user_dir = Path(self.cfg["crawler"]["user_data_dir"])
        user_dir.mkdir(parents=True, exist_ok=True)
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            storage_state=(
                str(user_dir / "state.json")
                if (user_dir / "state.json").exists()
                else None
            ),
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        return context

    async def _on_response(self, response):
        url = response.url
        if "/api/sns/web/v1/search/notes" in url and response.ok:
            try:
                body = await response.json()
                items = body.get("data", {}).get("items", [])
                for item in items:
                    nc = item.get("note_card", {}) or item.get("noteCard", {})
                    if nc:
                        self.api_notes.append(self._parse_note_from_api(nc))
            except Exception:
                pass

    def _parse_note_from_api(self, nc: dict) -> dict:
        return {
            "title": nc.get("display_title", ""),
            "url": f"https://www.xiaohongshu.com/explore/{nc.get('note_id', '')}",
            "author": nc.get("user", {}).get("nickname", ""),
            "likes": int(nc.get("interact_info", {}).get("liked_count", 0)),
            "collects": int(nc.get("interact_info", {}).get("collected_count", 0)),
            "comments": int(nc.get("interact_info", {}).get("comment_count", 0)),
            "cover": nc.get("cover", {}).get("url_default", ""),
        }

    async def _wait_for_login(self, page):
        await page.goto("https://www.xiaohongshu.com/explore", timeout=self.timeout * 1000)
        await asyncio.sleep(2)

        has_login_btn = await page.query_selector(".login-btn, .login-container, [class*=login]")
        if has_login_btn:
            print("请在弹出的浏览器窗口中扫码登录小红书")
            print("等待登录中（最长 120 秒）...")
            for _ in range(120):
                await asyncio.sleep(1)
                still_login = await page.query_selector(".login-btn, .login-container, [class*=login]")
                if not still_login:
                    print("登录成功")
                    break

    async def _search(self, page, keyword: str) -> list[dict]:
        self.api_notes = []

        search_url = (
            f"https://www.xiaohongshu.com/search_result"
            f"?keyword={keyword}&source=web_search_result_notes"
        )
        await page.goto(search_url, timeout=self.timeout * 1000)
        await asyncio.sleep(3)

        for _ in range(3):
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await asyncio.sleep(1.5)

        notes = list(self.api_notes[: self.max_notes])
        for n in notes:
            n["keyword"] = keyword
        return notes
