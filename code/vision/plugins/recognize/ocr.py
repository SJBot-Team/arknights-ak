"""OCR 识别器（可选插件）：用 PaddleOCR 读文字并返回词框。

依赖：paddleocr + paddlepaddle（本机 `设计\\media_tools\\.venv` 已装；
若本 venv 未装，`pip install paddleocr paddlepaddle` 即可 —— 属可选插件，缺失不影响内核）。

spec 参数：
    contains   期望包含的文字（缺省则命中任意文字）
    lang       默认 ch
    min_score  置信度下限，默认 0.6
"""
from __future__ import annotations

from kernel.registry import recognizer
from kernel.types import Match, Rect

_MODEL = None
_MODEL_LANG = None


def _get_model(lang: str):
    global _MODEL, _MODEL_LANG
    if _MODEL is None or _MODEL_LANG != lang:
        from paddleocr import PaddleOCR  # 延迟导入：未安装时只影响本识别器
        _MODEL = PaddleOCR(lang=lang)
        _MODEL_LANG = lang
    return _MODEL


@recognizer("ocr")
class OcrRecognizer:
    def run(self, image, spec: dict, ctx, origin, label: str = "", engine=None) -> list[Match]:
        if image is None or image.size == 0:
            return []
        try:
            model = _get_model(spec.get("lang", "ch"))
        except Exception as exc:
            raise RuntimeError(f"OCR 插件不可用（请在本 venv 安装 paddleocr/paddlepaddle）: {exc!r}") from exc

        want = spec.get("contains")
        min_score = float(spec.get("min_score", 0.6))
        out: list[Match] = []
        result = model.predict(image)
        for page in result or []:
            texts = page.get("rec_texts") if isinstance(page, dict) else None
            scores = page.get("rec_scores") if isinstance(page, dict) else None
            boxes = page.get("rec_boxes") if isinstance(page, dict) else None
            if texts is None:
                continue
            for i, text in enumerate(texts):
                score = float(scores[i]) if scores is not None and i < len(scores) else 1.0
                if score < min_score:
                    continue
                if want and want not in text:
                    continue
                box = boxes[i] if boxes is not None and i < len(boxes) else None
                if box is not None:
                    x1, y1, x2, y2 = (int(v) for v in list(box)[:4])
                else:
                    x1, y1, x2, y2 = 0, 0, image.shape[1], image.shape[0]
                rect = Rect(origin[0] + x1, origin[1] + y1, origin[0] + x2, origin[1] + y2)
                out.append(Match(label=label or "ocr", rect=rect, score=score, recognizer="ocr",
                                 extra={"text": text}))
        return out
