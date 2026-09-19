"""Prompt 构建：把当前事件 + Top-K 历史案例组装成模型输入。

两条硬约束
----------
1. **Prompt 完全由后端生成。** 接口不接受自由文本 prompt，
   否则平台会变成一个公开的 LLM 代理。
2. **最小必要信息。** 不下发设备内网 IP、数据库字段、源码路径、
   API Key、服务器地址 —— 这些对判断异常原因没有帮助。
"""

from __future__ import annotations

import json

from app.services.ai.retriever import CurrentEventContext, RetrievedCase

#: 系统提示词。
#:
#: 明确三件事：模型**不参与**报警判定、只能用给定数据、证据不足要直说。
BASE_SYSTEM_PROMPT = """你是制丝线物流监控系统的辅助分析模块。

系统已经用雷达、视觉与联合判定规则完成了风险判定，判定结果不由你修改。
你的任务是：根据给定的当前监测数据和历史异常事件，给出原因分析与处置建议。

必须遵守：
1. 只能使用下面提供的数据和历史知识，不得引入外部假设
2. 不得虚构传感器数据、设备状态或现场情况
3. 不得声称执行了系统没有执行的操作（例如"已停机""已通知现场"）
4. 不得修改或质疑系统给出的报警等级
5. 不得替代系统的安全规则；你的输出只是辅助参考
6. 如果提供的数据不足以判断，明确写"当前证据不足以确定"
7. 引用历史经验时，优先写出历史事件编号
8. 建议要具体、简短、可操作，避免泛泛而谈
9. 输出使用中文"""

#: 阶段化任务说明 —— warning 侧重提前干预，alarm 侧重当前处置
STAGE_PROMPT: dict[str, str] = {
    "warning": """当前阶段是**预警**：风险正在上升，但尚未达到异常判定条件。
请侧重提前干预：
- 说明风险趋势说明了什么
- 给出最可能的原因
- 指出应重点检查的位置或环节
- 给出预防性处理建议（在情况恶化前做什么）
- 参考历史相似案例的前兆与处置方式""",
    "alarm": """当前阶段是**报警**：已经达到异常判定条件，需要立即处置。
请侧重当前处置：
- 概括异常现状与关键证据
- 指出最可能的原因
- 按优先级列出检查项
- 给出处置顺序（先做什么、后做什么）
- 参考历史类似事件的处理经验与结果""",
}

#: 输出结构要求。不使用 response_format=json_schema ——
#: 并非所有 llama.cpp / 兼容服务都支持，改为在提示词里要求 JSON。
OUTPUT_FORMAT_PROMPT = """请只输出一个 JSON 对象，不要输出任何解释性文字或 Markdown 代码块标记。
字段如下：
{
  "summary": "1~2 句话概括当前情况",
  "possible_causes": ["可能原因，最多 3 条"],
  "recommended_checks": ["建议检查项，最多 4 条"],
  "recommended_actions": ["建议处置，最多 4 条"],
  "related_cases": ["参考的历史事件编号"],
  "evidence_basis": ["本次分析依据了哪些当前指标"]
}
所有字符串使用中文。数组元素是字符串，不要嵌套对象。"""


def _fmt(value: float | None, unit: str = "", digits: int = 2) -> str | None:
    if value is None:
        return None
    return f"{value:.{digits}f}{unit}"


def current_event_lines(current: CurrentEventContext) -> list[str]:
    """把当前事件整理成「字段：值」列表，**只含有值的字段**。

    没有值的字段直接省略 —— 宁可少给，也不编造。
    """
    lines = [
        f"分析阶段：{'预警（warning）' if current.stage == 'warning' else '报警（alarm）'}",
        f"监控点位：{current.location}",
        f"异常类型：{current.event_type}",
    ]
    if current.event_code:
        lines.append(f"事件编号：{current.event_code}")
    lines.append(f"风险指数：{current.risk_index:.1f}%")

    distance = _fmt(current.distance, " m", 3)
    if distance:
        lines.append(f"雷达当前测距：{distance}")
    baseline = _fmt(current.baseline_distance, " m", 3)
    if baseline:
        lines.append(f"雷达基准距离：{baseline}")
    if current.distance is not None and current.baseline_distance is not None:
        delta = current.distance - current.baseline_distance
        lines.append(f"相对基准变化：{delta:+.3f} m")

    if current.vision_label:
        lines.append(f"视觉判定：{current.vision_label}")
    if current.vision_confidence is not None:
        lines.append(f"视觉置信度：{current.vision_confidence * 100:.1f}%")
    coverage = _fmt(current.coverage * 100 if current.coverage is not None else None, "%", 1)
    if coverage:
        lines.append(f"物料覆盖率：{coverage}")

    speed = _fmt(current.conveyor_speed, " m/s", 2)
    if speed:
        lines.append(f"输送有效速度：{speed}")
    temperature = _fmt(current.temperature, " ℃", 1)
    if temperature:
        lines.append(f"环境温度：{temperature}")
    humidity = _fmt(current.humidity, " %", 0)
    if humidity:
        lines.append(f"环境湿度：{humidity}")
    load = _fmt(current.equipment_load, "", 1)
    if load:
        lines.append(f"设备负载：{load}")

    lines.append(f"点位类型：{'雷达 + 视觉' if current.has_radar else '仅视觉'}")
    return lines


def case_lines(case: RetrievedCase) -> list[str]:
    """把一条历史案例整理成模型可读的段落（白名单字段）。"""
    payload = case.payload
    lines = [f"【{payload.get('event_code', '')}】异常类型：{payload.get('event_type', '')}"]
    mapping = (
        ("pre_event_pattern", "异常前兆"),
        ("operator_review", "人工复核"),
        ("action_taken", "处理措施"),
        ("result", "处理结果"),
        ("preventive_suggestion", "预防建议"),
    )
    for key, label in mapping:
        value = payload.get(key)
        if value:
            lines.append(f"  {label}：{value}")
    return lines


def build_user_prompt(
    current: CurrentEventContext,
    cases: list[RetrievedCase],
) -> str:
    """组装用户消息。"""
    parts: list[str] = []

    stage_task = STAGE_PROMPT.get(current.stage, STAGE_PROMPT["alarm"])
    parts.append(stage_task)

    parts.append("\n## 当前监测数据\n" + "\n".join(current_event_lines(current)))

    if cases:
        parts.append("\n## 历史相似案例（按相关度排序）")
        for case in cases:
            parts.append("\n".join(case_lines(case)))
    else:
        parts.append("\n## 历史相似案例\n知识库中没有可参考的相似案例。")

    parts.append("\n## 输出要求\n" + OUTPUT_FORMAT_PROMPT)
    return "\n".join(parts)


def context_snapshot(current: CurrentEventContext, cases: list[RetrievedCase]) -> dict:
    """缓存 key 用的上下文摘要（不含任何敏感信息）。"""
    return {
        "stage": current.stage,
        "location": current.location,
        "event_type": current.event_type,
        "risk_index": current.risk_index,
        "event_code": current.event_code,
        "cases": [case.event_code for case in cases],
    }


def context_as_json(current: CurrentEventContext, cases: list[RetrievedCase]) -> str:
    """调试用：把上下文序列化（仅本地排查，不写日志）。"""
    return json.dumps(
        {"current": current_event_lines(current), "cases": [c.payload for c in cases]},
        ensure_ascii=False,
        indent=2,
    )
