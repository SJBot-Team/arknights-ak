"""Frida recipes for locating and driving an in-place decryptor.

Two moves recurred (#32):

- **write-protect probe** (`write_protect_recipe`): a container is decrypted in
  place, one record at a time, so making it read-only turns each decryption
  into a fault whose PC is the decryptor. On a fault we un-protect just that
  page and continue, so the game keeps running and later writes on other pages
  still get caught. Note from the field: `Process.setExceptionHandler` is itself
  detected by some anti-cheat during startup -- attach a few seconds in and hook
  only cold functions, or arm this after the game is running.

- **reload probe** (`reload_recipe`): replay the loader on a container, then
  call the post-load fix-up the runtime does through the image's vtable, so the
  assembly's name lookups resolve.

Both take addresses/offsets as parameters; nothing is baked in. They return
JavaScript source to hand to `frida -l` or a Frida `Script`.
"""

from __future__ import annotations


def write_protect_recipe(base_expr: str, size: int, page_size: int = 0x4000,
                         tick_seconds: int = 5) -> str:
    """JS that write-protects [base, base+size) and reports each faulting PC.

    `base_expr` is a JS expression yielding the region base (e.g.
    `"Process.findModuleByName('libil2cpp.so').base.add(0x1234000)"`).
    """
    return f"""// Report the PC of every instruction that writes into the protected region.
const IMAGE = {base_expr};
const SIZE = {size};
const PAGE = {page_size};
const seen = {{}};
let faults = 0;

Process.setExceptionHandler(function (details) {{
    const addr = details.memory ? details.memory.address : null;
    if (!addr || addr.compare(IMAGE) < 0 || addr.compare(IMAGE.add(SIZE)) >= 0) {{
        return false;
    }}
    const pc = details.context.pc;
    const mod = Process.findModuleByAddress(pc);
    const key = pc.toString();
    if (!seen[key]) {{
        seen[key] = true;
        send({{ type: 'write', pc: key,
                module: mod ? mod.name : '?',
                offset: mod ? pc.sub(mod.base).toString() : '?',
                target: addr.toString(),
                imageOffset: addr.sub(IMAGE).toString() }});
    }}
    Memory.protect(addr.and(ptr(PAGE - 1).not()), PAGE, 'rw-');
    faults++;
    return true;
}});

Memory.protect(IMAGE, SIZE, 'r--');
send({{ type: 'armed', base: IMAGE.toString(), size: SIZE }});
setInterval(function () {{ send({{ type: 'tick', faults: faults }}); }}, {tick_seconds * 1000});
"""


def reload_recipe(module: str, create_rva: int, load_vtable_slot: int = 0x10,
                  post_vtable_slot: int = 0x138, in_path: str = "/data/local/tmp/cont.bin",
                  out_path: str = "/data/local/tmp/cont.out") -> str:
    """JS that recreates an image from `in_path`, runs load + the post-load pass,
    and writes the fully materialised container to `out_path`."""
    return f"""// Replay the container load, including the post-load fix-up pass.
const m = Process.findModuleByName('{module}');
const CREATE = m.base.add({hex(create_rva)});
const bytes = File.readAllBytes('{in_path}');
const len = bytes.byteLength;
const buf = Memory.alloc(len);
buf.writeByteArray(bytes);
const holder = Memory.alloc(0x400);
send({{ type: 'setup', len: len }});

function dump(tag) {{
    const out = new File('{out_path}', 'wb');
    out.write(buf.readByteArray(len));
    out.close();
    send({{ type: 'wrote', tag: tag }});
}}

try {{
    new NativeFunction(CREATE, 'int', ['pointer', 'pointer'])(holder, buf);
    const image = holder.add(8).readPointer();
    const vt = image.readPointer();
    new NativeFunction(vt.add({hex(load_vtable_slot)}).readPointer(), 'int',
                       ['pointer', 'pointer', 'uint64'])(image, buf, len);
    dump('after-load');
    const post = vt.add({hex(post_vtable_slot)}).readPointer();
    const fn = new NativeFunction(post, ['uint64', 'uint64', 'uint64', 'uint64'], ['pointer', 'int']);
    fn(image, 1);
    dump('after-post');
}} catch (e) {{
    send({{ type: 'error', msg: '' + e }});
}}
"""
