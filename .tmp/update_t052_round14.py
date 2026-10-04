# -*- coding: utf-8 -*-
"""T-052 追加：第十四轮（验收对照文档）"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')
P = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
ADD = (
    '**第十四轮（验收对照）**：①新增 `knowledge/04/42_验收对照_模拟与打图.md`——把**原始需求逐条**'
    '（模拟环境 8 项 + 打图 6 项 + 案例互验）与**已实现的证据**对齐，标注状态（✅/🟡/🔴）、'
    '未完成项 A~E 及其前置条件、全量复现命令、合规执行情况；'
    '②结论：模拟环境 8 项中 7 项 ✅（1 项主体达成、残余近似已列明）；打图 6 项中 2.1~2.5 达成'
    '（2.4 PC 端未实测）、**2.6 自动进关未实现**（登录默认禁用）；案例达成**四方一致**'
    '（解析 / 模拟 / 执行端 / 作者记录）；③唯一阻塞项仍为**实机验证**（需用户在场 + 逐次登录同意）；'
    '④`00_目录.md` 与 doc41 头部已加指引（先读 42 看进度）；E 盘镜像已同步。'
)
s = io.open(P, encoding='utf-8').read()
tail = ' | 2026-09-14 |'
idx = s.find('| T-052 ')
end = s.find('\n', idx)
row = s[idx:end]
assert row.rstrip().endswith(tail.strip())
assert '第十四轮（验收对照）' not in row
row2 = row.rstrip()[:-len(tail.strip())].rstrip() + ' ' + ADD + tail
s = s[:idx] + row2 + s[end:]
io.open(P, 'w', encoding='utf-8').write(s)
print('已更新 T-052，长度', len(row), '→', len(row2))
