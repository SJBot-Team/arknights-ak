"""自检：不依赖窗口/游戏，验证内核可用（插件加载、模板匹配、颜色识别、流水线跑通）。"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from kernel import Engine, Pipeline, Runner  # noqa: E402


def make_fake_screen(tmp: Path) -> Path:
    """造一张"假屏幕"：白底 + 一个绿色按钮 + 一块红色状态点。"""
    img = np.full((720, 1280, 3), 240, dtype=np.uint8)
    cv2.rectangle(img, (100, 100), (300, 160), (60, 160, 60), -1)     # 绿色按钮
    cv2.putText(img, "START", (140, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
    cv2.circle(img, (1100, 600), 18, (0, 0, 220), -1)                 # 红色状态点
    p = tmp / "fake_screen.png"
    cv2.imwrite(str(p), img)
    return p


def main():
    tmp = Path(tempfile.mkdtemp(prefix="vision_selftest_"))
    tpl_dir = tmp / "templates"
    (tpl_dir / "ui").mkdir(parents=True, exist_ok=True)

    screen_path = make_fake_screen(tmp)
    screen = cv2.imread(str(screen_path))

    # 从假屏幕裁出模板 → 放入模板库
    cv2.imwrite(str(tpl_dir / "ui" / "start_button.png"), screen[100:161, 100:301])
    cv2.imwrite(str(tpl_dir / "ui" / "status_dot.png"), screen[582:619, 1082:1119])

    print(f"[1] 模板目录: {tpl_dir}")

    # 用 video 后端把假屏幕"伪装"成帧源，验证内核全链路（无需真实窗口）
    video = tmp / "fake.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    vw = cv2.VideoWriter(str(video), fourcc, 30.0, (1280, 720))
    for _ in range(30):
        vw.write(screen)
    vw.release()

    cfg = {
        "target_fps": 60,
        "capture": ["video"],
        "capture_kwargs": {"path": str(video)},   # video 后端读文件当帧源
        "input": [],                       # 自检不真的操作鼠标键盘
        "templates": str(tpl_dir),
        "plugins": str(ROOT / "plugins"),
        "window": None,
    }
    engine = Engine(cfg, root=ROOT, verbose=True)
    engine.open()

    print("\n[2] 一次性识别测试")
    m = engine.find("ui/start_button", threshold=0.8)
    print("    start_button →", None if m is None else f"命中 {m.rect.as_tuple()} score={m.score:.3f}")
    assert m is not None, "模板匹配应命中"

    m2 = engine.recognize({"type": "color", "rgb": [220, 0, 0], "tol": 20,
                           "point": [1100, 600]}, engine.grab(), engine.ctx)
    print("    color 状态点 →", None if m2 is None else f"命中 score={m2.score}")

    print("\n[3] 流水线测试（识别 → 记录动作 → 跳转）")
    pipe_data = {
        "name": "selftest",
        "start": "wait_button",
        "nodes": [
            {"id": "wait_button", "recognize": {"type": "template", "name": "ui/start_button", "threshold": 0.8},
             "on_found": [{"kind": "click", "params": {"target": "wait_button"}}], "next": "wait_dot"},
            {"id": "wait_dot", "recognize": {"type": "color", "rgb": [220, 0, 0], "tol": 20,
                                             "point": [1100, 600]},
             "on_found": [{"kind": "key", "params": {"key": "space"}}], "next": None},
        ],
    }
    pipe_path = tmp / "selftest.pipeline.json"
    pipe_path.write_text(json.dumps(pipe_data, ensure_ascii=False), encoding="utf-8")

    engine.input = None   # 动作只记录不执行（input 为空时 kernel 会跳过）
    stats = engine.run(pipeline=Pipeline.load(pipe_path), max_steps=5, seconds=10)
    print("    流水线结果:", json.dumps(stats.get("pipeline", {}), ensure_ascii=False))
    print("    运行统计:", {k: stats[k] for k in ("frames", "loop_fps", "grab_ms_avg", "step_ms_avg")})
    assert stats["pipeline"]["finished"], "流水线应跑完"
    assert stats["pipeline"]["hits"].get("wait_button") == 1, "第一个节点应命中一次"

    engine.close()
    print("\n✅ 自检通过（内核、插件、模板匹配、颜色识别、流水线均正常）")


if __name__ == "__main__":
    main()
