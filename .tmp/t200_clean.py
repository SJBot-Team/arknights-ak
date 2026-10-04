# -*- coding: utf-8 -*-
"""回填后的收尾清理 + 记录。"""
import io, os, re, glob

KB = r'C:\Users\23922\Documents\ds_harness\ak\knowledge'
n = 0
for p in glob.glob(os.path.join(KB, '**', '*.md'), recursive=True):
    s = io.open(p, encoding='utf-8').read()
    orig = s
    # ① 来源字段被列表项/多行污染 ⇒ 截断到第一个换行并去掉 "> - " 之类的残留
    s = re.sub(r'(> 层级：[^\n]*?来源：)> - ', r'\1', s)
    s = re.sub(r'(> 层级：[^\n]*?来源：)> ', r'\1', s)
    # ② 来源过长（>70 字）截断
    def trim(m):
        head, src = m.group(1), m.group(2)
        if len(src) > 70:
            src = src[:70].rstrip('　，,;；') + '…'
        return head + src
    s = re.sub(r'(> 层级：[^\n]*?来源：)([^\n]+)', trim, s)
    if s != orig:
        io.open(p, 'w', encoding='utf-8').write(s)
        n += 1
print(f'清理了 {n} 篇')

# ③ 记录到任务卡
p3 = r'C:\Users\23922\Documents\ds_harness\management\大任务\任务单\帧时间对齐与1-1复刻.md'
s3 = io.open(p3, encoding='utf-8').read()
row = ('| 00:3x | KB | **按建议顺序完成"规范头部回填"**：新增永久工具 `ak\\code\\tools\\kb_backfill_header.py`'
       '（**优先取带标签日期 → 头部 6 行裸日期 → 继承母文件标注日期**；**绝不用 mtime**——本轮刚给全库加过主题行，mtime 会误导；'
       '推断值一律标 `｜推断`/`（自动回填）`）。**执行顺序：03（14 篇）→ 04（52 篇）→ 01/02/00/05/07（27 篇）→ 根 1 篇**，'
       '过程中修掉 4 个工具 bug：**BOM 导致 H1 识别失败**、**日期取到正文场次日期**、**索引类被 RVA 计数误判 T1**、**母文件全路径未剥前缀**。'
       '**回填后注册表层级分布：T1×38 / T2×73 / T3×12 / —×7**（回填前 T1×39 / T2×44 / T3×40 / —×7，可见原先 40 篇是"推断"伪 T3） | ✅ |\n')
anchor = '\n---\n\n## 五、待裁决'
assert anchor in s3
s3 = s3.replace(anchor, '\n' + row + anchor, 1)
io.open(p3, 'w', encoding='utf-8').write(s3)
print('任务卡已记录')
