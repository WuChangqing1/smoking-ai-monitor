"""AI 分析流程测试：缓存、single-flight、故障降级、阶段触发。

**全部使用本地 mock 模型服务，绝不访问真实模型 API。**

重点证明两件事：
1. 同一个分析重复请求只真正调用模型一次（缓存 + single-flight）；
2. 模型服务各种故障都不能让业务接口崩溃。
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.services.ai.analysis import (
    STATUS_DISABLED,
    STATUS_OK,
    STATUS_UNAVAILABLE,
    build_cache_key,
    get_ai_service,
    reset_ai_service,
    reset_cache,
)
from app.services.ai.config_store import reset_settings_store
from app.services.ai.retriever import CurrentEventContext
from tests.mock_llm import FENCED_JSON, GOOD_JSON, PLAIN_TEXT, MockLLMServer


#: 本模块用的测试数据库路径（由 fixture 设置）
_DB: dict[str, Path] = {}


@pytest.fixture(autouse=True)
def _isolated(workdir: Path) -> None:
    """独立的配置库与缓存库，且每个测试前清空。

    注意先删文件：否则上一个测试留下的配置与缓存会污染下一个测试
    （缓存命中会让"应该调用模型"的用例静默通过）。
    """
    base = workdir / "ai_analysis"
    base.mkdir(parents=True, exist_ok=True)
    for name in ("settings.db", "cache.db"):
        path = base / name
        for suffix in ("", "-journal", "-wal", "-shm"):
            stale = Path(str(path) + suffix)
            if stale.exists():
                stale.unlink()

    _DB["settings"] = base / "settings.db"
    _DB["cache"] = base / "cache.db"
    _DB["main"] = base / "main.db"
    reset_settings_store(_DB["settings"])
    reset_cache(_DB["cache"])
    reset_ai_service()
    # 让分析服务也用测试库，避免写到真实 data/ 目录
    get_ai_service()._db_path = _DB["main"]


def _store():
    """当前测试的配置存储。

    **不能调用无参的 ``reset_settings_store()``** ——
    那会建到真实数据库上，配置就指不回 mock 服务了（曾因此让测试卡住）。
    """
    return reset_settings_store(_DB["settings"])


def _enable(server: MockLLMServer, **overrides) -> None:
    """把配置指向 mock 服务并启用。"""
    payload = {
        "enabled": True,
        "provider": "openai_compatible",
        "base_url": server.base_url,
        "model": "mock-model",
        "timeout": 8.0,
    }
    payload.update(overrides)
    _store().save(payload)


def _event(**overrides) -> CurrentEventContext:
    base = dict(
        stage="warning",
        location="制丝线 2 号输送段",
        event_type="物料堆积",
        risk_index=68.0,
        distance=0.632,
        baseline_distance=0.72,
        coverage=0.58,
        vision_label="物料堆积",
        vision_confidence=0.90,
        conveyor_speed=1.08,
        temperature=23.8,
        humidity=52.0,
        equipment_load=72.0,
    )
    base.update(overrides)
    return CurrentEventContext(**base)  # type: ignore[arg-type]


def _analyze(target: str, analysis_type: str = "warning", **kw):
    return asyncio.run(
        get_ai_service().analyze(
            target=target, analysis_type=analysis_type, current=_event(**kw)
        )
    )


# =============================================================================
# 1. 正常链路
# =============================================================================


class TestHappyPath:
    def test_returns_structured_analysis(self) -> None:
        with MockLLMServer() as server:
            _enable(server)
            result = _analyze("current:warning")
            assert result.status == STATUS_OK
            assert result.source == "llm"
            assert result.summary
            assert result.possible_causes
            assert result.recommended_checks
            assert result.recommended_actions
            assert result.structured is True
            assert result.provider
            assert result.model == "mock-model"

    def test_related_cases_filled_from_knowledge(self) -> None:
        with MockLLMServer() as server:
            _enable(server)
            result = _analyze("current:warning")
            # 模型给了 EVT-20250519-02；即便模型不给，也回退到检索结果
            assert result.related_cases

    def test_markdown_fenced_json_is_parsed(self) -> None:
        with MockLLMServer() as server:
            _enable(server)
            server.state.content = FENCED_JSON
            result = _analyze("current:warning")
            assert result.status == STATUS_OK
            assert result.structured is True
            assert result.summary

    def test_plain_text_becomes_fallback_text(self) -> None:
        """模型没按 JSON 输出时，原文保留供页面展示，不能 500。"""
        with MockLLMServer() as server:
            _enable(server)
            server.state.content = PLAIN_TEXT
            result = _analyze("current:warning")
            assert result.status == STATUS_OK
            assert result.structured is False
            assert result.fallback_text == PLAIN_TEXT


# =============================================================================
# 2. 缓存与 single-flight
# =============================================================================


class TestCaching:
    def test_ten_requests_call_model_once(self) -> None:
        """连续 10 次获取同一个 warning 分析，模型只应被调用 1 次。"""
        with MockLLMServer() as server:
            _enable(server)
            for _ in range(10):
                result = _analyze("current:warning")
                assert result.status == STATUS_OK
            assert server.state.call_count == 1, f"实际调用了 {server.state.call_count} 次"

    def test_alarm_and_warning_are_separate_keys(self) -> None:
        """warning 与 alarm 是两份独立缓存，各调用一次。"""
        with MockLLMServer() as server:
            _enable(server)
            for _ in range(10):
                _analyze("current:warning", "warning")
            for _ in range(10):
                _analyze("current:alarm", "alarm", stage="alarm")
            assert server.state.call_count == 2

    def test_cache_hit_is_marked(self) -> None:
        with MockLLMServer() as server:
            _enable(server)
            first = _analyze("current:warning")
            second = _analyze("current:warning")
            assert first.cached is False
            assert second.cached is True

    def test_force_bypasses_cache(self) -> None:
        with MockLLMServer() as server:
            _enable(server)
            _analyze("current:warning")
            forced = asyncio.run(
                get_ai_service().analyze(
                    target="current:warning",
                    analysis_type="warning",
                    current=_event(),
                    force=True,
                )
            )
            assert forced.status == STATUS_OK
            assert server.state.call_count == 2

    def test_config_change_produces_new_key(self) -> None:
        """改模型配置后，下一次必须重新调用模型。"""
        with MockLLMServer() as server:
            _enable(server)
            _analyze("current:warning")
            assert server.state.call_count == 1

            # 换模型 -> 指纹变 -> cache key 变
            _enable(server, model="another-model")
            _analyze("current:warning")
            assert server.state.call_count == 2

    def test_base_url_change_produces_new_key(self) -> None:
        with MockLLMServer() as server:
            _enable(server)
            _analyze("current:warning")
            _enable(server, base_url=server.base_url + "/")
            # 规范化后等价，指纹相同 -> 仍走缓存
            _analyze("current:warning")
            assert server.state.call_count == 1

    def test_knowledge_change_invalidates_cache(self) -> None:
        """检索出的案例内容变了，旧分析必须失效。"""
        from app.services.knowledge import get_knowledge_base

        with MockLLMServer() as server:
            _enable(server)
            _analyze("current:warning")
            assert server.state.call_count == 1

            kb = get_knowledge_base()
            conn = kb._connect()
            conn.execute(
                "UPDATE knowledge_event SET action_taken = ? WHERE event_code = ?",
                ("知识库被修改后的措施", "EVT-20250519-02"),
            )
            conn.commit()

            _analyze("current:warning")
            assert server.state.call_count == 2, "知识库变化后应重新分析"

    def test_unrelated_new_record_keeps_cache(self) -> None:
        """新增**无关**记录不应让缓存失效。

        引擎会持续产生报警记录。若用整库内容做 cache key，缓存会永久失效、
        每次请求都烧 Token。因此指纹只取实际进入 Prompt 的那几条案例。
        """
        from app.services.knowledge import get_knowledge_base

        with MockLLMServer() as server:
            _enable(server)
            _analyze("current:warning")
            assert server.state.call_count == 1

            # 插入一条与当前事件（物料堆积 / 制丝线 2 号输送段）无关的记录
            kb = get_knowledge_base()
            conn = kb._connect()
            conn.execute(
                """
                INSERT INTO knowledge_event (
                    event_code, timestamp, device_id, location, event_type,
                    radar_summary, vision_summary, environment_summary,
                    pre_event_pattern, operator_review, action_taken, result,
                    preventive_suggestion, source
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    "EVT-20990101-99",
                    "2099-01-01 00:00:00",
                    "CAM-07",
                    "贮叶柜入口段",
                    "人员进入检测区",
                    "无雷达",
                    "视觉检出人员",
                    "环境正常",
                    "无关记录",
                    "无关",
                    "无关",
                    "无关",
                    "无关",
                    "sample",
                ),
            )
            conn.commit()

            result = _analyze("current:warning")
            assert result.cached is True, "无关记录不应使缓存失效"
            assert server.state.call_count == 1

    def test_failed_call_is_not_cached(self) -> None:
        """失败结果不缓存 —— 否则模型恢复后仍会一直返回失败。"""
        with MockLLMServer() as server:
            _enable(server)
            server.state.status = 500
            first = _analyze("current:warning")
            assert first.status == STATUS_UNAVAILABLE

            server.state.status = 200
            second = _analyze("current:warning")
            assert second.status == STATUS_OK, "模型恢复后应能重新分析成功"
            assert server.state.call_count == 2

    def test_single_flight_under_concurrency(self) -> None:
        """并发请求同一个 key，只能发一次模型请求。"""
        with MockLLMServer() as server:
            _enable(server)
            server.state.delay = 0.3  # 拉长窗口，让并发真的重叠

            async def run_all():
                service = get_ai_service()
                return await asyncio.gather(
                    *[
                        service.analyze(
                            target="current:warning",
                            analysis_type="warning",
                            current=_event(),
                        )
                        for _ in range(6)
                    ]
                )

            results = asyncio.run(run_all())
            assert all(r.status == STATUS_OK for r in results)
            assert server.state.call_count == 1, (
                f"并发 6 次请求实际调用了 {server.state.call_count} 次模型"
            )

    def test_cache_key_composition(self) -> None:
        from app.services.ai.config_store import AISettings

        a = build_cache_key(
            target="t", analysis_type="warning", ai_settings=AISettings(), knowledge_hash="k1"
        )
        b = build_cache_key(
            target="t", analysis_type="warning", ai_settings=AISettings(), knowledge_hash="k2"
        )
        c = build_cache_key(
            target="u", analysis_type="warning", ai_settings=AISettings(), knowledge_hash="k1"
        )
        assert a != b, "知识库指纹应参与 key"
        assert a != c, "target 应参与 key"


