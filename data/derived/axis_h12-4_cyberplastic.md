# 轴表 H12-4（timebase=cost, seed=0）

| # | 费用 | 费用内帧 | 操作 | 单位 | 坐标 | 朝向 | 备注 |
|---|---|---|---|---|---|---|---|
| 1 | 11 | 15 | deploy | 令 | C12 | 上 |  |
| 2 | 20 | 0 | deploy | 蕾缪安 | G9 | 下 |  |
| 3 |  | 4 | skill | 蕾缪安 |  |  |  |
| 4 |  | 5 | skill | 蕾缪安 |  |  |  |
| 5 |  | 23 | skill | 令 |  |  |  |
| 6 |  | 0 | deploy | 弦惊 | D11 | 左 |  |
| 7 |  | 5 | deploy | 弦惊 | G8 | 上 |  |
| 8 |  | 5 | skill | 蕾缪安 |  |  |  |
| 9 |  | 3 | skill | 蕾缪安 |  |  |  |
| 10 |  | 0 | deploy | 弦惊 | G11 | 下 |  |
| 11 |  | 13 | skill | 蕾缪安 |  |  |  |
| 12 |  | 27 | skill | 令 |  |  |  |
| 13 |  | 8 | retreat | 蕾缪安 |  |  |  |
| 14 |  | 15 | deploy | 弦惊 | F8 | 上 |  |
| 15 |  | 0 | deploy | 麒麟R夜刀 | G12 | 上 |  |
| 16 |  | 5 | retreat | 麒麟R夜刀 |  |  |  |
| 17 | 29 | 20 | deploy | 弦惊 | H4 | 右 |  |
| 18 | 27 | 15 | skill | 令 |  |  |  |
| 19 | 29 | 0 | deploy | U-Official | B8 | 左 |  |
| 20 |  | 22 | retreat | U-Official |  |  |  |
| 21 |  | 0 | deploy | 蕾缪安 | E5 | 左 |  |
| 22 |  | 0 | retreat | 弦惊 | G11 |  |  |
| 23 | 18 | 0 | deploy | 弦惊 | C4 | 上 |  |
| 24 |  | 12 | skill | 蕾缪安 |  |  |  |
| 25 |  | 14 | skill | 蕾缪安 |  |  |  |
| 26 |  | 21 | deploy | 弦惊 | D4 | 右 |  |
| 27 |  | 22 | skill | 蕾缪安 |  |  |  |
| 28 |  | 14 | skill | 蕾缪安 |  |  |  |
| 29 |  | 8 | skill | 令 |  |  |  |
| 30 |  | 0 | deploy | 傀影 | G12 | 上 |  |
| 31 |  | 5 | retreat | 傀影 |  |  |  |
| 32 | 29 | 0 | deploy | 弦惊 | D5 | 左 |  |
| 33 |  | 0 | deploy | 艾拉 | G12 | 上 |  |
| 34 |  | 0 | deploy | 雷鸣地雷 | F10 | 无 |  |
| 35 |  | 0 | deploy | 雷鸣地雷 | F11 | 无 |  |
| 36 |  | 0 | deploy | 雷鸣地雷 | F12 | 无 |  |
| 37 |  | 0 | skill | 艾拉 |  |  |  |
| 38 |  | 0 | skill | 艾拉 |  |  |  |
| 39 |  | 0 | retreat | 艾拉 |  |  |  |
| 40 |  | 15 | skill | 蕾缪安 |  |  |  |
| 41 | 32 | 18 | deploy | 弦惊 | D4 | 左 |  |
| 42 |  | 0 | skill | 令 |  |  |  |
| 43 |  | 26 | deploy | 弦惊 | C4 | 上 |  |
| 44 |  | 20 | skill | 蕾缪安 |  |  |  |
| 45 |  | 6 | retreat | 弦惊 | D4 |  |  |
| 46 |  | 25 | deploy | 弦惊 | H5 | 右 |  |
| 47 |  | 27 | skill | 蕾缪安 |  |  |  |
| 48 |  | 29 | deploy | 弦惊 | G11 | 下 |  |
| 49 |  | 3 | skill | 令 |  |  |  |
| 50 |  | 15 | skill | 蕾缪安 |  |  |  |

