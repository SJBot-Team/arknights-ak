# -*- coding: utf-8 -*-
"""maa_task.py — **按 MAA 的任务定义**做界面识别（来源：MAA `resource/tasks/tasks.json`）

## 依用户 2026-09-15 要求
> 关卡外严格对照 MAA 现有实现的识别方式，目前阶段不要自行发明方案。

⇒ 本模块**不发明识别方式**，而是**直接读 MAA 的 tasks.json**，按其中的
`template` / `roi` / `algorithm` / `text` 等字段判定"当前画面命中了哪些 MAA 任务"，
并给出对应 1920×1080 的坐标（MAA 是 1280×720 基准 ⇒ ×1.5）。

## 已支持的识别类型
| MAA 字段 | 本模块处理 |
|---|---|
| `template: "Xxx.png"` | MAA 模板匹配（ROI 内，阈值可配）；支持 `SwitchTheme@X.png` 这类主题前缀 |
| `algorithm: "JustReturn"` | 恒真（流程占位） |
| `algorithm: "OcrDetect"` | **待接入 OCR 引擎**（返回 `unsupported`，不猜） |
| `algorithm: "RGBCount"` / `colorScales` | **待接入**（返回 `unsupported`） |

## 用法
    mt = MaaTask()
    hits = mt.evaluate(frame, ['StartUp', 'AccountManager', 'BattleStartPre'])
    for name, r in hits.items(): print(name, r)
"""
from __future__ import annotations

import json
import os
import sys

import cv2

if __package__ in (None, ''):        # 允许 `python plugins/recognize/maa_task.py` 直接跑
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from plugins.recognize.maa_anchor import BASE_W, MAA_ROOT

TASKS_JSON = os.path.join(MAA_ROOT, 'tasks', 'tasks.json')
# MAA 模板里有些写法带主题前缀（如 SwitchTheme@ToggleSettingsMenu.png），
# 实际文件在 template/ 下的具体目录；这里给出常见映射与回退搜索。
TEMPLATE_SEARCH_DIRS = ('UiTheme', 'Battle', 'StageNavigation', 'ReturnButton', 'WakeUp',
                        'OperBox', 'Recruit', 'Depot', 'Award', '')


