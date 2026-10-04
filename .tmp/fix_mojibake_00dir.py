# -*- coding: utf-8 -*-
r"""fix_mojibake_00dir.py — 修复被写成"UTF-8 文本按 GBK 再编码"的 md 文件

症状：`knowledge\04_数据对应与核验\00_目录.md` 里出现 `鎴戣鍋氱殑浜?` 这类乱码，
导致 `check_kb_links.py` 报 6 条断链（引用的 `00_目录.md`/`01_结论索引.md` 等文件名也一起乱码）。

原理：原始 UTF-8 字节被按 **GBK(cp936)** 解码成字符串，再以 UTF-8 存盘。
⇒ 逆向：把当前文本 `.encode('gbk')` 还原字节，再 `.decode('utf-8')`。

逐行处理：能成功往返的行才替换，否则保留原样（避免误伤本来就正常的行）。
"""
from __future__ import annotations

import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

TARGET = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\00_目录.md'
BACKUP_DIR = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'


def try_fix(s: str) -> str | None:
    try:
        raw = s.encode('gbk')
    except UnicodeEncodeError:
        return None
    try:
        return raw.decode('utf-8')
    except UnicodeDecodeError:
        return None


def main() -> int:
    raw_bytes = open(TARGET, 'rb').read()
    text = raw_bytes.decode('utf-8')
    lines = text.split('\n')
    out, fixed_n, kept_n = [], 0, 0
    for ln in lines:
        f = try_fix(ln)
        # 只有"修完以后更像正常中文"的行才采用
        if f is not None and f != ln:
            out.append(f)
            fixed_n += 1
        else:
            out.append(ln)
            kept_n += 1
    new_text = '\n'.join(out)

    os.makedirs(BACKUP_DIR, exist_ok=True)
    bak = os.path.join(BACKUP_DIR, '00_目录.md.mojibake-bak')
    shutil.copy2(TARGET, bak)

    open(TARGET, 'w', encoding='utf-8', newline='').write(new_text)
    print(f'修复行 {fixed_n} / 保留行 {kept_n}；备份 → {bak}')
    print('--- 修复后前 12 行 ---')
    for i, ln in enumerate(new_text.split('\n')[:12], 1):
        print(f'{i:>3}| {ln[:110]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
