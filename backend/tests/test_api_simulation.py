"""API 契约与业务行为测试。

这里不只断言 HTTP 200，还校验：
  - 响应 schema 的字段完整性（前端依赖这些字段名，改动即破坏契约）；
  - 典型字段的取值语义（状态、等级、字段之间的关联）；
  - 启停 / 重置 / 演示场景切换的实际行为。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.services.simulation import SAMPLE_RATE_HZ, get_engine


def drive(seconds: float) -> None:
    """显式推进仿真（测试中不启动后台线程，因此需要手动驱动）。"""
    engine = get_engine()
    for _ in range(int(seconds * SAMPLE_RATE_HZ)):
        engine.tick()


# =============================================================================
# 基础接口
# =============================================================================


class TestBasicEndpoints:
    def test_health_ok(self, client: TestClient) -> None:
        resp = client.get("/api/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["service"] == "smoking-monitor-api"

    def test_meta_matches_reference_documents(self, client: TestClient) -> None:
        """元信息必须与原始资料口径一致（3 雷达 + 15 摄像机 = 18 台，7 个点位）。"""
        resp = client.get("/api/meta")
        assert resp.status_code == 200
        body = resp.json()

        assert body["mode"] == "simulation"
        assert body["monitor_points"] == 7
        assert body["devices"] == {"radar": 3, "camera": 15, "total": 18}
        assert body["data_rate_hz"] == 10

    def test_openapi_docs_available(self, client: TestClient) -> None:
        assert client.get("/api/openapi.json").status_code == 200


# =============================================================================
# /api/system/status
# =============================================================================


class TestSystemStatus:
    EXPECTED_KEYS = {"system", "ai", "radar", "video"}

    def test_schema_is_stable(self, client: TestClient) -> None:
        resp = client.get("/api/system/status")
        assert resp.status_code == 200
        body = resp.json()

        for field in (
            "ts",
            "detection_running",
            "sim_state",
            "sim_state_text",
            "uptime_hours",
            "today_warnings",
            "devices_online",
            "devices_total",
            "statuses",
        ):
            assert field in body, f"缺少字段 {field}"

        assert {item["key"] for item in body["statuses"]} == self.EXPECTED_KEYS
        for item in body["statuses"]:
            assert item["state"] in ("ok", "warn", "error", "offline")
            assert item["label"] and item["text"]

    def test_device_counts_match_hardware(self, client: TestClient) -> None:
        body = client.get("/api/system/status").json()
        assert body["devices_total"] == 18
        assert body["devices_online"] == 18

    def test_status_consistent_with_realtime(self, client: TestClient) -> None:
        """系统状态与实时快照必须来自同一个引擎状态，不能互相矛盾。"""
        status = client.get("/api/system/status").json()
        realtime = client.get("/api/realtime").json()

        assert status["sim_state"] == realtime["sim_state"]
        assert status["detection_running"] == realtime["detection_running"]

    def test_ai_state_reflects_detection_running(self, client: TestClient) -> None:
        client.post("/api/detection/stop")
        status = client.get("/api/system/status").json()
        ai = next(i for i in status["statuses"] if i["key"] == "ai")
        assert ai["text"] == "已停止"
        assert ai["state"] == "offline"


# =============================================================================
# /api/realtime 与 /api/realtime/history
# =============================================================================


class TestRealtime:
    def test_snapshot_schema_is_stable(self, client: TestClient) -> None:
        body = client.get("/api/realtime").json()

        for field in (
            "ts",
            "monitor_point",
            "sim_state",
            "sim_state_text",
            "detection_running",
            "stage",
            "scenario_forced",
            "radar",
            "vision",
            "environment",
            "risk",
            "fusion",
            "samples",
            "sample_interval_seconds",
        ):
            assert field in body, f"缺少字段 {field}"

        # 雷达字段（前端雷视联动页面依赖）
        for field in (
            "distance",
            "baseline_distance",
            "delta",
            "measured",
            "filtered",
            "sample_rate_hz",
            "max_refresh_hz",
            "refresh_text",
            "data_fresh",
            "online",
        ):
            assert field in body["radar"], f"radar 缺少字段 {field}"

        # 「设备最高刷新能力 ≠ 当前系统采集频率」，两个字段必须都对外暴露
        assert body["radar"]["sample_rate_hz"] == 10
        assert body["radar"]["max_refresh_hz"] == 1000

        for field in ("status", "label", "label_text", "confidence", "coverage", "latency_ms"):
            assert field in body["vision"], f"vision 缺少字段 {field}"

        for field in ("index", "level", "level_text", "trend", "trend_text"):
            assert field in body["risk"], f"risk 缺少字段 {field}"

        for field in ("verdict", "verdict_text", "mode", "reason", "confidence"):
            assert field in body["fusion"], f"fusion 缺少字段 {field}"

    def test_delta_is_consistent_with_baseline(self, client: TestClient) -> None:
        radar = client.get("/api/realtime").json()["radar"]
        assert radar["delta"] == pytest.approx(
            radar["distance"] - radar["baseline_distance"], abs=1e-6
        )
        assert radar["baseline_distance"] == 0.72

    def test_samples_returned_with_snapshot(self, client: TestClient) -> None:
        body = client.get("/api/realtime").json()
        samples = body["samples"]
        assert 60 <= len(samples) <= 180

        first = samples[0]
        for field in (
            "ts",
            "label",
            "sim_state",
            "radar_distance",
            "radar_filtered",
            "risk_index",
            "vision_coverage",
            "vision_confidence",
            "conveyor_speed",
            "temperature",
            "humidity",
        ):
            assert field in first, f"sample 缺少字段 {field}"

    def test_samples_last_point_matches_current_reading(self, client: TestClient) -> None:
        """趋势曲线末端必须等于状态卡上的当前读数，否则两者会互相矛盾。"""
        body = client.get("/api/realtime").json()
        last = body["samples"][-1]
        assert last["radar_filtered"] == pytest.approx(body["radar"]["distance"], abs=1e-3)
        # 快照的风险指数保留 1 位小数，样本保留 2 位，取 0.1 容差
        assert last["risk_index"] == pytest.approx(body["risk"]["index"], abs=0.1)

    def test_sample_interval_reflects_downsampling(self, client: TestClient) -> None:
        """降采样间隔要如实反映 10 Hz 原始采样被抽稀的倍数。

        1200 个原始点抽成 120 个 → 每约 10 个点取一个 → 约 1.0 s。
        """
        body = client.get("/api/realtime?points=120").json()
        interval = body["sample_interval_seconds"]
        assert 0.9 <= interval <= 1.2, interval

        # 点数越多，间隔越小
        dense = client.get("/api/realtime?points=180").json()["sample_interval_seconds"]
        sparse = client.get("/api/realtime?points=60").json()["sample_interval_seconds"]
        assert dense < sparse

    def test_history_endpoint_respects_limit(self, client: TestClient) -> None:
        assert len(client.get("/api/realtime/history?limit=60").json()) == 60
        assert len(client.get("/api/realtime/history?limit=180").json()) == 180

    @pytest.mark.parametrize("limit", [1, 5000, 0, -3])
    def test_history_rejects_out_of_range_limit(self, client: TestClient, limit: int) -> None:
        """超出 10~180 的请求被显式拒绝，而不是悄悄返回海量数据或空数组。"""
        assert client.get(f"/api/realtime/history?limit={limit}").status_code == 422

    def test_history_never_returns_thousands_of_points(self, client: TestClient) -> None:
        """浏览器只需要 60~180 个点：即使内部有 6000 个原始采样也不全量返回。"""
        assert len(client.get("/api/realtime/history?limit=180").json()) <= 180
        body = client.get("/api/realtime").json()
        assert len(body["samples"]) <= 180

    def test_risk_level_matches_index(self, client: TestClient) -> None:
        risk = client.get("/api/realtime").json()["risk"]
        index, level = risk["index"], risk["level"]
        if index < 30:
            assert level == "low"
        elif index < 55:
            assert level == "medium"
        elif index < 80:
            assert level == "high"
        else:
            assert level == "critical"

    def test_monitor_point_is_primary(self, client: TestClient) -> None:
        point = client.get("/api/realtime").json()["monitor_point"]
        assert point["position"] == 2
        assert point["has_radar"] is True
        assert point["device_ip"] == "192.168.1.198"


# =============================================================================
# /api/devices 与 /api/monitor-points
# =============================================================================


class TestDevices:
    def test_device_count_and_kinds(self, client: TestClient) -> None:
        devices = client.get("/api/devices").json()
        assert len(devices) == 18

        radars = [d for d in devices if d["kind"] == "radar"]
        cameras = [d for d in devices if d["kind"] == "camera"]
        assert len(radars) == 3
        assert len(cameras) == 15

    def test_radar_specs_match_acceptance_report(self, client: TestClient) -> None:
        radars = [d for d in client.get("/api/devices").json() if d["kind"] == "radar"]
        for radar in radars:
            assert radar["radar"]["range"] == "0.1–40 m"
            assert radar["radar"]["accuracy"] == "±5 cm"
            assert radar["radar"]["max_refresh_hz"] == 1000
            assert radar["radar"]["protection"] == "IP65"
            assert "重庆邮电大学" == radar["vendor"]

    def test_camera_specs_match_acceptance_report(self, client: TestClient) -> None:
        cameras = [d for d in client.get("/api/devices").json() if d["kind"] == "camera"]
        for camera in cameras:
            assert camera["model"] == "DS-2CD2242CX8-L"
            assert camera["vendor"] == "海康威视"
            assert camera["camera"]["encoding"] == "H.265"
            assert camera["camera"]["fps"] == 25

    def test_monitor_points_fusion_modes(self, client: TestClient) -> None:
        """点位 1~3 有雷达（联合判断），点位 4~7 仅摄像头（单独判断）。"""
        points = client.get("/api/monitor-points").json()
        assert len(points) == 7

        with_radar = [p for p in points if p["has_radar"]]
        assert [p["position"] for p in with_radar] == [1, 2, 3]

    def test_only_primary_point_has_stream(self, client: TestClient) -> None:
        """只有主监控点具备画面素材，其余返回 null（前端显示待切换占位）。"""
        points = client.get("/api/monitor-points").json()
        with_stream = [p for p in points if p["stream"]]
        assert len(with_stream) == 1
        assert with_stream[0]["position"] == 2

    def test_primary_point_is_camera_01(self, client: TestClient) -> None:
        """主监控画面的机位标识必须是 Camera 01。

        机位编号与点位号是两套编号：主监控点是点位 2，但画面标识为 Camera 01。
        曾经用点位号直接生成 "Camera NN"，导致核心监控画面被标成 Camera 02。
        """
        points = client.get("/api/monitor-points").json()
        primary = next(p for p in points if p["position"] == 2)
        assert primary["code"] == "Camera 01"

    def test_realtime_reports_camera_01(self, client: TestClient) -> None:
        """实时快照的监控点标识同样必须是 Camera 01（页面直接显示该字段）。"""
        snapshot = client.get("/api/realtime").json()
        assert snapshot["monitor_point"]["code"] == "Camera 01"
        assert snapshot["monitor_point"]["position"] == 2

    def test_camera_number_mapping_is_consistent(self, client: TestClient) -> None:
        """每个点位的机位编号唯一，且与 CAMERA_NUMBER 映射一致。"""
        from app.services.devices import CAMERA_NUMBER

        points = client.get("/api/monitor-points").json()
        codes = [p["code"] for p in points]
        assert len(set(codes)) == len(codes), "机位编号出现重复"

        for item in points:
            expected = f"Camera {CAMERA_NUMBER[item['position']]:02d}"
            assert item["code"] == expected


# =============================================================================
# 启停 / 重置 / 演示场景
# =============================================================================


class TestControlEndpoints:
    def test_start_returns_action_response(self, client: TestClient) -> None:
        resp = client.post("/api/detection/start")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert "message" in body
        assert body["sim_state"] in ("normal", "attention", "warning", "alarm", "stopped")

    def test_stop_freezes_realtime_values(self, client: TestClient) -> None:
        drive(3)
        client.post("/api/detection/stop")
        first = client.get("/api/realtime").json()

        drive(10)  # 停止后推进也不应改变数据

        second = client.get("/api/realtime").json()
        assert first["sim_state"] == "stopped"
        assert second["radar"]["distance"] == first["radar"]["distance"]
        assert second["risk"]["index"] == first["risk"]["index"]
        assert second["detection_running"] is False

    def test_start_resumes_after_stop(self, client: TestClient) -> None:
        client.post("/api/detection/stop")
        client.post("/api/detection/start")
        assert client.get("/api/realtime").json()["detection_running"] is True

    def test_reset_restores_normal(self, client: TestClient) -> None:
        client.post("/api/simulation/scenario/alarm")
        drive(60)
        assert client.get("/api/realtime").json()["sim_state"] == "alarm"

        resp = client.post("/api/simulation/reset")
        assert resp.status_code == 200

        body = client.get("/api/realtime").json()
        assert body["sim_state"] == "normal"
        assert body["risk"]["level"] == "low"
        assert body["scenario_forced"] is False

    @pytest.mark.parametrize("scenario", ["normal", "attention", "warning", "alarm"])
    def test_scenario_switch(self, client: TestClient, scenario: str) -> None:
        resp = client.post(f"/api/simulation/scenario/{scenario}")
        assert resp.status_code == 200
        assert resp.json()["sim_state"] == scenario

        drive(60)
        body = client.get("/api/realtime").json()
        assert body["sim_state"] == scenario
        assert body["stage"] == scenario
        assert body["scenario_forced"] is True

    def test_invalid_scenario_returns_422(self, client: TestClient) -> None:
        assert client.post("/api/simulation/scenario/meltdown").status_code == 422

    def test_clear_scenario(self, client: TestClient) -> None:
        client.post("/api/simulation/scenario/warning")
        assert client.get("/api/realtime").json()["scenario_forced"] is True
        assert client.post("/api/simulation/scenario").status_code == 200
        assert client.get("/api/realtime").json()["scenario_forced"] is False

    def test_stop_does_not_affect_history_availability(self, client: TestClient) -> None:
        client.post("/api/detection/stop")
        assert len(client.get("/api/realtime/history?limit=60").json()) == 60


# =============================================================================
# /api/alarms
# =============================================================================


class TestAlarms:
    def test_seeded_alarms_present(self, client: TestClient) -> None:
        body = client.get("/api/alarms").json()
        assert body["total"] >= 4
        assert len(body["items"]) >= 4

    def test_alarm_schema_is_stable(self, client: TestClient) -> None:
        item = client.get("/api/alarms").json()["items"][0]
        for field in (
            "id",
            "code",
            "ts",
            "device_id",
            "device_name",
            "device_ip",
            "location",
            "event_type",
            "level",
            "level_text",
            "radar_value",
            "vision_result",
            "fusion_result",
            "status",
            "status_text",
            "risk_index",
        ):
            assert field in item, f"报警记录缺少字段 {field}"

        assert item["level"] in ("info", "warning", "critical")
        assert item["status"] in ("pending", "processing", "resolved", "archived")
        # event_type 使用内部代码，vision_result 为中文描述
        assert item["event_type"] == "material_accumulation"
        assert item["vision_result"]

    def test_alarm_content_matches_reference_report(self, client: TestClient) -> None:
        """报警内容口径：设备名称 + 设备 IP + 报警时间 + 距离信息。"""
        item = client.get("/api/alarms").json()["items"][0]
        assert item["device_name"]
        assert item["device_ip"]
        assert item["ts"] > 0
        assert item["radar_value"] is not None

    def test_alarms_sorted_desc_by_time(self, client: TestClient) -> None:
        items = client.get("/api/alarms").json()["items"]
        ts = [i["ts"] for i in items]
        assert ts == sorted(ts, reverse=True)

    def test_filter_by_level(self, client: TestClient) -> None:
        body = client.get("/api/alarms?level=critical").json()
        assert all(i["level"] == "critical" for i in body["items"])

    def test_filter_by_status(self, client: TestClient) -> None:
        body = client.get("/api/alarms?status=archived").json()
        assert all(i["status"] == "archived" for i in body["items"])

    def test_filter_by_event_type(self, client: TestClient) -> None:
        body = client.get("/api/alarms?event_type=material_accumulation").json()
        assert body["total"] >= 1
        assert all(i["event_type"] == "material_accumulation" for i in body["items"])

    def test_filter_by_unknown_event_type_returns_empty(self, client: TestClient) -> None:
        body = client.get("/api/alarms?event_type=not_a_real_type").json()
        assert body["total"] == 0
        assert body["items"] == []

    def test_pagination(self, client: TestClient) -> None:
        body = client.get("/api/alarms?page=1&page_size=2").json()
        assert len(body["items"]) <= 2
        assert body["page"] == 1
        assert body["page_size"] == 2

    def test_alarm_generated_by_alarm_scenario(self, client: TestClient) -> None:
        before = client.get("/api/alarms").json()["total"]
        client.post("/api/simulation/scenario/alarm")
        drive(60)
        after = client.get("/api/alarms").json()
        assert after["total"] > before
        assert after["items"][0]["level"] == "critical"

    def test_alarm_detail_full_closure(self, client: TestClient) -> None:
        alarm_id = client.get("/api/alarms").json()["items"][0]["id"]
        resp = client.get(f"/api/alarms/{alarm_id}")
        assert resp.status_code == 200
        detail = resp.json()

        for field in (
            "baseline_distance",
            "snapshot",
            "radar_trend",
            "ai_analysis",
            "timeline",
            "operator",
            "resolution",
        ):
            assert field in detail, f"报警详情缺少字段 {field}"

        stages = [entry["stage"] for entry in detail["timeline"]]
        assert stages == ["发现", "判断", "报警", "处理", "归档"]

        assert detail["radar_trend"], "详情页需要雷达趋势数据"
        for field in ("vision_label", "confidence", "coverage", "note"):
            assert field in detail["ai_analysis"]

    def test_alarm_detail_404(self, client: TestClient) -> None:
        assert client.get("/api/alarms/EVT-NOT-EXIST").status_code == 404

    def test_event_type_has_chinese_label(self, client: TestClient) -> None:
        """接口必须直接给出中文异常类型，前端不散落翻译表。"""
        item = client.get("/api/alarms").json()["items"][0]
        assert item["event_type"] == "material_accumulation"
        assert item["event_type_text"] == "物料堆积"

    def test_filter_options_endpoint(self, client: TestClient) -> None:
        """筛选选项由后端提供，且与实际数据一致。"""
        body = client.get("/api/alarms/options").json()

        for key in ("levels", "statuses", "devices", "event_types"):
            assert key in body, f"缺少筛选选项 {key}"
            assert body[key], f"{key} 不应为空"

        level_values = {o["value"] for o in body["levels"]}
        assert level_values == {"info", "warning", "critical"}

        status_values = {o["value"] for o in body["statuses"]}
        assert status_values == {"pending", "processing", "resolved", "archived"}

        # 事件类型选项必须是中文标签，且能被筛选接口接受
        for option in body["event_types"]:
            assert option["label"] and option["label"] != option["value"]
            filtered = client.get(f"/api/alarms?event_type={option['value']}").json()
            assert filtered["total"] >= 1, f"选项 {option['value']} 筛不出任何数据"

    def test_options_route_not_shadowed_by_detail_route(self, client: TestClient) -> None:
        """/api/alarms/options 不能被 /api/alarms/{event_id} 抢先匹配成 404。"""
        assert client.get("/api/alarms/options").status_code == 200

    def test_seed_history_covers_multiple_dimensions(self, client: TestClient) -> None:
        """种子历史必须覆盖多个设备、多个异常类型与两个等级。

        否则数据溯源页的筛选下拉会退化成只有一个选项，失去演示意义。
        """
        items = client.get("/api/alarms?page_size=100").json()["items"]

        devices = {a["device_id"] for a in items}
        assert len(devices) >= 3, f"历史报警应覆盖至少 3 台设备，实际 {devices}"

        event_types = {a["event_type"] for a in items}
        assert len(event_types) >= 3, f"应覆盖至少 3 种异常类型，实际 {event_types}"

        levels = {a["level"] for a in items}
        assert "critical" in levels and "warning" in levels

        # 每条记录的 device_id 都应是台账中真实存在的设备
        known = {d["id"] for d in client.get("/api/devices").json()}
        assert devices <= known, f"存在台账外的设备编号: {devices - known}"

    def test_device_filter_returns_only_that_device(self, client: TestClient) -> None:
        for device_id in ("RAD-01", "RAD-02", "RAD-03"):
            body = client.get(f"/api/alarms?device_id={device_id}").json()
            assert all(a["device_id"] == device_id for a in body["items"])


# =============================================================================
# /api/prediction
# =============================================================================


class TestPrediction:
    def test_schema_is_stable(self, client: TestClient) -> None:
        body = client.get("/api/prediction").json()

        for field in (
            "ts",
            "horizon_minutes",
            "current",
            "forecast",
            "evidence",
            "suggestions",
            "similar_events",
            "curve",
        ):
            assert field in body, f"缺少字段 {field}"

        assert body["horizon_minutes"] == 30
        for field in ("index", "level", "level_text"):
            assert field in body["current"]
        for field in (
            "risk_index",
            "change",
            "change_text",
            "level",
            "level_text",
            "confidence",
        ):
            assert field in body["forecast"]

    def test_wording_is_probabilistic(self, client: TestClient) -> None:
        body = client.get("/api/prediction").json()
        joined = " ".join(body["suggestions"]) + " " + " ".join(
            e["text"] for e in body["evidence"]
        )
        for forbidden in ("一定", "必然", "肯定会堵"):
            assert forbidden not in joined, f"预测措辞不应出现确定性结论：{forbidden}"

    def test_evidence_covers_multiple_sources(self, client: TestClient) -> None:
        body = client.get("/api/prediction").json()
        sources = {e["source"] for e in body["evidence"]}
        assert "radar" in sources
        assert "vision" in sources
        assert len(sources) >= 3

    def test_similar_events_reference_documented_case(self, client: TestClient) -> None:
        body = client.get("/api/prediction").json()
        codes = [e["event_code"] for e in body["similar_events"]]
        assert any(code.startswith("EVT-2025") for code in codes)

    def test_warning_scenario_raises_forecast(self, client: TestClient) -> None:
        low = client.get("/api/prediction").json()["forecast"]["risk_index"]

        client.post("/api/simulation/scenario/warning")
        drive(60)
        high = client.get("/api/prediction").json()["forecast"]["risk_index"]

        assert high > low

    def test_curve_has_actual_and_predicted(self, client: TestClient) -> None:
        curve = client.get("/api/prediction").json()["curve"]
        assert any(p["actual"] is not None for p in curve)
        assert any(p["predicted"] is not None for p in curve)


# =============================================================================
# /api/knowledge
# =============================================================================


class TestKnowledge:
    def test_seed_count_in_expected_range(self, client: TestClient) -> None:
        """按任务要求生成 8~15 条高质量样例，而不是几百条垃圾数据。"""
        events = client.get("/api/knowledge").json()
        assert 8 <= len(events) <= 15

    def test_schema_is_stable(self, client: TestClient) -> None:
        event = client.get("/api/knowledge").json()[0]
        for field in (
            "id",
            "event_code",
            "timestamp",
            "device_id",
            "location",
            "event_type",
            "radar_summary",
            "vision_summary",
            "environment_summary",
            "pre_event_pattern",
            "operator_review",
            "action_taken",
            "result",
            "preventive_suggestion",
        ):
            assert field in event, f"知识库事件缺少字段 {field}"

    def test_documented_event_from_acceptance_report(self, client: TestClient) -> None:
        """资料中真实发生过的事件必须存在且描述与原始记录一致。"""
        events = client.get("/api/knowledge").json()
        target = next(e for e in events if e["event_code"] == "EVT-20250519-02")

        assert target["location"] == "制丝线 2 号输送段"
        assert target["event_type"] == "物料堆积"
        # 资料原文：测距均值由 0.71m 逐步下降至 0.62m；风险指数达到 72%
        assert "0.71" in target["radar_summary"]
        assert "0.62" in target["radar_summary"]
        assert "72%" in target["radar_summary"]
        # 资料原文：进料量短时间升高，同时下游输送速度降低
        assert "进料量" in target["operator_review"]
        assert "输送速度" in target["operator_review"]
        # 资料原文：约 4 分钟后物料恢复正常
        assert "4 分钟" in target["result"]

    def test_sorted_desc_by_timestamp(self, client: TestClient) -> None:
        events = client.get("/api/knowledge").json()
        stamps = [e["timestamp"] for e in events]
        assert stamps == sorted(stamps, reverse=True)

    def test_keyword_search(self, client: TestClient) -> None:
        """关键词为全文检索：命中任意描述字段即应返回。"""
        events = client.get("/api/knowledge?keyword=物料堆积").json()
        assert events

        hit_fields = (
            "event_code",
            "location",
            "event_type",
            "radar_summary",
            "vision_summary",
            "environment_summary",
            "pre_event_pattern",
            "operator_review",
            "action_taken",
            "result",
            "preventive_suggestion",
        )
        for event in events:
            assert any("物料堆积" in event[f] for f in hit_fields), event["event_code"]

    def test_keyword_search_by_event_code(self, client: TestClient) -> None:
        """按事件编号检索应命中该事件（其他事件可能在描述中引用它）。"""
        events = client.get("/api/knowledge?keyword=EVT-20250519-02").json()
        codes = [e["event_code"] for e in events]
        assert "EVT-20250519-02" in codes

    def test_keyword_search_no_match(self, client: TestClient) -> None:
        assert client.get("/api/knowledge?keyword=不存在的关键词XYZ").json() == []

    def test_event_type_filter(self, client: TestClient) -> None:
        types = client.get("/api/knowledge/types").json()
        assert "物料堆积" in types

        events = client.get("/api/knowledge?event_type=物料堆积").json()
        assert all(e["event_type"] == "物料堆积" for e in events)

    def test_detail_endpoint(self, client: TestClient) -> None:
        assert client.get("/api/knowledge/EVT-20250519-02").status_code == 200
        assert client.get("/api/knowledge/EVT-NOT-EXIST").status_code == 404