class MaaTask:
    def __init__(self, tasks_json: str = TASKS_JSON, thr: float = 0.8):
        self.tasks = json.load(open(tasks_json, encoding='utf-8'))
        self.thr = thr
        self._tpl_cache: dict[str, object] = {}
        # 递归索引 template/ 下全部 png：basename → [路径,...]（MAA 的模板可直接用文件名引用）
        self._tpl_index: dict[str, list] = {}
        root = os.path.join(MAA_ROOT, 'template')
        for dp, _dn, fns in os.walk(root):
            for f in fns:
                if f.lower().endswith('.png'):
                    self._tpl_index.setdefault(f, []).append(os.path.join(dp, f))
                # MAA 里的 "00@EnterEpisodeNew.png" 形式，其 basename 含 @，原样入索引
        self._tpl_index.setdefault('empty.png', [])
        # empty.png 是 MAA 的"空模板"约定（表示不做图像匹配）
        if not self._tpl_index['empty.png']:
            self._tpl_index['empty.png'] = [os.path.join(root, 'empty.png')]

    # ---------- 模板定位（递归索引 + 主题前缀回退） ----------
    def _find_template_file(self, name):
        if name in self._tpl_cache:
            return self._tpl_cache[name]
        img = None
        cand = []
        # MAA 里 template 可以是 "Default/Terminal.png" 这类**带相对路径**的写法：
        # 先按 template/ 下的相对路径直查，再退回按 basename 索引。
        if '/' in name or '\\' in name:
            cand.append(os.path.join(MAA_ROOT, 'template', name.replace('/', os.sep)))
        cand += list(self._tpl_index.get(os.path.basename(name), []))
        if not cand and '@' in name:           # SwitchTheme@ToggleSettingsMenu.png
            theme, base = name.split('@', 1)
            cand = list(self._tpl_index.get(base, [])) + list(self._tpl_index.get(name, []))
        for p in cand:
            if os.path.exists(p):
                img = cv2.imread(p, cv2.IMREAD_COLOR)
                if img is not None:
                    break
        self._tpl_cache[name] = img
        return img

    # ---------- OCR（照 MAA 的 OcrDetect 语义：裁 roi → 识别 → 与 text 列表比对） ----------
    TESSERACT = r'D:\__soft\ak\prts+\_internal\Tesseract-OCR\tesseract.exe'
    TESSDATA = r'D:\__soft\ak\prts+\_internal\Tesseract-OCR\tessdata'

    def ocr_roi(self, frame, roi, lang: str = 'chi_sim+eng', psm: int = 6) -> str:
        """裁剪 MAA 的 roi（1280×720 基准）→ 放大回原始尺度 → tesseract 识别。

        psm 6 = 假设为单个统一文本块（MAA 的按钮文字多为单行短语）。
        """
        import subprocess
        import tempfile
        fh, fw = frame.shape[:2]
        scale = fw / float(BASE_W)
        x, y, w, h = [int(v) for v in roi]
        x0, y0 = int(x * scale), int(y * scale)
        x1, y1 = int((x + w) * scale), int((y + h) * scale)
        crop = frame[max(0, y0):y1, max(0, x0):x1]
        if crop.size == 0:
            return ''
        # 放大 2× 提升小字识别率（MAA 也做预处理）
        crop = cv2.resize(crop, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            tmp = f.name
        cv2.imwrite(tmp, crop)
        try:
            p = subprocess.run([self.TESSERACT, tmp, 'stdout', '-l', lang,
                                '--tessdata-dir', self.TESSDATA, '--psm', str(psm)],
                               capture_output=True, encoding='utf-8', errors='replace', timeout=25)
            return ' '.join((p.stdout or '').split())
        except Exception:
            return ''
        finally:
            try:
                os.remove(tmp)
            except Exception:
                pass

    # ---------- 单个任务判定 ----------
    def evaluate_one(self, frame, task_name: str) -> dict:
        t = self.tasks.get(task_name)
        if t is None:
            return {'status': 'missing_task'}
        algo = t.get('algorithm')
        if algo == 'JustReturn':
            return {'status': 'always', 'task': task_name}
        if algo == 'OcrDetect':
            # ★ 照 MAA 的 OcrDetect：裁 roi → OCR → 与 text 列表比对（fullMatch 时要求整段相等）
            roi = t.get('roi')
            if not roi:
                return {'status': 'ocr_no_roi', 'task': task_name}
            text = self.ocr_roi(frame, roi, lang=t.get('lang', 'chi_sim+eng'))
            want = t.get('text') or []
            if isinstance(want, str):
                want = [want]
            full = bool(t.get('fullMatch'))
            hit = False
            for w in want:
                w2 = str(w)
                if (text == w2) if full else (w2 in text):
                    hit = True
                    break
            # text 为空：MAA 的语义是"**由外部传入目标文本**"（如关卡名），
            # 本模块不猜，标为 needs_target 而不是无条件命中。
            if not want:
                return {'status': 'needs_target', 'task': task_name,
                        'ocr_text': text, 'want': [], 'fullMatch': full, 'roi': roi,
                        'note': 'MAA 此任务 text 为空，需由调用方给出目标文本（如关卡名）'}
            return {'status': 'hit' if hit else 'miss', 'task': task_name,
                    'ocr_text': text, 'want': want, 'fullMatch': full, 'roi': roi}
        if algo:
            return {'status': 'unsupported', 'algorithm': algo,
                    'note': '待接入（颜色计数等），不猜结果'}
        tpl_name = t.get('template')
        if tpl_name is None:
            # ★ MAA 约定：任务没写 template 时，**默认用任务名当模板名**
            #   （例：'00@EnterEpisodeNew' ⇒ StageNavigation/Episode/00@EnterEpisodeNew.png）
            tpl_name = task_name.split('@')[-1] if '@' in task_name else task_name
            tpl_name = f'{tpl_name}.png'
        names = tpl_name if isinstance(tpl_name, list) else [tpl_name]
        # empty.png = MAA 的"空模板"约定（表示不做图像匹配、只做动作）
        if any(str(n).endswith('empty.png') for n in names):
            return {'status': 'no_match_needed', 'task': task_name, 'template': names}
        tpl = None
        used = None
        for n in names:
            tpl = self._find_template_file(n)
            if tpl is not None:
                used = n
                break
        if tpl is None:
            return {'status': 'template_not_found', 'template': names}
        roi = t.get('roi')
        fh, fw = frame.shape[:2]
        scale = fw / float(BASE_W)
        small = cv2.resize(frame, (BASE_W, int(round(BASE_W * fh / fw))),
                           interpolation=cv2.INTER_AREA)
        if roi:
            x, y, w, h = [int(v) for v in roi]
            area = small[max(0, y):y + h, max(0, x):x + w]
            off = (max(0, x), max(0, y))
        else:
            area, off = small, (0, 0)
        if area.size == 0 or area.shape[0] < tpl.shape[0] or area.shape[1] < tpl.shape[1]:
            return {'status': 'roi_too_small', 'task': task_name}
        res = cv2.matchTemplate(area, tpl, cv2.TM_CCOEFF_NORMED)
        _, maxv, _, maxloc = cv2.minMaxLoc(res)
        _tt = t.get('templThreshold', self.thr)
        if isinstance(_tt, list):
            _tt = _tt[0] if _tt else self.thr      # MAA 允许与 template 数组对齐的阈值数组
        thr = float(_tt)
        cx = off[0] + maxloc[0] + tpl.shape[1] / 2
        cy = off[1] + maxloc[1] + tpl.shape[0] / 2
        return {'status': 'hit' if maxv >= thr else 'miss', 'task': task_name,
                'score': float(maxv), 'thr': thr, 'template': used,
                'center_base': (cx, cy),
                'center_frame': (round(cx * scale), round(cy * scale))}

    # ---------- 批量判定 ----------
    def evaluate(self, frame, names) -> dict:
        return {n: self.evaluate_one(frame, n) for n in names}

    def scan_all(self, frame, only_template=True, topn: int = 15) -> list:
        """扫**全部任务**里带 template 的（不发明，只用 MAA 自己的定义），按分数排序。"""
        out = []
        for name, t in self.tasks.items():
            if only_template and not t.get('template'):
                continue
            r = self.evaluate_one(frame, name)
            if r.get('status') == 'hit':
                out.append((r['score'], name, r.get('center_frame')))
        out.sort(reverse=True)
        return out[:topn]


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    path = sys.argv[1] if len(sys.argv) > 1 else None
    if path:
        frame = cv2.imread(path)
    else:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))))
        from plugins.capture.emu_window import make_capture
        frame = make_capture('adb').grab().image
    mt = MaaTask()
    print('=== 按 MAA tasks.json 判定几个关键任务 ===')
    for name in ('StartUp', 'Fight', 'AccountManager', 'BattleStartPre', 'LoadingIcon',
                 'OfflineConfirm', 'CloseHomeSanity'):
        r = mt.evaluate_one(frame, name)
        print(f'  {name:<20} {r.get("status"):<18} '
              f'{("score=" + format(r["score"], ".3f")) if "score" in r else ""} '
              f'{("@" + str(r["center_frame"])) if "center_frame" in r else ""}')
    print('\n=== 全任务扫描（命中的 MAA 任务）===')
    for s, n, c in mt.scan_all(frame):
        print(f'  {s:.3f}  {n:<40} {c}')
