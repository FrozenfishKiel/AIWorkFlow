from __future__ import annotations

import app.main as app_main
from app.core.settings import get_settings
from app.models import ExportJobStatus, TaskStatus


def build_product_payload() -> dict[str, object]:
    return {
        "product": {
            "name": "氨基酸净澈洁面乳",
            "category": "个护清洁",
            "specifications": ["150g", "氨基酸配方", "敏感肌可用"],
            "price_range": "79-99元",
            "core_selling_points": ["温和净润", "泡沫细腻", "清洁后不紧绷"],
            "target_audience": "18-35岁女性",
            "use_scenarios": ["日常洁面", "换季维稳", "早晚护肤"],
            "promotion_notes": "夏季焕肤专题，主打温和净澈",
        },
        "task_description": "生成电商卖点文案、详情页文案和小红书种草短文案。",
    }


def test_root_acceptance_covers_product_content_generation_and_export(
    client,
    monkeypatch,
) -> None:
    def raise_task_enqueue(*args, **kwargs):
        raise RuntimeError("broker unavailable")

    def raise_export_enqueue(*args, **kwargs):
        raise RuntimeError("export broker unavailable")

    monkeypatch.setattr("app.api.routes_product_content.run_task_pipeline.delay", raise_task_enqueue)
    monkeypatch.setattr("app.api.routes_exports.run_export_job.delay", raise_export_enqueue)

    create_response = client.post("/product-content/jobs", json=build_product_payload())

    assert create_response.status_code == 201
    job = create_response.json()
    assert job["status"] == TaskStatus.COMPLETED
    assert job["product"]["name"] == "氨基酸净澈洁面乳"
    assert job["product_brief"]["summary"]
    assert job["generated_content"]["selling_points_copy"]
    assert job["generated_content"]["detail_page_copy"]
    assert job["generated_content"]["social_seed_copy"]
    assert job["generated_content"]["risk_notes"]
    assert job["reference_context"]

    export_response = client.post(
        "/exports",
        json={
            "task_id": job["id"],
            "export_type": "markdown",
        },
    )

    assert export_response.status_code == 201
    export_job = export_response.json()
    assert export_job["status"] == ExportJobStatus.COMPLETED

    export_list_response = client.get("/exports", params={"task_id": job["id"]})
    assert export_list_response.status_code == 200
    listed_exports = export_list_response.json()
    assert [item["id"] for item in listed_exports] == [export_job["id"]]

    artifact_response = client.get(f"/exports/{export_job['id']}/artifact")
    assert artifact_response.status_code == 200
    artifact_text = artifact_response.content.decode("utf-8")
    assert f"# Export for task {job['id']}" in artifact_text
    assert "电商卖点文案" in artifact_text
    assert "商品详情页文案" in artifact_text
    assert "小红书/种草短文案" in artifact_text
    assert job["generated_content"]["selling_points_copy"][0] in artifact_text
    assert job["generated_content"]["risk_notes"][0] in artifact_text


def test_root_acceptance_covers_password_login_and_product_content_flow(
    client,
    monkeypatch,
) -> None:
    monkeypatch.delenv("API_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("AUTH_LOGIN_USERNAME", "operator")
    monkeypatch.setenv("AUTH_LOGIN_PASSWORD", "open-sesame")
    monkeypatch.setenv("AUTH_SECRET_KEY", "0123456789abcdef0123456789abcdef")
    get_settings.cache_clear()
    app_main.settings = get_settings()

    config_response = client.get("/auth/config")
    assert config_response.status_code == 200
    assert config_response.json()["auth_mode"] == "password_login"

    unauthorized_create_response = client.post("/product-content/jobs", json=build_product_payload())
    assert unauthorized_create_response.status_code == 401

    login_response = client.post(
        "/auth/login",
        json={"username": "operator", "password": "open-sesame"},
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {access_token}"}

    me_response = client.get("/auth/me", headers=auth_headers)
    assert me_response.status_code == 200
    assert me_response.json()["username"] == "operator"

    def raise_task_enqueue(*args, **kwargs):
        raise RuntimeError("broker unavailable")

    def raise_export_enqueue(*args, **kwargs):
        raise RuntimeError("export broker unavailable")

    monkeypatch.setattr("app.api.routes_product_content.run_task_pipeline.delay", raise_task_enqueue)
    monkeypatch.setattr("app.api.routes_exports.run_export_job.delay", raise_export_enqueue)

    create_response = client.post(
        "/product-content/jobs",
        headers=auth_headers,
        json=build_product_payload(),
    )

    assert create_response.status_code == 201
    job = create_response.json()
    assert job["status"] == TaskStatus.COMPLETED
    assert job["generated_content"]["selling_points_copy"]
    assert job["reference_context"]

    export_response = client.post(
        "/exports",
        headers=auth_headers,
        json={
            "task_id": job["id"],
            "export_type": "structured_text",
        },
    )

    assert export_response.status_code == 201
    export_job = export_response.json()
    assert export_job["status"] == ExportJobStatus.COMPLETED

    artifact_response = client.get(
        f"/exports/{export_job['id']}/artifact",
        headers=auth_headers,
    )
    assert artifact_response.status_code == 200
    artifact_text = artifact_response.content.decode("utf-8")
    assert f"Export for task {job['id']}" in artifact_text
    assert "电商卖点文案" in artifact_text
    assert "风险提醒" in artifact_text
    assert job["generated_content"]["selling_points_copy"][0] in artifact_text
    assert job["generated_content"]["risk_notes"][0] in artifact_text
