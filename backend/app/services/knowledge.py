"""知识库：历史异常处理经验库（SQLite）。

为什么用 SQLite：比赛演示阶段只需要一个可查询、可持久化、零运维的经验库，
引入 Milvus / Elasticsearch / 向量数据库属于明显的过度设计。

种子数据说明
------------
``knowledge_event`` 中 12 条记录按真实生产记录格式撰写。其中：

* ``EVT-20250519-02``、``EVT-20250517-01``、``EVT-20250517-02`` 直接取自原始资料
  （2025-05-19 加料堵料事件与钉钉自动报警机器人推送记录）；
* 其余为同一格式的高仿真样例，用于覆盖不同异常类型，不伪装成真实发生过的记录
  （``source`` 字段区分 ``documented`` / ``sample``）。
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from app.config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS knowledge_event (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    event_code            TEXT    NOT NULL UNIQUE,
    timestamp             TEXT    NOT NULL,
    device_id             TEXT    NOT NULL,
    location              TEXT    NOT NULL,
    event_type            TEXT    NOT NULL,
    radar_summary         TEXT    NOT NULL,
    vision_summary        TEXT    NOT NULL,
    environment_summary   TEXT    NOT NULL,
    pre_event_pattern     TEXT    NOT NULL,
    operator_review       TEXT    NOT NULL,
    action_taken          TEXT    NOT NULL,
    result                TEXT    NOT NULL,
    preventive_suggestion TEXT    NOT NULL,
    source                TEXT    NOT NULL DEFAULT 'sample'
);

CREATE INDEX IF NOT EXISTS idx_knowledge_timestamp ON knowledge_event(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_knowledge_type      ON knowledge_event(event_type);
"""