# =============================================================================
# 3. 阶段触发规则
# =============================================================================


class TestStageGating:
    @pytest.mark.parametrize("stage", ["normal", "attention"])
    def test_normal_and_attention_do_not_call_model(self, stage: str) -> None:
        with MockLLMServer() as server:
            _enable(server)
            result = asyncio.run(
                get_ai_service().analyze(
                    target=f"current:{stage}",
                    analysis_type=stage,
                    current=_event(stage=stage),
                )
            )
            assert result.status == STATUS_DISABLED
            assert server.state.call_count == 0, f"{stage} 阶段不应调用模型"

    @pytest.mark.parametrize("stage", ["warning", "alarm"])
    def test_warning_and_alarm_are_analyzable(self, stage: str) -> None:
        with MockLLMServer() as server:
            _enable(server)
            result = asyncio.run(
                get_ai_service().analyze(
                    target=f"current:{stage}",
                    analysis_type=stage,
                    current=_event(stage=stage),
                )
            )
            assert result.status == STATUS_OK
            assert server.state.call_count == 1

    def test_disabled_service_does_not_call_model(self) -> None:
        with MockLLMServer() as server:
            _store().save({"enabled": False, "base_url": server.base_url})
            result = _analyze("current:warning")
            assert result.status == STATUS_DISABLED
            assert server.state.call_count == 0

    def test_incomplete_config_does_not_call_model(self) -> None:
        with MockLLMServer() as server:
            _store().save({"enabled": True, "base_url": "", "model": ""})
            result = _analyze("current:warning")
            assert result.status == STATUS_DISABLED
            assert server.state.call_count == 0


