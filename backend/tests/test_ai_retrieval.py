"""知识检索与 Prompt 构建测试。

覆盖任务要求：
相同类型优先 / 同点位加权 / Top-K=3 / 不返回全部 12 条 /
分析历史事件时排除自身 / 知识包含措施与结果 /
不下发设备内网 IP / Prompt 不含任何密钥与内部路径。
"""

from __future__ import annotations

import pytest

from app.services.ai import prompt as prompt_builder
from app.services.ai.retriever import (
    CONTEXT_FIELDS,
    TOP_K,
    CurrentEventContext,
    KnowledgeRetriever,
    knowledge_fingerprint,
    score_case,
)
from app.services.knowledge import get_knowledge_base


@pytest.fixture
def retriever() -> KnowledgeRetriever:
    return KnowledgeRetriever(get_knowledge_base())


def _accumulation_event(**overrides) -> CurrentEventContext:
    """一个典型的物料堆积预警事件。"""
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
        has_radar=True,
    )
    base.update(overrides)
    return CurrentEventContext(**base)  # type: ignore[arg-type]


# =============================================================================
# 1. Top-K 与排序
# =============================================================================


class TestTopK:
    def test_default_top_k_is_three(self, retriever: KnowledgeRetriever) -> None:
        assert TOP_K == 3
        assert len(retriever.retrieve(_accumulation_event())) <= 3

    def test_exactly_top_k_when_enough_cases(self, retriever: KnowledgeRetriever) -> None:
        result = retriever.retrieve(_accumulation_event(), top_k=3)
        assert len(result) == 3

    def test_does_not_return_all_records(self, retriever: KnowledgeRetriever) -> None:
        """不能把 12 条无脑塞进上下文。"""
        total = len(get_knowledge_base().list_events(limit=100))
        assert total >= 10, "测试前提：知识库应有 10 条以上记录"
        result = retriever.retrieve(_accumulation_event())
        assert len(result) < total

    def test_top_k_is_configurable(self, retriever: KnowledgeRetriever) -> None:
        assert len(retriever.retrieve(_accumulation_event(), top_k=5)) == 5

    def test_scores_are_descending(self, retriever: KnowledgeRetriever) -> None:
        scores = [c.score for c in retriever.retrieve(_accumulation_event(), top_k=5)]
        assert scores == sorted(scores, reverse=True)


class TestScoring:
    def test_same_event_type_ranks_first(self, retriever: KnowledgeRetriever) -> None:
        """相同异常类型必须排在最前 —— 这是权重最高的一维。"""
        result = retriever.retrieve(_accumulation_event())
        assert result[0].event_type == "物料堆积"

    def test_same_event_type_beats_other_type(self) -> None:
        current = _accumulation_event()
        same = {
            "event_code": "A",
            "event_type": "物料堆积",
            "location": "别处",
            "device_id": "RAD-09",
            "radar_summary": "",
        }
        other = {
            "event_code": "B",
            "event_type": "人员进入检测区",
            "location": current.location,
            "device_id": "RAD-02",
            "radar_summary": "",
        }
        same_score, _ = score_case(current, same)
        other_score, _ = score_case(current, other)
        assert same_score > other_score

    def test_same_location_adds_score(self) -> None:
        current = _accumulation_event()
        near = {"event_code": "A", "event_type": "物料堆积", "location": current.location}
        far = {"event_code": "B", "event_type": "物料堆积", "location": "叶线提升段"}
        near_score, near_parts = score_case(current, near)
        far_score, far_parts = score_case(current, far)
        assert near_score > far_score
        assert near_parts["location"] == 1.0
        assert far_parts["location"] == 0.0

    def test_same_device_kind_adds_score(self) -> None:
        current = _accumulation_event(has_radar=True)
        radar = {"event_code": "A", "event_type": "物料堆积", "location": "x", "device_id": "RAD-01"}
        vision = {"event_code": "B", "event_type": "物料堆积", "location": "x", "device_id": "CAM-05"}
        assert score_case(current, radar)[1]["device_kind"] == 1.0
        assert score_case(current, vision)[1]["device_kind"] == 0.0

    def test_closer_distance_scores_higher(self) -> None:
        """测距越接近当前值，严重程度维度得分越高。"""
        current = _accumulation_event(distance=0.58)
        close = {
            "event_code": "A",
            "event_type": "物料堆积",
            "location": "x",
            "radar_summary": "测距降至 0.58 m",
        }
        far = {
            "event_code": "B",
            "event_type": "物料堆积",
            "location": "x",
            "radar_summary": "测距降至 0.72 m",
        }
        assert score_case(current, close)[1]["severity"] > score_case(current, far)[1]["severity"]

    def test_breakdown_covers_all_dimensions(self) -> None:
        _, parts = score_case(_accumulation_event(), {"event_code": "A", "event_type": "物料堆积"})
        assert set(parts) == {"event_type", "location", "device_kind", "severity", "keyword"}


