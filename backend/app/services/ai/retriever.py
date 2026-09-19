"""知识库检索：为模型挑选最相关的历史案例。

为什么不用向量检索
------------------
知识库当前只有 12 条结构化历史记录。为这个规模引入
Milvus / FAISS / Chroma / Embedding 服务，运维成本远大于收益。
这里用**结构化字段匹配 + 加权打分**，结果可解释、可断言、零依赖。

打分维度
--------
============  ======  ==========================================
维度          权重    说明
============  ======  ==========================================
异常类型      0.45    同类异常最关键（相同类型直接给满分）
点位/位置     0.25    同一输送段的历史经验更可迁移
设备类型      0.10    雷达点位 vs 视觉点位的处置思路不同
严重程度      0.10    风险指数越接近越有参考价值
关键词        0.10    前兆描述与当前视觉/环境结果的字面重合
============  ======  ==========================================

同一 ``event_type`` 的权重最高，保证「物料堆积」事件优先召回物料堆积案例。
返回 Top-K（默认 3），不把 12 条全塞进上下文。
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field

from app.services.knowledge import KnowledgeBase

logger = logging.getLogger(__name__)

#: 默认返回条数。刻意保持小 —— 上下文越长，模型越容易跑题
TOP_K = 3

#: 各维度权重（合计 1.0）
WEIGHTS: dict[str, float] = {
    "event_type": 0.45,
    "location": 0.25,
    "device_kind": 0.10,
    "severity": 0.10,
    "keyword": 0.10,
}

#: 送入模型的知识字段（白名单）。
#:
#: **不是**把数据库整行丢给模型：device_id / 内网 IP / source / 自增 id
#: 这类字段对分析没有帮助，还会造成不必要的内部信息外发。
CONTEXT_FIELDS: tuple[str, ...] = (
    "event_code",
    "event_type",
    "pre_event_pattern",
    "operator_review",
    "action_taken",
    "result",
    "preventive_suggestion",
)

#: 关键词表：把当前观测映射到知识库里的前兆用语
_KEYWORD_GROUPS: dict[str, tuple[str, ...]] = {
    "堆积": ("堆积", "积料", "堵料", "料面", "挡料板"),
    "下降": ("下降", "下探", "降幅", "降低", "回落"),
    "速率": ("速率", "cm/分钟", "快速", "平缓", "逐渐"),
    "速度": ("输送速度", "速度", "变频器", "打滑", "降速"),
    "波动": ("波动", "周期性", "往复", "节拍", "不均"),
    "标准差": ("标准差", "不平整", "扰动", "瞬时"),
    "覆盖率": ("覆盖率", "形态", "置信度"),
    "环境": ("温度", "湿度", "负载"),
    "刷新": ("刷新", "雷达数据", "采样"),
    "人员": ("人员", "护栏", "安全"),
}


@dataclass(slots=True)
class CurrentEventContext:
    """当前待分析的监测事件（只放系统真实存在的字段）。"""

    #: 分析阶段：warning / alarm
    stage: str
    #: 点位名称，例如「制丝线 2 号输送段」
    location: str
    #: 异常类型，例如「物料堆积」
    event_type: str
    #: 风险指数 0~100
    risk_index: float = 0.0
    #: 雷达测距（m），无雷达时为 None
    distance: float | None = None
    #: 基准距离（m）
    baseline_distance: float | None = None
    #: 物料覆盖率 0~1
    coverage: float | None = None
    #: 视觉判定标签（中文）
    vision_label: str = ""
    #: 视觉置信度 0~1
    vision_confidence: float | None = None
    #: 输送有效速度（m/s）
    conveyor_speed: float | None = None
    #: 环境温度（℃）
    temperature: float | None = None
    #: 环境湿度（%）
    humidity: float | None = None
    #: 设备负载
    equipment_load: float | None = None
    #: 是否为雷达点位（影响设备类型打分）
    has_radar: bool = True
    #: 正在分析的报警编号（用于排除自引用）
    event_code: str | None = None


@dataclass(slots=True)
class RetrievedCase:
    """一条被检索出的历史案例。"""

    event_code: str
    event_type: str
    score: float
    #: 打分明细，便于测试断言与排查
    breakdown: dict[str, float] = field(default_factory=dict)
    #: 送入模型的字段（白名单）
    payload: dict[str, str] = field(default_factory=dict)


def _device_kind(has_radar: bool) -> str:
    return "radar" if has_radar else "vision_only"


def _case_device_kind(case: dict) -> str:
    """知识库记录的设备类型：设备编号以 RAD- 开头即雷达点位。"""
    return "radar" if str(case.get("device_id", "")).upper().startswith("RAD") else "vision_only"


def _keyword_overlap(current: CurrentEventContext, case: dict) -> float:
    """当前观测与历史前兆描述的关键词重合度 0~1。"""
    haystack = " ".join(
        str(case.get(key, ""))
        for key in (
            "pre_event_pattern",
            "radar_summary",
            "vision_summary",
            "environment_summary",
        )
    )
    if not haystack:
        return 0.0

    # 当前侧文本：把已有观测拼成一段描述
    parts: list[str] = [current.event_type, current.vision_label]
    if current.distance is not None:
        parts.append("测距下降" if current.stage in ("warning", "alarm") else "测距平稳")
    if current.conveyor_speed is not None:
        parts.append("输送速度")
    if current.coverage is not None and current.coverage > 0.5:
        parts.append("覆盖率")
    probe = " ".join(parts)

    hits = 0
    total = 0
    for tokens in _KEYWORD_GROUPS.values():
        if any(token in probe for token in tokens):
            total += 1
            if any(token in haystack for token in tokens):
                hits += 1
    return hits / total if total else 0.0


def score_case(current: CurrentEventContext, case: dict) -> tuple[float, dict[str, float]]:
    """给一条历史案例打分，返回 (总分, 明细)。"""
    breakdown: dict[str, float] = {}

    # 异常类型：相同给满分 —— 权重最高，保证同类案例优先
    breakdown["event_type"] = 1.0 if case.get("event_type") == current.event_type else 0.0

    # 点位：同一位置更可迁移
    breakdown["location"] = 1.0 if case.get("location") == current.location else 0.0

    # 设备类型
    breakdown["device_kind"] = (
        1.0 if _case_device_kind(case) == _device_kind(current.has_radar) else 0.0
    )

    # 严重程度：用历史测距与当前测距的接近度近似。
    # 知识库里没有风险指数，但有雷达测距描述，取其中的最小值做近似。
    severity = 0.0
    if current.distance is not None:
        numbers = [float(n) for n in re.findall(r"0\.\d{2}", str(case.get("radar_summary", "")))]
        if numbers:
            historical = min(numbers)
            severity = max(0.0, 1.0 - abs(historical - current.distance) / 0.15)
    breakdown["severity"] = severity

    breakdown["keyword"] = _keyword_overlap(current, case)

    total = sum(WEIGHTS[key] * breakdown[key] for key in WEIGHTS)
    return round(total, 4), breakdown


class KnowledgeRetriever:
    """按当前事件检索最相关的历史案例。"""

    def __init__(self, knowledge_base: KnowledgeBase) -> None:
        self._kb = knowledge_base

    def retrieve(
        self,
        current: CurrentEventContext,
        *,
        top_k: int = TOP_K,
        exclude_event_code: str | None = None,
    ) -> list[RetrievedCase]:
        """返回相关度最高的 ``top_k`` 条历史案例。

        ``exclude_event_code`` 用于**分析历史事件时排除它自己** ——
        否则模型会把「这次事件发生之后的处置结果」当成类似历史经验，
        形成自我引用。
        """
        excluded = exclude_event_code or current.event_code
        candidates = self._kb.list_events(limit=200)

        scored: list[RetrievedCase] = []
        for case in candidates:
            code = str(case.get("event_code", ""))
            if excluded and code == excluded:
                continue
            total, breakdown = score_case(current, case)
            scored.append(
                RetrievedCase(
                    event_code=code,
                    event_type=str(case.get("event_type", "")),
                    score=total,
                    breakdown=breakdown,
                    payload={key: str(case.get(key, "")) for key in CONTEXT_FIELDS},
                )
            )

        # 分数相同时按事件编号稳定排序，保证结果可复现
        scored.sort(key=lambda item: (-item.score, item.event_code))
        return scored[: max(1, top_k)]


def knowledge_fingerprint(knowledge_base: KnowledgeBase) -> str:
    """**整库**内容指纹。

    只用于「知识库是否发生过变化」的粗粒度判断。
    缓存 key 请优先用 :func:`cases_fingerprint` —— 见那里的说明。
    """
    rows = knowledge_base.list_events(limit=1000)
    chunks = [
        f"{row.get('event_code')}:{row.get('event_type')}:{row.get('action_taken')}:{row.get('result')}"
        for row in sorted(rows, key=lambda r: str(r.get("event_code", "")))
    ]
    raw = f"{len(rows)}|" + "|".join(chunks)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def cases_fingerprint(cases: list[RetrievedCase]) -> str:
    """**实际送进 Prompt 的那几条**案例的指纹。

    为什么不直接用整库指纹：引擎会持续新增报警记录，整库指纹每次都变，
    缓存就会永久失效 —— 而只要检索出的 Top-K 内容没变，
    模型拿到的上下文其实完全相同，没有重新调用的必要。

    这里用「实际案例」做指纹，既能保证知识真的变了就重新分析，
    又不会因为无关记录新增而反复消耗模型 Token。
    """
    if not cases:
        return "no-cases"
    chunks = [
        f"{case.event_code}|{json.dumps(case.payload, ensure_ascii=False, sort_keys=True)}"
        for case in cases
    ]
    raw = "||".join(chunks)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
