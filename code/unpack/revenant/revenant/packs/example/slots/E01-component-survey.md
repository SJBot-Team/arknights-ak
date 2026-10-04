---
id: E01
title: 这个游戏接了哪些第三方组件
facets:
  platform_differences:
    applicable: false
  core_mechanism:
    threshold: structural
    ceiling: structural
probes:
  - kind: class_regex
    pattern: ".*(Sdk|SDK|Manager|Bridge)$"
  - kind: string_const
    values: ["applovin", "appsflyer", "firebase", "adjust"]
---

## 问题

在判断任何一块功能是自研还是第三方之前，先普查这个包里到底装了哪些组件。

## 什么算好答案

一张表，逐个组件写明：在场证据（类名 / 字符串 / 原生库）、以及**是否真的被调用**。
字符串证明「在场」，调用图才证明「在用」——这两件事在语料里被混淆过，并造成过三处归属误判。

## 常见的坑

只抓三级包名会漏掉一整批组件；原生库不要按文件名猜厂商，要看导出符号。
