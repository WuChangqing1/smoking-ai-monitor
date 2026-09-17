"""轮次 1 基础接口测试。

运行：conda activate smoking && cd backend && pytest -q
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok() -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "smoking-monitor-api"


def test_meta_matches_reference_documents() -> None:
    """元信息必须与原始资料口径一致（3 台雷达 + 15 台摄像头 = 18 台设备，7 个点位）。"""
    resp = client.get("/api/meta")
    assert resp.status_code == 200
    body = resp.json()

    assert body["mode"] == "simulation"
    assert body["monitor_points"] == 7
    assert body["devices"] == {"radar": 3, "camera": 15, "total": 18}
    # 原始资料：数据采集频率 10 Hz
    assert body["data_rate_hz"] == 10


def test_openapi_docs_available() -> None:
    assert client.get("/api/openapi.json").status_code == 200
