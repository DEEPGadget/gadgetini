#!/usr/bin/env python3
"""
dg5R Dashboard dev workflow tool.

Usage:
  python3 build.py extract   # JSON → parse to html onInit onRender css (Use this first to get individual files for editing)
  python3 build.py build     # Individual files → JSON (Run this after editing the files to update the dashboard JSON)
"""

import json
import sys
from pathlib import Path

DASHBOARD_JSON = Path(__file__).parent.parent / "dg5R_dashboard.json"
DEV_DIR = Path(__file__).parent

PANELS = {
    2: {
        "name": "server_overview",
        "fields": {"html": "html.html", "css": "style.css", "onRender": "onRender.js", "onInit": "onInit.js"},
    },
    5: {
        "name": "cooling_health",
        "fields": {"html": "html.html", "css": "style.css", "onRender": "onRender.js", "onInit": "onInit.js"},
    },
    6: {
        "name": "compute_health",
        "fields": {"html": "html.html", "css": "style.css", "onRender": "onRender.js", "onInit": "onInit.js"},
    },
    7: {
        "name": "network_health",
        "fields": {"html": "html.html", "css": "style.css", "onRender": "onRender.js", "onInit": "onInit.js"},
    },
}


def panel_dir(panel_id: int, name: str) -> Path:
    return DEV_DIR / "panels" / f"{panel_id:02d}_{name}"


def extract():
    with open(DASHBOARD_JSON, encoding="utf-8") as f:
        dashboard = json.load(f)

    panel_map = {p["id"]: p for p in dashboard["panels"] if "options" in p}

    for pid, cfg in PANELS.items():
        if pid not in panel_map:
            print(f"[WARN] Panel {pid} not found")
            continue

        options = panel_map[pid].get("options", {})
        out_dir = panel_dir(pid, cfg["name"])
        out_dir.mkdir(parents=True, exist_ok=True)

        for field, filename in cfg["fields"].items():
            content = options.get(field, "")
            (out_dir / filename).write_text(content, encoding="utf-8")
            print(f"  extracted → panels/{pid:02d}_{cfg['name']}/{filename}")



def build():
    with open(DASHBOARD_JSON, encoding="utf-8") as f:
        dashboard = json.load(f)

    panel_map = {p["id"]: p for p in dashboard["panels"] if "options" in p}

    for pid, cfg in PANELS.items():
        if pid not in panel_map:
            print(f"[WARN] Panel {pid} not found")
            continue

        out_dir = panel_dir(pid, cfg["name"])
        options = panel_map[pid]["options"]

        for field, filename in cfg["fields"].items():
            file_path = out_dir / filename
            if not file_path.exists():
                print(f"[WARN] {file_path.relative_to(DEV_DIR)} not found, skipped")
                continue
            options[field] = file_path.read_text(encoding="utf-8")
            print(f"  loaded ← panels/{pid:02d}_{cfg['name']}/{filename}")

    with open(DASHBOARD_JSON, "w", encoding="utf-8") as f:
        json.dump(dashboard, f, indent=2, ensure_ascii=False)
        f.write("\n")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("extract", "build"):
        print(__doc__)
        sys.exit(1)

    {"extract": extract, "build": build}[sys.argv[1]]()
