# FlatBuffers 大表读得慢，慢在哪

对应 ticket [#60 FlatBuffers 大表读得完：先 profile，再改](https://github.com/joycastle/revenant/issues/60)。
实测日期 2026-08-17，机器 Apple Silicon / macOS 25.6 / CPython 3.11.15 (arm64)。
代码基线：改动前 `3342123`，改动后 `revenant/flatbuffers.py` 同一工作树，两个模块并排加载逐输入比对。

The ticket assumed the cost was per-row schema work: "每行都在重新解析
schema、重新探测类型", with the fix being to resolve each table's layout once.
It said to profile before changing anything. **The profile refutes that
hypothesis**, and the change that followed is a different one.

Measured on a synthetic buffer — 184 KB, a root holding a vector of 2,000 item
tables, each with six fields (two ints, a float, two strings, a nested table) —
because no real CMS blob belongs in this repository. The shape mirrors the table
the ticket names.

## What the profile said

Two runs of the same buffer, differing only in whether the schema resolves every
slot:

| | before | ms/row |
|---|---|---|
| every slot resolves | 0.020 s | 0.010 |
| one unresolved slot per row | 1.342 s | 0.671 |

So schema handling is not the bottleneck: with the schema doing its job the
whole 2,000-row read took 20 ms. Resolving each table's layout once — the fix
the ticket proposed — would have bought almost nothing.

The 67× gap between the two rows is the finding. `cProfile` on the slow one:

```
ncalls  tottime  cumtime  function
 10979    2.054    4.184  flatbuffers.py:99(vtable)
9008797    1.431    1.900  flatbuffers.py:82(u16)
9094121    0.475    0.475  {built-in method _struct.unpack_from}
  8000    0.035    4.238  flatbuffers.py:193(probe)
```

Nine million `u16` reads for eleven thousand vtable lookups — about 820 reads
per lookup, for tables with six slots. `probe` accounts for essentially the
whole run.

## The cause

`probe` runs `as_table` over bytes that are usually *not* a table, to find out
whether they are. `as_table` asked `vtable`, which built the full list of field
offsets — and then threw it away, keeping only whether the count was nonzero:

```python
slots, _ = vtable(buf, at)
return at if slots else None
```

On bytes that are not a vtable, the declared length is arbitrary. A `vt_len` of
`0xfffe` passes every bounds check on any buffer over 64 KB, and the loop then
runs 32,765 times building a list nobody reads.

## The change

Split the header parse from materialising the offsets. `vtable_header` returns
the declared count from the header alone — four reads, no loop — and `as_table`
asks that. `vtable` still returns the full list for callers that want it, now
via one `struct.unpack_from` over the contiguous offset array instead of one
call per slot.

Deliberately **not** tightened. Rejecting implausible vtables outright would be
faster still, and would be a different set of answers: this is a speed change,
and the output has to be the same output.

## Results

Same buffer, same schema, `min` of three runs:

| case | before | after | |
|---|---|---|---|
| 3 rows, resolved | 0.029 ms | 0.028 ms | 1.1× |
| 3 rows, probes | 0.055 ms | 0.054 ms | 1.1× |
| 2,000 rows, resolved | 18.2 ms | 17.3 ms | 1.1× |
| 2,000 rows, probes | 1,304.7 ms | 37.8 ms | **34.5×** |

Small tables are not slower, which was the other thing to check.

## Byte-identical, checked rather than argued

The old module was loaded beside the new one and both were run over the same
inputs:

- the 300-row buffer with a fully resolving schema — same decode, same
  `inferred` list;
- the same buffer with a schema that leaves slots unresolved, so every row
  probes — same decode, same `inferred` list;
- 500 random noise buffers through `walk` and `strings`, where a bogus vtable is
  the normal case rather than the exception — same slots, same readings;
- **every one of the 65,536 values a `vt_len` field can hold**, at a fixed
  layout, comparing `vtable` including which inputs raise;
- 16,000 `vtable` and `as_table` comparisons over random buffers at four
  positions each.

The exhaustive sweep earned its keep. A `vt_len` of 2 clears every guard —
non-zero, even, inside the buffer — and yields a slot count of **-1**, which is
truthy. The loop that was replaced ran `range(-1)` and produced an empty list;
the batched read handed the -1 to `struct` as a repeat count and raised. Random
buffers had not once landed on it, and a probe on a real corpus meets malformed
vtables constantly. `vtable` now guards on `<= 0` and returns the same `(-1, [])`
it always did.

## What this does not measure

The ticket's "1 秒/条" is a figure from the project, on a real CMS blob through
`fbread.py`. Nothing here reproduces it, so the 34.5× is a speedup on this
shape, not a prediction about that one. What the two columns above do establish
is which of the two shapes was expensive: a read whose schema resolves was never
slow, and a read that falls back to probing was slow for a reason that had
nothing to do with schemas. If the real corpus is still slow after this, the
next profile should be run on it, and it will be measuring something else.
