# 模板库（templates/）

丢进来的 PNG/JPG 就是可识别的目标；**文件名即模板名**，子目录会拼进名字。

```
templates\
├── main\start.png        →  模板名 "main/start"
├── battle\pause.png      →  模板名 "battle/pause"
└── common\loading.png    →  模板名 "common/loading"
```

## 制作模板的建议

1. 从实际画面截图（分辨率/缩放/窗口大小保持与运行时一致）；
2. 裁剪到**特征稳定**的区域（避开会变化的数字、动画、闪烁元素）；
3. 尺寸别太大：40×40 ~ 200×80 之间匹配最快最稳；越大越慢（成本≈面积）；
4. 同一目标若有多种外观（高亮/普通），分别存两张，在流水线里做成两个节点或 `scales` 多尺度；
5. 半透明按钮可用 `mask` 参数（另存一张同尺寸黑白掩码图）。

## 复用 MAA 的模板（推荐）

MAA 自带 **2149 张**明日方舟模板（`D:\__soft\MAA\resource\template\`），按需挑选即可：

```powershell
$dst = "C:\Users\23922\Documents\ds_harness\ak\code\vision\templates\maa"
New-Item -ItemType Directory -Force $dst | Out-Null
Copy-Item "D:\__soft\MAA\resource\template\StartUp*" $dst -ErrorAction SilentlyContinue
Copy-Item "D:\__soft\MAA\resource\template\*Confirm*" $dst -ErrorAction SilentlyContinue
```

> 注意：MAA 模板按 **1280×720（或 720p 基准）** 制作；若客户端分辨率不同，
> 需用 `scales`（多尺度）或先把画面缩放到与模板一致的基准分辨率。

## 目录约定（本项目自建）

- `main\`   主界面/导航
- `battle\` 作战内元素
- `common\` 通用弹窗/加载
- `maa\`    从 MAA 复制的模板
