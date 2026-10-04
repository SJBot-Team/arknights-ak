"""任务流水线：JSON 定义的「识别 → 动作 → 跳转」图，MAA tasks.json 风格但更小。

节点字段（全部可选，除 id/recognize 外）：
    id            节点唯一名
    roi           相对参考矩形的 [l, t, r, b]（0~1）；缺省=全帧
    recognize     {"type": "template|color|always|ocr", ...参数}
    interval_ms   该节点最短识别间隔（节流；默认 0=每帧）
    timeout_ms    从进入该节点起，多久没识别到算超时
    on_found      命中后执行的动作列表
    on_timeout    超时后执行的动作列表（可选）
    next          命中后跳转的节点 id（null=结束/停留）
    on_timeout_goto 超时后跳转的节点 id
    loop          命中后是否停留本节点重复（默认 False）
    labels        便于阅读的说明
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .types import ActionSpec, Context, Match, Rect


@dataclass
class Node:
    id: str
    recognize: dict = field(default_factory=dict)
    roi: list[float] | None = None
    interval_ms: int = 0
    timeout_ms: int | None = None
    on_found: list[dict] = field(default_factory=list)
    on_timeout: list[dict] = field(default_factory=list)
    next: str | None = None
    on_timeout_goto: str | None = None
    loop: bool = False
    labels: str = ""

    # 运行态
    entered_at: float = 0.0
    last_run: float = 0.0
    hits: int = 0
    misses: int = 0


class Pipeline:
    def __init__(self, data: dict):
        self.name = data.get("name", "pipeline")
        self.description = data.get("description", "")
        self.start = data.get("start")
        raw_nodes = data.get("nodes", [])
        self.nodes: dict[str, Node] = {}
        for n in raw_nodes:
            node = Node(
                id=n["id"],
                recognize=n.get("recognize", {}),
                roi=n.get("roi"),
                interval_ms=int(n.get("interval_ms", 0)),
                timeout_ms=n.get("timeout_ms"),
                on_found=n.get("on_found", []),
                on_timeout=n.get("on_timeout", []),
                next=n.get("next"),
                on_timeout_goto=n.get("on_timeout_goto"),
                loop=bool(n.get("loop", False)),
                labels=n.get("labels", ""),
            )
            self.nodes[node.id] = node
        if not self.start and self.nodes:
            self.start = next(iter(self.nodes))

    @staticmethod
    def load(path: str | Path) -> "Pipeline":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return Pipeline(data)

    def roi_rect(self, node: Node, ctx: Context) -> Rect | None:
        if not node.roi:
            return None
        base = ctx.base_rect()
        return Rect.from_rel(tuple(node.roi), base)  # type: ignore[arg-type]

    def actions(self, items: list[dict]) -> list[ActionSpec]:
        return [ActionSpec(kind=a["kind"], params=a.get("params", {})) for a in items]


@dataclass
class StepResult:
    node_id: str
    matched: bool
    match: Match | None
    dropped: bool = False          # 本帧被节流跳过
    timed_out: bool = False
    next_node: str | None = None
    elapsed_ms: float = 0.0


class Runner:
    """流水线执行器：内核每帧调用 step()，返回本帧结果。"""

    def __init__(self, pipeline: Pipeline):
        self.pipeline = pipeline
        self.current: str | None = pipeline.start
        self.finished = False
        self.history: list[StepResult] = []
        if self.current:
            self.pipeline.nodes[self.current].entered_at = time.perf_counter()

    def step(self, engine, ctx: Context, frame) -> StepResult:
        if self.finished or self.current is None:
            return StepResult(node_id="<done>", matched=False, match=None)
        node = self.pipeline.nodes[self.current]
        now = time.perf_counter()

        # 节流
        if node.interval_ms and (now - node.last_run) * 1000 < node.interval_ms:
            return StepResult(node_id=node.id, matched=False, match=None, dropped=True)
        node.last_run = now

        roi = self.pipeline.roi_rect(node, ctx)
        t0 = time.perf_counter()
        match = engine.recognize(node.recognize, frame, ctx, roi, label=node.id)
        elapsed = (time.perf_counter() - t0) * 1000

        if match is not None:
            node.hits += 1
            ctx.variables[f"match:{node.id}"] = match
            for spec in self.pipeline.actions(node.on_found):
                engine.do(spec, ctx)
            nxt = node.id if node.loop else node.next
            self._goto(nxt)
            res = StepResult(node.id, True, match, next_node=nxt, elapsed_ms=elapsed)
        else:
            node.misses += 1
            timed_out = bool(node.timeout_ms) and (now - node.entered_at) * 1000 > node.timeout_ms
            if timed_out:
                for spec in self.pipeline.actions(node.on_timeout):
                    engine.do(spec, ctx)
                self._goto(node.on_timeout_goto)
            res = StepResult(node.id, False, None, timed_out=timed_out,
                             next_node=node.on_timeout_goto if timed_out else None,
                             elapsed_ms=elapsed)
        if len(self.history) < 5000:
            self.history.append(res)
        return res

    def _goto(self, node_id: str | None) -> None:
        if node_id is None:
            self.finished = True
            self.current = None
            return
        if node_id not in self.pipeline.nodes:
            raise KeyError(f"流水线跳转到不存在的节点: {node_id}")
        self.current = node_id
        self.pipeline.nodes[node_id].entered_at = time.perf_counter()

    def summary(self) -> dict[str, Any]:
        hits = {n.id: n.hits for n in self.pipeline.nodes.values() if n.hits}
        return {
            "pipeline": self.pipeline.name,
            "finished": self.finished,
            "current": self.current,
            "steps": len(self.history),
            "hits": hits,
        }
