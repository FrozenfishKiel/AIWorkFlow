from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DIR = REPO_ROOT / ".runtime-real-chain"
API_ROOT = REPO_ROOT / "apps" / "api"

if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

os.environ["APP_RUNTIME_DIR"] = str(RUNTIME_DIR)
os.environ["TASK_GENERATION_PROVIDER"] = "deepseek"
os.environ["RETRIEVAL_PROFILE_PROVIDER"] = "deepseek"
os.environ["DEEPSEEK_TIMEOUT_SECONDS"] = "90"
os.environ["CELERY_RESULT_BACKEND"] = "cache+memory://"

from app.main import app  # noqa: E402


CASES = [
    {
        "label": "黑咖啡浓缩液",
        "payload": {
            "product": {
                "name": "黑咖啡浓缩液",
                "category": "冲调饮品",
                "specifications": ["30ml*7条", "冷水即溶", "便携小袋装"],
                "price_range": "39-49元",
                "core_selling_points": ["冷水即溶", "0蔗糖", "便携提神", "黑咖风味纯粹"],
                "target_audience": "通勤族、学生党、需要控糖提神的人群",
                "use_scenarios": ["早八通勤", "午后犯困", "加班复习", "出差随身"],
                "promotion_notes": "夏季提神专题，主打低负担快冲快喝",
            },
            "task_description": "生成电商卖点文案、详情页文案和种草短文案，重点突出便携提神、冷水即溶和低负担。",
        },
    },
    {
        "label": "便携挂脖小风扇",
        "payload": {
            "product": {
                "name": "便携挂脖小风扇",
                "category": "便携小家电",
                "specifications": ["三档风力", "Type-C充电", "约180g"],
                "price_range": "59-89元",
                "core_selling_points": ["解放双手", "轻量不压脖", "外出随身降温"],
                "target_audience": "通勤族、学生党、易闷热人群",
                "use_scenarios": ["地铁通勤", "户外排队", "午休散步"],
                "promotion_notes": "夏日出行清凉专场",
            },
            "task_description": "生成详情页文案和种草短文案，重点强调通勤降温、轻量佩戴和不占手。",
        },
    },
    {
        "label": "宠物除味喷雾-弱输入",
        "payload": {
            "product": {
                "name": "宠物除味喷雾",
                "category": "宠物清洁",
                "specifications": ["300ml"],
                "price_range": "29-39元",
                "core_selling_points": ["日常除味"],
                "target_audience": "",
                "use_scenarios": [],
                "promotion_notes": "",
            },
            "task_description": "写种草文案，别太夸张。",
        },
    },
]


def main() -> int:
    client = TestClient(app)
    results: list[dict[str, object]] = []

    for case in CASES:
        started = time.perf_counter()
        response = client.post("/product-content/jobs", json=case["payload"])
        elapsed_seconds = round(time.perf_counter() - started, 2)
        payload = response.json()
        diagnostics = payload.get("diagnostics") or {}
        generated_content = payload.get("generated_content") or {}
        results.append(
            {
                "label": case["label"],
                "status_code": response.status_code,
                "elapsed_seconds": elapsed_seconds,
                "status": payload.get("status"),
                "error_message": payload.get("error_message"),
                "selected_titles": diagnostics.get("selected_titles"),
                "weak_retrieval": diagnostics.get("weak_retrieval"),
                "input_alerts": payload.get("input_alerts"),
                "risk_notes": generated_content.get("risk_notes"),
                "selling_points_copy": generated_content.get("selling_points_copy"),
                "detail_page_copy": generated_content.get("detail_page_copy"),
                "social_seed_copy": generated_content.get("social_seed_copy"),
            }
        )

    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    output_path = RUNTIME_DIR / "manual-real-chain-probe-results.json"
    output_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
