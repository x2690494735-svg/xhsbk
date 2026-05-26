"""浏览器爬取核心"""

import asyncio
import json
import re
from pathlib import Path

import yaml
from playwright.async_api import async_playwright


class Crawler:
    """小红书爬取器"""

    def __init__(self, config_path: str = "config.yaml"):
        with open(config_path, "r", encoding="utf-8") as f:
            self.cfg = yaml.safe_load(f)
        self.keywords = self.cfg["keywords"]
        self.max_notes = self.cfg["crawler"]["max_notes"]
        self.timeout = self.cfg["crawler"]["timeout"]
        self.headless = self.cfg["crawler"]["headless"]
        self.api_notes: list[dict] = []

    async def run(self) -> list[dict]:
        """主入口：依次搜索所有关键词，返回收集到的笔记列表"""
        all_notes: list[dict] = []

        async with async_playwright() as p:
            browser = await self._launch(p)
            context = await self._create_context(browser)
            page = await context.new_page()

            # 拦截 API 响应，采集结构化数据
            page.on("response", self._on_response)

            for kw in self.keywords:
                print(f"🔍 搜索关键词: {kw}")
                notes = await self._search(page, kw)
                all_notes.extend(notes)
                print(f"   → 采集 {len(notes)} 条")

            await browser.close()

        return all_notes

    async def _launch(self, browser_type):
        """启动浏览器，带上反检测参数"""
        return await browser_type.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )

    async def _create_context(self, browser):
        """创建持久化上下文，保留登录态"""
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
        """拦截 API 响应，提取笔记数据"""
        url = response.url
        if "/api/sns/web/v1/search/notes" in url and response.ok:
            try:
                body = await response.json()
                items = (
                    body.get("data", {})
                    .get("items", [])
                )
                for item in items:
                    nc = item.get("note_card", {}) or item.get("noteCard", {})
                    if nc:
                        self.api_notes.append(self._parse_note_from_api(nc))
            except Exception:
                pass  # 解析失败就跳过，不影响主流程

    def _parse_note_from_api(self, nc: dict) -> dict:
        """从 API 返回的 note_card 中提取字段"""
        return {
            "title": nc.get("display_title", ""),
            "url": f"https://www.xiaohongshu.com/explore/{nc.get('note_id', '')}",
            "author": nc.get("user", {}).get("nickname", ""),
            "likes": int(nc.get("interact_info", {}).get("liked_count", 0)),
            "collects": int(nc.get("interact_info", {}).get("collected_count", 0)),
            "comments": int(nc.get("interact_info", {}).get("comment_count", 0)),
            "cover": nc.get("cover", {}).get("url_default", ""),
        }

    async def _search(self, page, keyword: str) -> list[dict]:
        """搜索单个关键词，采集结果"""
        self.api_notes = []

        search_url = (
            f"https://www.xiaohongshu.com/search_result"
            f"?keyword={keyword}&source=web_search_result_notes"
        )
        await page.goto(search_url, timeout=self.timeout * 1000)
        await asyncio.sleep(3)  # 等页面渲染完

        # 滚动加载更多
        for _ in range(3):
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await asyncio.sleep(1.5)

        notes = list(self.api_notes[: self.max_notes])
        for n in notes:
            n["keyword"] = keyword
        return notes
