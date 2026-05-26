"""数据存储"""

import json
from datetime import datetime
from pathlib import Path


class Store:
    """JSON 文件存储"""

    def __init__(self, data_dir: str = "data"):
        self.dir = Path(data_dir)
        self.dir.mkdir(parents=True, exist_ok=True)

    def save(self, notes: list[dict], label: str = "") -> str:
        """保存笔记列表，返回文件路径"""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = f"{label}_{ts}.json" if label else f"{ts}.json"
        path = self.dir / name
        with open(path, "w", encoding="utf-8") as f:
            json.dump(notes, f, ensure_ascii=False, indent=2)
        return str(path)

