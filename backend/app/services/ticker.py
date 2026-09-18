"""后台 tick 线程。

按资料口径以 10 Hz 推进数据引擎。使用独立的守护线程而不是 asyncio 任务，
原因是引擎本身是纯同步实现（并配 threading.Lock 保证并发安全），
用线程驱动最简单、也最容易在测试中单独调用 ``engine.tick()``。
"""

from __future__ import annotations

import logging
import threading
import time

from app.services.simulation import get_engine

logger = logging.getLogger(__name__)

#: 10 Hz
TICK_INTERVAL = 0.1


class SimulationTicker:
    """以固定频率驱动 SimulationEngine。"""

    def __init__(self, interval: float = TICK_INTERVAL) -> None:
        self._interval = interval
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="simulation-ticker", daemon=True
        )
        self._thread.start()
        logger.info("采集 tick 线程已启动（间隔 %.3f s）", self._interval)

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)
        self._thread = None
        logger.info("采集 tick 线程已停止")

    @property
    def alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run(self) -> None:
        engine = get_engine()
        next_at = time.perf_counter()

        while not self._stop.is_set():
            try:
                engine.tick()
            except Exception:  # pragma: no cover - 守护线程不能因异常退出
                logger.exception("采集 tick 执行异常，已跳过本次")

            next_at += self._interval
            sleep_for = next_at - time.perf_counter()
            if sleep_for < -self._interval:
                # 明显落后（例如机器休眠）时重新对齐，避免追赶风暴
                next_at = time.perf_counter()
                sleep_for = self._interval
            if sleep_for > 0:
                self._stop.wait(sleep_for)


ticker = SimulationTicker()
