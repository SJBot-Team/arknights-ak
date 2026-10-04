# 79 prts+ 卡位识别：**反汇编复原 + 实机验证**（用户裁决②）
> 主题：**04E 实机 / 打图操作**（本域按主题的虚拟分组，索引见 `04/00_目录.md §三之二`；文件路径未变）

> 层级：**T1-逆向（prts+ 字节码）+ T1-实测（1-1 演习）**　建立日期：2026-09-29　任务：**T-200c**
> 依据：`ak\.tmp\t200g_39_la.txt`（T-200g 从 prts+ 冻结包反汇编出的 `locate_avatar` 字节码）
> 脚本：`ak\.tmp\t200_prts_cardid2.py`（忠实复刻）；实机：1-1 演习、10 张卡（芬已部署）

---

## §1 ★反汇编复原出的 `locate_avatar`（逐句对应字节码）

```python
def locate_avatar(action):
    """Locate the exact location of the avatar on game screen. Modify the action object in place."""
    avatars       = get_avatars(action.oper)                    # 该干员的全部头像变体
    oper_area_img = capture_game_window(ratioconfig.OPERATOR_AREA_RATIO)   # 截图→标准尺度→裁下方 20%
    max_val, max_pos, max_avatar = 0, (0, 0), None
    for avatar in avatars:
        matched = cv2.matchTemplate(oper_area_img, avatar, cv2.TM_CCOEFF_NORMED)
        _, val, _, pos = cv2.minMaxLoc(matched)
        if val > max_val:
            max_val, max_pos, max_avatar = val, pos, avatar
    if max_val < imgconfig.TEMPLATE_MATCH_THRESHOLD:            # 0.8
        logger.error(ErrorToLog('Could not find a good matching avatar for ' + ... + '未在待部署区找到干员' ...))
    else:
        oper_area_img = replace_avatar(oper_area_img, max_pos, max_avatar)   # ★抹掉已命中的头像
        avatar_ratio_x = OPERATOR_AREA_RATIO[0] + (max_pos[0] + max_avatar.shape[1] / 2) / SCREEN_STANDARD_SIZE[0]
        avatar_ratio_y = OPERATOR_AREA_RATIO[1] + (max_pos[1] + max_avatar.shape[0] / 2) / SCREEN_STANDARD_SIZE[1]
        action.avatar_pos = (avatar_ratio_x, avatar_ratio_y)    # ★存的是"屏幕比例"，不是像素
        logger.info('Found best matching avatar for ' + ... + 'Avatar position of ' + ... + ' found at: ' ...)
```
**要点**（此前猜错的地方）：
1. 整条链在 **`SCREEN_STANDARD_SIZE = (1280, 720)` 标准尺度**上做——截图先缩到 1280×720；
   待部署区 = 该尺度下的 `(0, 576)-(1280, 720)`（即 `OPERATOR_AREA_RATIO=(0,0.8,1,1)`）。
2. **`replace_avatar`**：命中一个头像后就把它**从待部署区抹掉**，避免下一个干员重复命中同一张卡。
3. `avatar_pos` 输出的是**屏幕比例**（`区域原点比例 + 中心偏移/标准尺寸`），不是像素。

## §2 实机验证结果（1-1、10 张卡、1280×720 标准尺度）

**位置识别 —— ✅ 稳定可用**：10 个干员各自命中**互不重复**的槽位，
间距均匀（x ≈ 229/406/585/763/940/1119/1297/1474/1653/1830，pitch ≈ 177px），
且**已部署的芬只拿到 0.368 被正确排除**（不在待部署区）。

**名字识别 —— 🟡 需按"脸部裁切"调，且真值要用游戏面板**：

| 模板裁切 | 单目标落对真值槽 | 典型 NCC |
|---|---|---|
| 全头像 /120 | 0/10（模板大于区域，被跳过） | — |
| 全头像 /多尺度(100/113/126) | 5/10 | 0.43~0.57 |
| 头肩(0.10~0.72) /多尺度 | 5/10 | 0.51~0.67 |
| **脸(0.15~0.60) /多尺度(70/80/90)** | **5/10** | **0.70~0.86** ← 最高 |

⇒ **脸部裁切 + 多尺度** 的 NCC 明显最高（香草 0.84、斑点 0.84、卡缇 0.86、月见夜 0.70），
**最接近 prts+ 的 0.8 阈值**，方向正确。

⚠️ **但"命中 5/10"这个数字目前不可信**：真值是我**目视判读**的，而 3 星干员（卡缇/香草/克罗斯/泡普卡）
长相相近、卡片下缘还被裁掉，我自己的判读就存在不确定（例如"戴风镜的淡紫发"我判为克洛丝，
而匹配器以 0.86 判为卡缇）。

---

## §3 结论与下一步

1. **prts+ 的做法可以直接用**：`matchTemplate(TM_CCOEFF_NORMED)` + 标准尺度 + `replace_avatar` 去重
   ⇒ **卡槽位置** 稳（本机一次全中、无重复）；
   **前提**是待部署区必须按 **1280×720 标准尺度**取，且**用脸部裁切**做模板。
2. **要得到可信的识别率，必须先有可信真值**：
   **按住每张卡 → 读左侧面板**（本项目已在芬/月见夜上验证可靠）⇒ 逐张建"卡位↔干员"表；
   一次约 10 次手势、~1 分钟，**建立一次即可整局复用**（卡位在整局内不变，只在"有人被部署后"整体左移）。
3. **落地形态建议**：开局（或每次需要部署前）跑一次"卡位表" →
   之后**按干员名查表**取 `avatar_pos` → 直接拖拽；这与 prts+ 的 `locate_avatar(action)` 完全同构。
"""
