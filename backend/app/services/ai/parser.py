"""模型输出解析。

模型输出必须当作**不可信外部文本**处理：
- 不执行、不渲染 HTML；
- 优先按 JSON 解析；被 Markdown 代码块包住就先剥离；
- 仍解析不了就原样保留为 ``fallback_text``，页面照样能展示。

**不能因为模型多写了两个字就返回 500。**
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

#: 解析出的字段（与提示词里的输出结构一致）
LIST_FIELDS: tuple[str, ...] = (
    "possible_causes",
    "recommended_checks",
    "recommended_actions",
    "related_cases",
    "evidence_basis",
)

#: 各列表字段最多保留的条数（模型可能不听话多写几条）
MAX_ITEMS: dict[str, int] = {
    "possible_causes": 3,
    "recommended_checks": 4,
    "recommended_actions": 4,
    "related_cases": 5,
    "evidence_basis": 5,
}

#: 单条文本长度上限，避免异常长文本撑爆页面
MAX_ITEM_CHARS = 300

_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL | re.IGNORECASE)
#: 从混杂文本里抠出第一个 JSON 对象
_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


@dataclass(slots=True)
class ParsedAnalysis:
    """解析结果。``structured`` 为 False 时表示只能作为纯文本展示。"""

    summary: str = ""
    possible_causes: list[str] = field(default_factory=list)
    recommended_checks: list[str] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)
    related_cases: list[str] = field(default_factory=list)
    evidence_basis: list[str] = field(default_factory=list)
    fallback_text: str = ""
    structured: bool = False


def _clean_text(value: object) -> str:
    text = str(value).strip()
    text = text.replace("\r\n", "\n")
    if len(text) > MAX_ITEM_CHARS:
        text = text[:MAX_ITEM_CHARS] + "…"
    return text


def _clean_list(value: object, limit: int) -> list[str]:
    """把任意值整理成字符串列表。

    模型可能返回字符串、字符串数组，甚至对象数组 —— 都尽力兼容，
    而不是直接判定失败。
    """
    if value is None:
        return []
    items: list[object]
    if isinstance(value, str):
        # 允许模型用换行或分号分隔
        parts = re.split(r"[\n;；]+", value)
        items = [p for p in parts if p.strip()]
    elif isinstance(value, list):
        items = value
    else:
        items = [value]

    result: list[str] = []
    for item in items:
        if isinstance(item, dict):
            # 例如 {"case": "EVT-..."} 或 {"item": "..."}
            inner = item.get("item") or item.get("text") or item.get("value")
            if inner is None:
                inner = "；".join(f"{k}:{v}" for k, v in item.items())
            text = _clean_text(inner)
        else:
            text = _clean_text(item)
        if text:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def strip_code_fence(text: str) -> str:
    """剥离 Markdown 代码块包裹。"""
    match = _FENCE_RE.match(text)
    if match:
        return match.group(1).strip()
    return text.strip()


def _try_load(text: str) -> dict | None:
    """尽最大努力把文本解析成 JSON 对象。"""
    for candidate in (strip_code_fence(text), text.strip()):
        try:
            data = json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(data, dict):
            return data

    # 文本里混了说明时，抠出第一个对象再试
    match = _OBJECT_RE.search(strip_code_fence(text))
    if match:
        try:
            data = json.loads(match.group(0))
        except (json.JSONDecodeError, ValueError):
            return None
        if isinstance(data, dict):
            return data
    return None


def parse_analysis(text: str) -> ParsedAnalysis:
    """解析模型输出。

    能解出 JSON 就用结构化字段；解不出则整段保留为 ``fallback_text``。
    """
    raw = (text or "").strip()
    if not raw:
        return ParsedAnalysis(fallback_text="", structured=False)

    data = _try_load(raw)
    if data is None:
        # 解析失败也要能用：把原文作为纯文本呈现
        return ParsedAnalysis(fallback_text=raw, structured=False)

    summary = _clean_text(data.get("summary", "")) if data.get("summary") else ""
    parsed = ParsedAnalysis(
        summary=summary,
        structured=bool(summary),
        fallback_text="" if summary else raw,
    )
    for key in LIST_FIELDS:
        setattr(parsed, key, _clean_list(data.get(key), MAX_ITEMS[key]))
    return parsed
