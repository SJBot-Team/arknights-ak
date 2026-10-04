---
id: E02
title: 归因是怎么做的
facets:
  core_mechanism:
    threshold: disassembly
    ceiling: managed_code
probes:
  - kind: class_regex
    pattern: ".*(Attribution|Attrib|Referrer|Install).*"
  - kind: method_regex
    pattern: ".*(Track|Report)(Install|Conversion).*"
  - kind: string_const
    values: ["media_source", "af_status", "install_referrer", "campaign"]
---

## 问题

安装来源怎么采、怎么回传、谁裁决。

## 什么算好答案

从采集点到回传端点的完整链路，且指出**哪些字段由服务端裁决**——那部分拿不到具体数值时，
用缺口标记记下来，不要因此把整条结论降级：结论成立，缺的只是数值。

## 常见的坑

这个槽位的核心机制切面在多数靶子上到不了反汇编级，因为链路的一半在原生 SDK 里。
上限已经预标成「托管代码坐实」——标得比它高会收到警告。
