"""时钟插件包：为打图任务提供「逻辑帧时钟」抽象。

可用时钟源（见 cost_ruler.py）：
  - ruler    ：费用尺（ArknightsCostBarRuler）本机 API，最精确，需尺子在跑
  - cost_bar ：自研费用条识别器兜底，只依赖截图
"""
