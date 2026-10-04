# -*- coding: utf-8 -*-
"""add_trait_scale.py — ★实现"职业特性（trait）的 atk_scale"（远程攻击 ×0.8）

## 依据（1-1 标定反推）
月见夜（WARRIOR / **lord** 远程近卫）的 `trait = {blackboard:[{key:"atk_scale", value:0.8}]}`
⇒ 语义：**远程攻击时攻击力 ×0.8**（近战目标按全额）。

**因果验证**：
- 实机：**432 芬(325) + 438 月见夜(569×0.8=455) = 780 < 820 ⇒ 不致死**，
  接着 **464 芬再打 325 ⇒ 1105 > 820 ⇒ 击杀** ✅ 与标定完全吻合；
- 本方缺该特性 ⇒ 325+569=894>820 ⇒ **439 即死** ❌。

## 实现
在 `_do_attack` 计算 `scale_v` 时，追加**特性缩放**：
- 从干员数据的 `trait` 里取 `blackboard` 的 `atk_scale`（需已并入 spec——见下方"注意"）；
- **仅当"该次攻击属于远程"时应用**：判据 = **目标与本单位的距离 > TRAIT_RANGED_DIST**（默认 1.0）；
- 可用 `options={'trait_scale': False}` 关闭。

**注意**：若 `spec` 里没有 `trait` 字段，则本补丁会顺带从 `character_table` 现取一次。
"""
from __future__ import annotations

import io
import sys

sys.stdout.reconfigure(encoding='utf-8')

ENGINE = r'C:\Users\23922\Documents\ds_harness\ak\sim\draft\ak_sim\engine.py'

ANCHOR = """        scale_v = 1.0
        extra_targets = 0"""

NEW = """        scale_v = 1.0
        # ★职业特性（trait）的 atk_scale：如月见夜（lord 远程近卫）远程攻击 ×0.8。
        #   依 1-1 标定反推：实机"432 芬325 + 438 月见夜455(=569×0.8) = 780 < 820 ⇒ 不致死"，
        #   接着"464 芬再打 325 ⇒ 击杀" ⇒ 与标定完全吻合；若缺该特性则会 439 即死。
        if getattr(self, 'trait_scale', True):
            ts = self._trait_atk_scale(src, tgt)
            if ts is not None and ts != 1.0:
                scale_v *= float(ts)
        extra_targets = 0"""

HELPER = '''
    # ---------------- ★职业特性（trait）atk_scale ----------------
    TRAIT_RANGED_DIST = 1.0     # 目标距离 > 该值 视为"远程攻击"（≥1 格）

    def _trait_atk_scale(self, src: Unit, tgt: Unit):
        """取"职业特性"里的 `atk_scale`；仅当本次攻击为"远程"时生效。

        - 数据来源：干员 spec 的 `trait`（`blackboard` 中的 `atk_scale`），
          若 spec 未带 `trait`，则回退到 `character_table.json` 现取一次并缓存；
        - **判据**：`src.dist_to(tgt) > TRAIT_RANGED_DIST`（远程）⇒ 应用缩放；否则返还 1.0。
        """
        key = getattr(src, 'key', None)
        if not key or not getattr(src, 'is_operator', False):
            return None
        cache = getattr(self, '_trait_scale_cache', None)
        if cache is None:
            cache = {}
            self._trait_scale_cache = cache
        if key not in cache:
            val = None
            try:
                from . import data as _D
                ct = _D.load_table('character_table.json')
                c = ct.get(key) or {}
                for cand in ((c.get('trait') or {}).get('candidates') or []):
                    for bb in (cand.get('blackboard') or []):
                        if bb.get('key') == 'atk_scale' and bb.get('value') is not None:
                            val = float(bb['value'])
                            break
                    if val is not None:
                        break
            except Exception:
                val = None
            cache[key] = val
        val = cache.get(key)
        if val is None:
            return None
        try:
            d = src.dist_to(tgt)
        except Exception:
            return None
        return val if d > self.TRAIT_RANGED_DIST else 1.0
'''


def main():
    s = io.open(ENGINE, encoding='utf-8').read()
    n = 0
    if '★职业特性（trait）的 atk_scale' not in s:
        if ANCHOR in s:
            s = s.replace(ANCHOR, NEW, 1)
            n += 1
        else:
            print('★锚点未匹配')
    else:
        print('已有 trait_scale 逻辑')
    if 'def _trait_atk_scale' not in s:
        idx = s.find('    def _do_attack(self, src: Unit, tgt: Unit) -> None:')
        if idx > 0:
            s = s[:idx] + HELPER + '\n' + s[idx:]
            n += 1
        else:
            print('★helper 插入点未找到')
    if 'self.trait_scale' not in s:
        s = s.replace("        self.block_snap = bool(opts.get('block_snap', True))",
                      "        self.block_snap = bool(opts.get('block_snap', True))\n"
                      "        # ★职业特性(trait) atk_scale（如月见夜远程 ×0.8）\n"
                      "        self.trait_scale = bool(opts.get('trait_scale', True))", 1)
        n += 1
    io.open(ENGINE, 'w', encoding='utf-8', newline='').write(s)
    print(f'已修改 {n} 处')
    import ast
    ast.parse(io.open(ENGINE, encoding='utf-8').read())
    print('语法 OK')


if __name__ == '__main__':
    main()