# =============================================================================
# 4. 故障降级
# =============================================================================


class TestFailureHandling:
    @pytest.mark.parametrize(
        ("status", "expect_in_error"),
        [
            (401, "鉴权"),
            (403, "拒绝"),
            (404, "不存在"),
            (429, "频繁"),
            (500, "内部错误"),
        ],
    )
    def test_http_errors_degrade_gracefully(self, status: int, expect_in_error: str) -> None:
        with MockLLMServer() as server:
            _enable(server)
            server.state.status = status
            result = _analyze("current:warning")
            assert result.status == STATUS_UNAVAILABLE
            assert result.source == "fallback"
            assert result.error_message
            assert expect_in_error in result.error_message

    def test_connection_refused(self) -> None:
        _store().save(
            {
                "enabled": True,
                "base_url": "http://127.0.0.1:1/v1",
                "model": "x",
                "timeout": 3.0,
            }
        )
        result = _analyze("current:warning")
        assert result.status == STATUS_UNAVAILABLE
        assert "无法连接" in (result.error_message or "")

    def test_timeout(self) -> None:
        with MockLLMServer() as server:
            _enable(server, timeout=3.0)
            server.state.delay = 6.0
            result = _analyze("current:warning")
            assert result.status == STATUS_UNAVAILABLE
            assert "超时" in (result.error_message or "")

    def test_malformed_json_body(self) -> None:
        with MockLLMServer() as server:
            _enable(server)
            server.state.malformed = True
            result = _analyze("current:warning")
            assert result.status == STATUS_UNAVAILABLE

    def test_empty_content(self) -> None:
        with MockLLMServer() as server:
            _enable(server)
            server.state.empty_content = True
            result = _analyze("current:warning")
            assert result.status == STATUS_UNAVAILABLE
            assert "无法解析" in (result.error_message or "") or result.error_message

    def test_error_message_has_no_traceback(self) -> None:
        with MockLLMServer() as server:
            _enable(server)
            server.state.status = 500
            result = _analyze("current:warning")
            message = result.error_message or ""
            for forbidden in ("Traceback", "File \"", "line ", ".py", "urllib"):
                assert forbidden not in message, f"错误信息不应包含 {forbidden!r}"


