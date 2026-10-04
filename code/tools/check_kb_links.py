# -*- coding: utf-8 -*-
"""知识库内部链接检查器（T-062「持续更新机制」的配套工具）。

做一件事：把 .md 里**反引号包起来的、以 .md 结尾的字符串**当作内部引用，检查目标是否存在。
（只检查"具体路径/文件名"，模式串如 `*_*.md`、`<名>.md` 一律跳过。）

解析顺序（命中即算存在）：
  1. 相对 `ak/`（如 `knowledge/04/41_….md`、`meta/流程规范.md`、`code/…`）
  2. 相对 `ak/knowledge/`（如 `04/41_….md`、`01_基础数据/01a_….md`）
  3. 相对工作区根（`management/…`）
  4. 不含 `/` 时：按**文件名**在 `ak/` 与 `management/` 全树中查（同名多处也算命中）

用法：
  python check_kb_links.py          # 只列出有断链的文件
  python check_kb_links.py -v       # 附统计
"""
import os
import re
import sys

WS = r'C:\Users\23922\Documents\ds_harness'
AK = os.path.join(WS, 'ak')
KB = os.path.join(AK, 'knowledge')
SKIP_DIRS = {'.venv', '__pycache__', 'node_modules', '.git', '_runs', '_runtime', '.tmp'}
SKIP_TREES = {os.path.join('code', 'unpack'), os.path.join('code', 'external')}  # 第三方 vendored 代码树

CODE_SPAN = re.compile(r'`([^`\n]+)`')
SKIP_MARK = ('*', '<', '>', '…', '\\', ' ', '|', 'NN', '{', '（')

# 已知"引用但当前不存在"的合法条目（计划中 / 临时 / 库外），由人工维护：
#   计划中 = 已在本库登记为待建文件；临时 = 已清理的 .tmp 产物；库外 = 位于 E: 或第三方仓库，不在 ak\ 内
KNOWN_ABSENT = {
    '搭建经验.md',                      # 计划中：meta 侧占位（模拟环境搭建总结）
    '.tmp/stage_survey.md',            # 临时：出怪普查脚本产物，已清理
    'ArkDPS代码逻辑解析.md',             # 库外：E: 设计\…\技能搜索与合并优化\ 下的社区解析
    'docs/API.md',                     # 库外：第三方项目文档
    'doc/how_to_use_console.md',       # 库外：OpenBachelorS 仓库内文档
    '来源.md',                          # 见 ak\data\README.md（待补或改名）
    '00_结论索引.md',                    # 历史名：已改名为 01_结论索引.md，正文中的说明性提及
}


def walk_md(root, skip_trees=()):
    out = []
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        rel = os.path.relpath(base, root)
        if any(rel == t or rel.startswith(t + os.sep) for t in skip_trees):
            dirs[:] = []
            continue
        for f in files:
            if f.endswith('.md'):
                out.append(os.path.join(base, f))
    return out


def domain_map():
    """`04/xx.md` 这类引用里的两位编号 → 真实领域目录名（如 `04_数据对应与核验`）。"""
    m = {}
    for name in os.listdir(KB):
        p = os.path.join(KB, name)
        if os.path.isdir(p) and len(name) > 2 and name[:2].isdigit() and name[2] == '_':
            m[name[:2]] = name
    return m


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    verbose = '-v' in sys.argv

    ak_files = walk_md(AK, SKIP_TREES)                 # 待扫描的"自家"文档
    all_files = walk_md(AK) + walk_md(os.path.join(WS, 'management'))  # 存在性索引（含第三方树）
    mg_files = [p for p in all_files if os.path.normcase(p).startswith(os.path.normcase(os.path.join(WS, 'management')))]
    by_name = {}
    for p in all_files:
        by_name.setdefault(os.path.basename(p), []).append(p)
    ak_set = set(os.path.normcase(os.path.abspath(p)) for p in all_files)
    dom = domain_map()

    def exists(p):
        return os.path.normcase(os.path.abspath(p)) in ak_set

    def resolve(ref, src):
        ref = ref.strip()
        if not ref.endswith('.md') or ref == '.md':
            return True
        if any(m in ref for m in SKIP_MARK):
            return True
        if ref in KNOWN_ABSENT or os.path.basename(ref) in KNOWN_ABSENT:
            return True
        # 相对源文件所在目录（如 sim/README.md 里的 `draft/ak_sim/README.md`）
        cands = [os.path.join(os.path.dirname(src), ref)]
        cands += [os.path.join(AK, ref), os.path.join(KB, ref), os.path.join(WS, ref)]
        # `04/xx.md` → `knowledge/04_数据对应与核验/xx.md`
        head, _, tail = ref.partition('/')
        if tail and head in dom:
            cands.append(os.path.join(KB, dom[head], tail))
        # `knowledge/04/xx.md` → `knowledge/04_数据对应与核验/xx.md`
        parts = ref.split('/')
        if len(parts) >= 3 and parts[0] == 'knowledge' and parts[1] in dom:
            cands.append(os.path.join(KB, dom[parts[1]], *parts[2:]))
        if '/' not in ref and ref in by_name:
            return True
        return any(exists(c) for c in cands)

    total = bad = 0
    hit_files = []
    for src in sorted(ak_files):
        text = open(src, encoding='utf-8-sig', errors='replace').read()
        misses = []
        for m in CODE_SPAN.finditer(text):
            ref = m.group(1).strip()
            if not ref.endswith('.md') or any(k in ref for k in SKIP_MARK):
                continue
            total += 1
            if not resolve(ref, src):
                misses.append(ref)
        if misses:
            bad += len(misses)
            hit_files.append((src, list(dict.fromkeys(misses))))

    for src, misses in hit_files:
        print('✗ ' + os.path.relpath(src, WS))
        for r in misses:
            print('    → 未找到: ' + r)
    print(f'\n检查 {len(ak_files)} 个 md 文件，内部 .md 引用 {total} 条，**断链 {bad} 条**（分布在 {len(hit_files)} 个文件）')
    if verbose:
        print(f'可用基线：ak/ 下 md {len(ak_files)} 个，management/ 下 {len(mg_files)} 个，唯一文件名 {len(by_name)} 个')


if __name__ == '__main__':
    main()
