"""pytest 共享夹具。

关键点：每个测试开始前把仿真引擎与知识库都重置到确定状态，
因此测试之间互不影响，也不会因为后台 tick 或残留状态而不稳定。

  * 引擎使用固定 seed（``TEST_SEED``），随机数可复现；
  * 知识库使用 SQLite 内存库（``:memory:``），测试不写磁盘、不留垃圾文件；
  * 测试里使用 ``TestClient(app)`` 而不进入上下文管理器，
    这样 lifespan 不会启动后台 tick 线程 —— 仿真推进完全由测试显式控制。
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.knowledge import reset_knowledge_base
from app.services.simulation import reset_engine

TEST_SEED = 20250519


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def fresh_state() -> Iterator[None]:
    """每个测试都用全新的引擎与内存知识库。"""
    reset_engine(seed=TEST_SEED)
    reset_knowledge_base(":memory:")
    yield
    reset_engine(seed=TEST_SEED)