# =============================================================================
# 2. 自引用排除
# =============================================================================


class TestSelfExclusion:
    def test_excludes_own_event_code(self, retriever: KnowledgeRetriever) -> None:
        """分析历史事件时不得把该事件自己当作类似历史经验。"""
        current = _accumulation_event(event_code="EVT-20250519-02")
        result = retriever.retrieve(current, top_k=10)
        assert "EVT-20250519-02" not in [c.event_code for c in result]

    def test_explicit_exclusion_argument(self, retriever: KnowledgeRetriever) -> None:
        result = retriever.retrieve(
            _accumulation_event(), top_k=10, exclude_event_code="EVT-20250519-02"
        )
        assert "EVT-20250519-02" not in [c.event_code for c in result]

    def test_other_cases_still_returned(self, retriever: KnowledgeRetriever) -> None:
        """排除自身后仍应返回其他案例，不能把自己排除掉就空了。"""
        result = retriever.retrieve(_accumulation_event(event_code="EVT-20250519-02"), top_k=3)
        assert len(result) == 3
        assert all(c.event_code != "EVT-20250519-02" for c in result)


# =============================================================================
# 3. 上下文内容
# =============================================================================


class TestContextFields:
    def test_contains_actions_and_result(self, retriever: KnowledgeRetriever) -> None:
        """历史案例必须带来处理措施与结果，否则模型没有经验可参考。"""
        case = retriever.retrieve(_accumulation_event())[0]
        assert case.payload["action_taken"], "应包含处理措施"
        assert case.payload["result"], "应包含处理结果"
        assert case.payload["pre_event_pattern"], "应包含异常前兆"

    def test_context_field_whitelist(self) -> None:
        """只送白名单字段 —— 不把数据库整行丢给模型。"""
        assert "device_id" not in CONTEXT_FIELDS
        assert "device_ip" not in CONTEXT_FIELDS
        assert "id" not in CONTEXT_FIELDS
        assert "source" not in CONTEXT_FIELDS
        assert "timestamp" not in CONTEXT_FIELDS

    def test_payload_only_has_whitelisted_keys(self, retriever: KnowledgeRetriever) -> None:
        case = retriever.retrieve(_accumulation_event())[0]
        assert set(case.payload) == set(CONTEXT_FIELDS)

    def test_no_device_ip_in_context(self, retriever: KnowledgeRetriever) -> None:
        """设备内网 IP 不进入上下文（对判断原因没帮助，且是内部信息）。"""
        cases = retriever.retrieve(_accumulation_event(), top_k=5)
        blob = " ".join(str(v) for c in cases for v in c.payload.values())
        assert "192.168." not in blob


# =============================================================================
# 4. Prompt
# =============================================================================