#: 种子数据：(event_code, timestamp, device_id, location, event_type,
#:            radar_summary, vision_summary, environment_summary,
#:            pre_event_pattern, operator_review, action_taken, result,
#:            preventive_suggestion, source)
SEED_EVENTS: tuple[tuple[str, ...], ...] = (
    (
        "EVT-20250519-02",
        "2025-05-19 13:34:15",
        "RAD-02",
        "制丝线 2 号输送段",
        "物料堆积",
        "13:18 起雷达测距均值由 0.71 m 逐步下降至 0.62 m，滤波值同步跟随，无跳变；"
        "13:31 联合风险指数达到 72%，13:34 测距 0.58 m 触发报警。",
        "13:27 后视觉模型检测到输送区域物料覆盖率持续增加，"
        "类别判定为物料堆积，置信度 91.4%。",
        "环境温度 23.8 ℃、湿度 52%，处于正常区间，未出现剧烈变化；"
        "输送有效速度较基准下降约 0.12 m/s。",
        "测距连续下降 13 分钟（0.71→0.62 m）且下降速率逐步加快；"
        "视觉覆盖率同步上升约 21 个百分点；输送速度出现下降。",
        "现场人员确认进料量短时间升高，同时下游输送速度降低。",
        "降低上游进料量并检查输送设备。",
        "约 4 分钟后物料恢复正常，测距回到 0.70 m 附近，风险指数回落至低风险区间。",
        "进料量与下游输送速度需保持匹配；测距连续下降超过 8 分钟即应安排现场巡检。",
        "documented",
    ),
    (
        "EVT-20250517-01",
        "2025-05-17 09:29:14",
        "RAD-02",
        "制丝线 2 号输送段",
        "物料堆积",
        "09:21 起测距由 0.70 m 缓降至 0.60 m，移动标准差由 0.004 升至 0.011，"
        "表明料面开始不平整。",
        "视觉模型在 09:25 检出物料堆积形态，置信度 88.6%。",
        "温度 24.1 ℃、湿度 51%，输送负载上升约 9%。",
        "测距下降伴随移动标准差增大，是料层开始堆积的典型早期特征。",
        "值班人员经钉钉推送后到场确认落料口有积料。",
        "清理落料口积料，并调整喂料机频率。",
        "处理后 6 分钟测距恢复至 0.69 m。",
        "关注测距移动标准差的增大趋势，它比平均值更早反映堆积风险。",
        "documented",
    ),
    (
        "EVT-20250517-02",
        "2025-05-17 09:31:34",
        "RAD-02",
        "制丝线 2 号输送段",
        "物料堆积",
        "该次为同一工况下的持续报警，测距维持在 0.59~0.61 m 区间。",
        "视觉覆盖率维持在 62%~68%，判定为物料堆积。",
        "环境参数稳定，说明本次异常由物料流量而非环境因素引起。",
        "短时间重复报警，说明处置尚未生效。",
        "与上一次报警为同一事件延续，现场正在处置中。",
        "合并处理，避免重复派工。",
        "与 EVT-20250517-01 合并归档。",
        "同类报警在 5 分钟内重复出现时应合并为同一事件处理。",
        "documented",
    ),
    (
        "EVT-20250312-01",
        "2025-03-12 10:07:41",
        "RAD-02",
        "制丝线 2 号输送段",
        "输送速度下降",
        "测距保持 0.70~0.72 m 基本平稳，未出现单向下降。",
        "视觉模型未检出堆积形态，覆盖率维持在 19%~23%，判定为正常输送。",
        "输送有效速度由 1.20 m/s 降至 1.09 m/s，设备负载上升 7%。",
        "雷达与视觉均正常，仅输送速度单项下降 —— 典型的需要联合判断才能正确解释的工况。",
        "现场确认为变频器输出波动，输送带无异常。",
        "复紧输送带张紧装置后恢复。",
        "速度在 3 分钟内回到 1.19 m/s。",
        "雷达与视觉均正常而速度下降时，应优先排查传动与变频器，而非物料堆积。",
        "sample",
    ),
    (
        "EVT-20250328-01",
        "2025-03-28 15:42:09",
        "RAD-01",
        "制丝线 1 号输送段",
        "物料流量波动",
        "测距在 0.66~0.74 m 之间往复波动，无持续单向趋势。",
        "视觉覆盖率在 30%~55% 之间快速变化，未形成稳定堆积形态。",
        "温度湿度稳定。",
        "波动呈周期性（周期约 90 秒），与上游喂料机的给料节拍一致。",
        "确认为上游喂料机给料不均，非设备故障。",
        "调整喂料机给料频率，使料流更均匀。",
        "波动幅度收窄至 0.69~0.73 m。",
        "周期性波动应结合上游设备节拍判断，避免误报为堆积。",
        "sample",
    ),
    (
        "EVT-20250408-01",
        "2025-04-08 08:55:22",
        "RAD-03",
        "制丝线 3 号输送段",
        "物料堆积",
        "08:44 起测距由 0.72 m 降至 0.63 m，08:53 降至 0.59 m。",
        "视觉模型检出堆积形态，置信度 90.2%，覆盖率升至 66%。",
        "设备负载上升 11%，温度无异常。",
        "测距下降速率约 0.9 cm/分钟，属中等发展速度。",
        "现场确认 3 号输送段出口挡料板位置偏移，导致物料排出不畅。",
        "校正挡料板位置并紧固。",
        "测距在 5 分钟内回到 0.71 m。",
        "挡料板等机械部件偏移也会表现为测距下降，处置时需一并检查。",
        "sample",
    ),
    (
        "EVT-20250422-01",
        "2025-04-22 14:18:33",
        "CAM-05",
        "叶线提升段",
        "人员进入检测区",
        "该点位未配备激光雷达，本次由视觉单独判断。",
        "视觉模型在提升段护栏内侧检出人员目标，置信度 93.7%，持续 12 秒后离开。",
        "环境参数正常。",
        "人员在设备运行期间进入提升段护栏内侧，属安全规范要求关注的场景。",
        "经核实为巡检人员抄近路穿越，未发生危险。",
        "现场提醒并按安全管理规定记录，班组会上重申行走路线。",
        "已完成安全教育，后续一个月未再出现同类情况。",
        "仅配摄像头的点位应保持人员检测常开，作为安全管理补充手段。",
        "sample",
    ),
    (
        "EVT-20250506-01",
        "2025-05-06 11:26:57",
        "RAD-02",
        "制丝线 2 号输送段",
        "物料堆积",
        "测距由 0.71 m 缓降至 0.64 m，耗时 11 分钟，下降平缓。",
        "视觉覆盖率由 24% 升至 51%，类别为疑似物料堆积，置信度 84.1%。",
        "输送速度下降 0.06 m/s，温度湿度稳定。",
        "下降平缓、视觉置信度中等 —— 属于「关注」级别，尚未达到预警强度。",
        "确认为换批期间进料量临时增加，属工艺正常波动。",
        "保持观察，未做现场干预。",
        "换批结束后自行恢复，测距回到 0.70 m。",
        "换批时段应适当放宽阈值，避免工艺正常波动产生大量无效预警。",
        "sample",
    ),
    (
        "EVT-20250523-01",
        "2025-05-23 16:44:12",
        "RAD-01",
        "制丝线 1 号输送段",
        "物料堆积",
        "测距由 0.72 m 快速降至 0.58 m，仅耗时 7 分钟。",
        "视觉模型检出物料堆积，置信度 92.8%，覆盖率升至 71%。",
        "设备负载上升 14%，温度上升 0.6 ℃。",
        "下降速率达 2.0 cm/分钟，属快速发展型异常，预警窗口很短。",
        "现场确认下游输送带打滑，导致物料在 1 号段滞留。",
        "停机检查并更换磨损的输送带滚筒包胶。",
        "更换后测距恢复至 0.71 m，连续观察 3 天无复发。",
        "下降速率超过 1.5 cm/分钟时应直接升级为严重报警，缩短响应时间。",
        "sample",
    ),
    (
        "EVT-20250604-01",
        "2025-06-04 21:44:12",
        "RAD-02",
        "制丝线 2 号输送段",
        "物料堆积",
        "系统生成异常时域曲线图 plot_test_2025-06-04 21-44-12.png，"
        "测距在 0.61~0.71 m 之间出现明显下探后回升。",
        "视觉覆盖率短时升至 58%，未形成持续堆积。",
        "输送速度出现 0.04 m/s 的短时下探后恢复。",
        "单次下探后立即回升，属于瞬时扰动而非堆积发展过程。",
        "现场确认有物料团块通过，属正常输送现象。",
        "无需处置。",
        "曲线自行恢复，未生成报警。",
        "瞬时下探不应触发报警；系统需以趋势持续时间而非单点越限作为判据。",
        "sample",
    ),
    (
        "EVT-20250611-01",
        "2025-06-11 09:12:38",
        "RAD-03",
        "制丝线 3 号输送段",
        "输送速度下降",
        "测距稳定在 0.70~0.72 m，雷达数据刷新正常。",
        "视觉判定为正常输送，覆盖率 20%~24%。",
        "输送有效速度由 1.20 m/s 降至 1.02 m/s，为本月最大降幅。",
        "速度单项大幅下降，雷达与视觉均正常。",
        "现场确认为下游设备联锁降速，属计划内的工艺调整。",
        "与生产调度确认后维持运行。",
        "按计划恢复正常速度。",
        "与生产调度建立信息同步机制，避免计划性降速被误判为异常。",
        "sample",
    ),
    (
        "EVT-20250618-01",
        "2025-06-18 13:58:04",
        "RAD-02",
        "制丝线 2 号输送段",
        "物料堆积",
        "13:46 起测距由 0.71 m 降至 0.63 m，13:55 降至 0.60 m 并触发预警。",
        "视觉覆盖率由 22% 升至 60%，置信度 89.3%。",
        "设备负载上升 10%，环境参数稳定。",
        "与 EVT-20250519-02 前兆模式相似度较高：下降持续约 9 分钟、速率逐渐加快。",
        "现场确认上游电子秤计量偏差导致进料量偏大。",
        "校准电子秤并调整进料量设定值。",
        "测距在 4 分钟后回到 0.70 m。",
        "测距下降前兆出现时，可同步核对上游计量设备的最近校准记录。",
        "sample",
    ),
)