> 模拟校验：{'matched_ops': 0, 'max_frame_diff': 0, 'sim_result': 'WIN', 'sim_frames': 12000}
- op1 模拟帧=45 参考帧=None OK deploy char_2023_ling
- op2 模拟帧=601 参考帧=None OK deploy char_4193_lemuen
- op3 模拟帧=605 参考帧=None FAIL skill char_4193_lemuen
- op4 模拟帧=610 参考帧=None FAIL skill char_4193_lemuen
- op5 模拟帧=633 参考帧=None FAIL skill char_2023_ling
- op6 模拟帧=633 参考帧=None FAIL deploy token_10020_ling_soul3
- op7 模拟帧=638 参考帧=None FAIL deploy token_10020_ling_soul3
- op8 模拟帧=643 参考帧=None FAIL skill char_4193_lemuen
- op9 模拟帧=643 参考帧=None FAIL skill char_4193_lemuen
- op10 模拟帧=643 参考帧=None FAIL deploy token_10020_ling_soul3
- op11 模拟帧=656 参考帧=None FAIL skill char_4193_lemuen
- op12 模拟帧=683 参考帧=None FAIL skill char_2023_ling
- op13 模拟帧=691 参考帧=None OK retreat char_4193_lemuen
- op14 模拟帧=706 参考帧=None FAIL deploy token_10020_ling_soul3
- op15 模拟帧=706 参考帧=None OK deploy char_1029_yato2
- op16 模拟帧=711 参考帧=None OK retreat char_1029_yato2
- op17 模拟帧=2180 参考帧=None OK deploy token_10020_ling_soul3
- op18 模拟帧=2655 参考帧=None OK skill char_2023_ling
- op19 模拟帧=2701 参考帧=None OK deploy char_4091_ulika
- op20 模拟帧=2723 参考帧=None OK retreat char_4091_ulika
- op21 模拟帧=2723 参考帧=None OK deploy char_4193_lemuen
- op22 模拟帧=2723 参考帧=None FAIL retreat token_10020_ling_soul3
- op23 模拟帧=3031 参考帧=None FAIL deploy token_10020_ling_soul3
- op24 模拟帧=3043 参考帧=None FAIL skill char_4193_lemuen
- op25 模拟帧=3057 参考帧=None FAIL skill char_4193_lemuen
- op26 模拟帧=3078 参考帧=None FAIL deploy token_10020_ling_soul3
- op27 模拟帧=3100 参考帧=None FAIL skill char_4193_lemuen
- op28 模拟帧=3114 参考帧=None FAIL skill char_4193_lemuen
- op29 模拟帧=3122 参考帧=None FAIL skill char_2023_ling
- op30 模拟帧=3122 参考帧=None FAIL deploy char_250_phatom
- op31 模拟帧=3127 参考帧=None FAIL retreat char_250_phatom
- op32 模拟帧=3361 参考帧=None FAIL deploy token_10020_ling_soul3
- op33 模拟帧=3361 参考帧=None FAIL deploy char_4123_ela
- op34 模拟帧=3361 参考帧=None FAIL deploy token_10033_ela_grzmot
- op35 模拟帧=3361 参考帧=None FAIL deploy token_10033_ela_grzmot
- op36 模拟帧=3361 参考帧=None FAIL deploy token_10033_ela_grzmot
- op37 模拟帧=3361 参考帧=None FAIL skill char_4123_ela
- op38 模拟帧=3361 参考帧=None FAIL skill char_4123_ela
- op39 模拟帧=3361 参考帧=None FAIL retreat char_4123_ela
- op40 模拟帧=3376 参考帧=None OK skill char_4193_lemuen
- op41 模拟帧=3468 参考帧=None OK deploy token_10020_ling_soul3
- op42 模拟帧=3468 参考帧=None FAIL skill char_2023_ling
- op43 模拟帧=3494 参考帧=None FAIL deploy token_10020_ling_soul3
- op44 模拟帧=3514 参考帧=None FAIL skill char_4193_lemuen
- op45 模拟帧=3514 参考帧=None OK retreat token_10020_ling_soul3
- op46 模拟帧=3539 参考帧=None OK deploy token_10020_ling_soul3
- op47 模拟帧=3566 参考帧=None FAIL skill char_4193_lemuen
- op48 模拟帧=3595 参考帧=None FAIL deploy token_10020_ling_soul3
- op49 模拟帧=3595 参考帧=None FAIL skill char_2023_ling
- op50 模拟帧=3610 参考帧=None FAIL skill char_4193_lemuen