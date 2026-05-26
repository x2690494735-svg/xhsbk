import os
import sys
import traceback

FROZEN = getattr(sys, "frozen", False)
ROOT = os.path.dirname(sys.executable) if FROZEN else os.path.dirname(__file__)

LOG = os.path.join(ROOT, "error.log")

try:
    import asyncio
    import json
    from datetime import datetime
    from pathlib import Path

    import yaml
    from flask import Flask, jsonify, render_template, request

    from xhs.crawler import Crawler
    from xhs.storage import Store
except Exception:
    with open(LOG, "w", encoding="utf-8") as f:
        f.write(traceback.format_exc())
    print(f"启动失败，详情见 {LOG}")
    sys.exit(1)

app = Flask(
    __name__,
    template_folder=os.path.join(ROOT, "templates"),
)
cfg_path = os.path.join(ROOT, "config.yaml")
data_dir = os.path.join(ROOT, "data")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/crawl", methods=["POST"])
def crawl():
    crawler = Crawler(cfg_path)
    try:
        notes = asyncio.run(crawler.run())
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "notes": []})

    store = Store(data_dir)
    path = store.save(notes, label="hot")
    ranked = sorted(notes, key=lambda n: n.get("likes", 0), reverse=True)

    return jsonify({
        "ok": True,
        "path": path,
        "total": len(ranked),
        "notes": ranked,
    })


@app.route("/api/history")
def history():
    store = Store(data_dir)
    files = sorted(store.dir.glob("*.json"), reverse=True)[:50]
    result = []
    for f in files:
        stat = f.stat()
        result.append({
            "name": f.stem,
            "time": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "size": stat.st_size,
        })
    return jsonify(result)


@app.route("/api/history/<name>")
def history_detail(name):
    store = Store(data_dir)
    path = store.dir / f"{name}.json"
    if not path.exists():
        return jsonify({"ok": False, "error": "文件不存在"})
    with open(path, "r", encoding="utf-8") as f:
        notes = json.load(f)
    ranked = sorted(notes, key=lambda n: n.get("likes", 0), reverse=True)
    return jsonify({"ok": True, "notes": ranked})


@app.route("/api/config", methods=["GET", "POST"])
def config():
    if request.method == "GET":
        with open(cfg_path, "r", encoding="utf-8") as f:
            return jsonify(yaml.safe_load(f))
    else:
        data = request.get_json()
        with open(cfg_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
        return jsonify({"ok": True})


if __name__ == "__main__":
    try:
        print("小红书热点收集器 -> http://127.0.0.1:5000")
        app.run(debug=False, port=5000)
    except Exception:
        with open(LOG, "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        print(f"运行失败，详情见 {LOG}")
        sys.exit(1)
