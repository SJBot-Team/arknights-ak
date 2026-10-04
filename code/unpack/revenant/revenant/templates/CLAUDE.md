# IL2CPP / xLua 逆向工程项目 (Revenant)

这是一个由 `revenant init` 生成的逆向工程工作目录。目标游戏的 package / 版本 / 架构由工具**自动检测**——开工先调 `re_status` 看当前目标与就绪状态。把 apk/xapk 放进项目根、跑一遍准备流水线即可换游戏,无需改任何代码(代码在已安装的 `revenant` 包里,不在本目录)。

## 逆向工具(re MCP server)

分析能力由 `re` MCP server 提供(只读,已在 `.claude/settings.json` 里免确认),工具名 `mcp__re__*`;文件读写用内置 Read / Write / Edit。

- `re_status` —— 自检 + 目标身份(package / version / 架构)+ 索引 / Lua 就绪。**每次开工先调它,拿 `<version>` 用于路径。**
- `re_search(query, limit)` —— 按名搜类/方法,拿 RVA(发现入口)
- `re_type_info(type_name)` —— 类的字段(含 offset)+ 方法 + enum 值名 + const 字面量
- `re_find_asm(rva)` —— 方法 ISIL 汇编(复原首选输入,架构无关)
- `re_cfg(rva)` —— 控制流:基本块 / 循环 / always-executed 集合(含分支的方法先调它)
- `re_lookup` / `re_xrefs` / `re_callgraph` —— RVA→名 / 调用方 / 调用图(只统计直接 bl/b;虚/接口/委托调用不可见,0 ≠ 未使用)
- `re_field_scan` / `re_disasm` / `re_evidence` —— 字段扫描 / 裸反汇编 / 证据包
- **xLua 游戏的 Lua 逻辑**:`re_lua_list` / `re_lua_source` / `re_lua_grep`(全文搜)/ `re_lua_refs`(交叉引用)/ `re_lua_bridge`(过 C#↔Lua 桥)

RVA 是十六进制(如 `0x00B10014`)。先用 `re_search` 解析成 RVA,或读 `re_type_info` 给的 `.cs` 看 `[Address(RVA=...)]`。

## 方法论

复原方法论(证据分级、`src/` scaffold gate、`re_cfg` 时机、xLua 跨层)全部在 `re` 技能里,做逆向时它会自动加载——不在本文件重复。入口命令:`/re-deep`、`/re-scaffold`、`/re-map`、`/re-verify`。

## 数据准备流水线(版本/Unity 自动检测)

把 apk/xapk 放项目根,然后**一条命令**跑完整条流水线:

```bash
revenant prepare    # extract-apks → find-binary/metadata → run-cpp2il(ISIL+DiffableCs)
                    # → build-indices → seed-src → lua-extract(xLua,需先配 [lua])
```

`prepare` 会跳过已完成的昂贵步骤;`--force` 重做,`--keep-going` 跳过失败继续,`revenant status` 看就绪状态。单跑某一步用 `revenant prepare --only <step>`(如 `--only run-cpp2il`)。xLua 游戏若 `[lua]` 未配,`prepare` 会停下提示你先逆 Lua 加载器、填 `[lua]`,再重跑即可补上 lua-extract。

换游戏:换 apk、`revenant prepare`、重启 Claude Code 让 MCP server 重连。

## 文档约定

标识符/代码/`src/` C# 一律英文;正文中文可。不用 emoji,不用 `---` 分隔线。RE 发现写 `notes/<arch|core|elem|rule>-NN-<slug>.md`。提交时文档与代码分开 commit。