# =============================================================================
# 5. 接口层
# =============================================================================


class TestApiEndpoints:
    def test_meta_endpoint(self, client: TestClient) -> None:
        body = client.get("/api/ai/analysis/meta").json()
        assert set(body["analyzable_stages"]) == {"warning", "alarm"}
        assert body["top_k"] == 3

    def test_current_analysis_returns_disabled_when_not_enabled(self, client: TestClient) -> None:
        body = client.get("/api/ai/analysis/current?type=warning").json()
        assert body["status"] == "disabled"
        assert body["source"] == "fallback"

    def test_current_analysis_ok_when_enabled(self, client: TestClient) -> None:
        with MockLLMServer() as server:
            _enable(server)
            body = client.get("/api/ai/analysis/current?type=warning").json()
            assert body["status"] == "ok"
            assert body["source"] == "llm"
            assert body["summary"]

    def test_repeated_api_calls_call_model_once(self, client: TestClient) -> None:
        """接口层也必须有缓存 —— 前端轮询不应重复烧 Token。"""
        with MockLLMServer() as server:
            _enable(server)
            for _ in range(10):
                assert client.get("/api/ai/analysis/current?type=warning").status_code == 200
            assert server.state.call_count == 1

    def test_invalid_type_rejected(self, client: TestClient) -> None:
        assert client.get("/api/ai/analysis/current?type=normal").status_code == 422

    def test_event_analysis_requires_existing_event(self, client: TestClient) -> None:
        assert client.get("/api/ai/analysis/event/EVT-NOT-EXIST").status_code == 404

    def test_event_analysis_works(self, client: TestClient) -> None:
        """提交版的核心演示链路：历史报警 → 知识检索 → LLM → 分析。"""
        items = client.get("/api/alarms?page_size=100").json()["items"]
        accumulation = [a for a in items if a["event_type"] == "material_accumulation"]
        assert accumulation, "测试前提：应有物料堆积类报警"

        with MockLLMServer() as server:
            _enable(server)
            event_id = accumulation[0]["id"]
            body = client.get(f"/api/ai/analysis/event/{event_id}").json()
            assert body["status"] == "ok"
            assert body["summary"]

            # 再次请求走缓存
            again = client.get(f"/api/ai/analysis/event/{event_id}").json()
            assert again["cached"] is True
            assert server.state.call_count == 1

    def test_event_analysis_excludes_itself_from_cases(self, client: TestClient) -> None:
        """模型收到的历史案例里不能包含正在分析的这条事件本身。"""
        items = client.get("/api/alarms?page_size=100").json()["items"]
        accumulation = [a for a in items if a["event_type"] == "material_accumulation"]

        with MockLLMServer() as server:
            _enable(server)
            event_id = accumulation[0]["id"]
            client.get(f"/api/ai/analysis/event/{event_id}")

            prompt_text = server.state.requests[0]["messages"][1]["content"]
            # 事件本身的信息只能出现在「当前监测数据」段，不能出现在案例段
            cases_section = prompt_text.split("## 历史相似案例")[1]
            assert event_id not in cases_section.split("## 输出要求")[0]

    def test_prompt_sent_to_model_has_no_secrets(self, client: TestClient) -> None:
        with MockLLMServer() as server:
            _enable(server, api_key="sk-must-not-leak-1234")
            client.get("/api/ai/analysis/current?type=warning")

            body = server.state.requests[0]
            blob = body["messages"][0]["content"] + body["messages"][1]["content"]
            for forbidden in ("sk-must-not-leak", "192.168.", "110.42.236.65", "D:\\", "/home/"):
                assert forbidden not in blob, f"Prompt 泄漏了 {forbidden!r}"

    def test_refresh_requires_admin(self, client: TestClient) -> None:
        """强制重新分析必须带管理员令牌。"""
        previous = settings.ai_admin_token
        object.__setattr__(settings, "ai_admin_token", "tok")
        try:
            assert client.get("/api/ai/analysis/current?type=warning&refresh=true").status_code == 401
            assert (
                client.get(
                    "/api/ai/analysis/current?type=warning&refresh=true",
                    headers={"X-AI-Admin-Token": "tok"},
                ).status_code
                == 200
            )
        finally:
            object.__setattr__(settings, "ai_admin_token", previous)