class TestPrompt:
    def test_user_prompt_contains_current_data(self, retriever: KnowledgeRetriever) -> None:
        current = _accumulation_event()
        text = prompt_builder.build_user_prompt(current, retriever.retrieve(current))
        assert current.location in text
        assert current.event_type in text
        assert "0.632" in text, "应包含当前测距"
        assert "68.0" in text, "应包含风险指数"

    def test_warning_and_alarm_have_different_tasks(self, retriever: KnowledgeRetriever) -> None:
        warning = prompt_builder.build_user_prompt(
            _accumulation_event(stage="warning"), retriever.retrieve(_accumulation_event())
        )
        alarm = prompt_builder.build_user_prompt(
            _accumulation_event(stage="alarm"), retriever.retrieve(_accumulation_event())
        )
        assert "预警" in warning and "提前干预" in warning
        assert "报警" in alarm and "立即处置" in alarm
        assert warning != alarm

    def test_prompt_contains_top_k_cases(self, retriever: KnowledgeRetriever) -> None:
        current = _accumulation_event()
        cases = retriever.retrieve(current)
        text = prompt_builder.build_user_prompt(current, cases)
        for case in cases:
            assert case.event_code in text

    def test_prompt_has_no_cases_note_when_empty(self) -> None:
        text = prompt_builder.build_user_prompt(_accumulation_event(), [])
        assert "没有可参考的相似案例" in text

    def test_prompt_requires_json_output(self, retriever: KnowledgeRetriever) -> None:
        text = prompt_builder.build_user_prompt(_accumulation_event(), [])
        for key in (
            "summary",
            "possible_causes",
            "recommended_checks",
            "recommended_actions",
            "related_cases",
            "evidence_basis",
        ):
            assert key in text

    def test_system_prompt_states_llm_does_not_decide_level(
        self,
    ) -> None:
        system = prompt_builder.BASE_SYSTEM_PROMPT
        assert "不得修改或质疑系统给出的报警等级" in system
        assert "判定结果不由你修改" in system
        assert "当前证据不足以确定" in system

    def test_prompt_contains_no_secrets(self, retriever: KnowledgeRetriever) -> None:
        """Prompt 里不得出现密钥、令牌、公网 IP、源码路径。"""
        current = _accumulation_event()
        text = prompt_builder.build_user_prompt(
            current, retriever.retrieve(current)
        )
        system = prompt_builder.BASE_SYSTEM_PROMPT
        blob = system + text

        for forbidden in (
            "sk-",
            "Bearer",
            "api_key",
            "API_KEY",
            "AI_ADMIN_TOKEN",
            "110.42.236.65",
            "127.0.0.1",
            "localhost",
            "192.168.",
            "D:\\",
            "C:\\",
            "/home/",
            "traceback",
        ):
            assert forbidden not in blob, f"Prompt 不应包含 {forbidden!r}"

    def test_omits_missing_fields_instead_of_faking(self, retriever: KnowledgeRetriever) -> None:
        """没有的字段直接省略 —— 宁可少给也不编造。"""
        sparse = CurrentEventContext(
            stage="alarm",
            location="制丝线 1 号输送段",
            event_type="物料堆积",
            risk_index=85.0,
            distance=0.59,
        )
        text = prompt_builder.build_user_prompt(sparse, [])
        assert "环境温度" not in text
        assert "环境湿度" not in text
        assert "设备负载" not in text
        assert "输送有效速度" not in text
        assert "0.59" in text, "提供的字段仍应出现"


# =============================================================================
# 5. 知识库指纹
# =============================================================================


class TestKnowledgeFingerprint:
    def test_stable_across_calls(self) -> None:
        kb = get_knowledge_base()
        assert knowledge_fingerprint(kb) == knowledge_fingerprint(kb)

    def test_changes_when_content_changes(self, workdir) -> None:
        """知识库内容变化后指纹必须变化，让旧分析失效。"""
        from app.services.knowledge import KnowledgeBase

        db = workdir / "kb_fp.db"
        if db.exists():
            db.unlink()
        kb = KnowledgeBase(db)
        kb.initialize()
        before = knowledge_fingerprint(kb)

        # 改一条记录的结果文本
        conn = kb._connect()
        conn.execute(
            "UPDATE knowledge_event SET result = ? WHERE event_code = ?",
            ("测试改动后的结果", "EVT-20250519-02"),
        )
        conn.commit()

        assert knowledge_fingerprint(kb) != before