class KnowledgeBase:
    """知识库访问对象。线程安全（每次操作使用独立连接 + 全局写锁）。"""

    def __init__(self, db_path: Path | str) -> None:
        self._path = Path(db_path)
        self._write_lock = threading.Lock()
        self._is_memory = str(db_path) == ":memory:"
        self._memory_conn: sqlite3.Connection | None = None

    # ---- 连接管理 -----------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        if self._is_memory:
            if self._memory_conn is None:
                self._memory_conn = sqlite3.connect(":memory:", check_same_thread=False)
                self._memory_conn.row_factory = sqlite3.Row
                self._memory_conn.executescript(_SCHEMA)
            return self._memory_conn

        self._path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.executescript(_SCHEMA)
        return conn

    def initialize(self, *, force: bool = False) -> int:
        """建表并写入种子数据。返回当前记录数。"""
        with self._write_lock:
            conn = self._connect()
            try:
                if force:
                    conn.execute("DELETE FROM knowledge_event")
                    conn.commit()

                existing = conn.execute("SELECT COUNT(*) AS c FROM knowledge_event").fetchone()["c"]
                if existing == 0:
                    conn.executemany(
                        """
                        INSERT INTO knowledge_event (
                            event_code, timestamp, device_id, location, event_type,
                            radar_summary, vision_summary, environment_summary,
                            pre_event_pattern, operator_review, action_taken, result,
                            preventive_suggestion, source
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        SEED_EVENTS,
                    )
                    conn.commit()
                return int(
                    conn.execute("SELECT COUNT(*) AS c FROM knowledge_event").fetchone()["c"]
                )
            finally:
                if not self._is_memory:
                    conn.close()

    # ---- 查询 ---------------------------------------------------------------

    def list_events(
        self,
        *,
        keyword: str | None = None,
        event_type: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        conn = self._connect()
        try:
            sql = "SELECT * FROM knowledge_event WHERE 1=1"
            params: list[object] = []
            if event_type:
                sql += " AND event_type = ?"
                params.append(event_type)
            if keyword:
                # 全文关键词检索：覆盖事件编号、位置、类型与全部描述字段
                sql += (
                    " AND (event_code LIKE ?"
                    " OR location LIKE ?"
                    " OR event_type LIKE ?"
                    " OR radar_summary LIKE ?"
                    " OR vision_summary LIKE ?"
                    " OR environment_summary LIKE ?"
                    " OR pre_event_pattern LIKE ?"
                    " OR operator_review LIKE ?"
                    " OR action_taken LIKE ?"
                    " OR result LIKE ?"
                    " OR preventive_suggestion LIKE ?)"
                )
                like = f"%{keyword}%"
                params.extend([like] * 11)
            sql += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            return [dict(row) for row in conn.execute(sql, params).fetchall()]
        finally:
            if not self._is_memory:
                conn.close()

    def event_types(self) -> list[str]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT DISTINCT event_type FROM knowledge_event ORDER BY event_type"
            ).fetchall()
            return [row["event_type"] for row in rows]
        finally:
            if not self._is_memory:
                conn.close()

    def get(self, event_code: str) -> dict | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM knowledge_event WHERE event_code = ?", (event_code,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            if not self._is_memory:
                conn.close()


_kb: KnowledgeBase | None = None
_kb_lock = threading.Lock()


def get_knowledge_base() -> KnowledgeBase:
    global _kb
    if _kb is None:
        with _kb_lock:
            if _kb is None:
                _kb = KnowledgeBase(settings.db_path)
                _kb.initialize()
    return _kb


def reset_knowledge_base(db_path: Path | str | None = None) -> KnowledgeBase:
    """重建知识库实例（测试用）。"""
    global _kb
    with _kb_lock:
        _kb = KnowledgeBase(db_path if db_path is not None else settings.db_path)
        _kb.initialize(force=True)
    return _kb
