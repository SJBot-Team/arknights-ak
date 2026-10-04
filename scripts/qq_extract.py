"""
qq_extract.py — NTQQ 聊天记录增量提取工具（低消耗、高效、即时）

原理：
  1. 密钥：从运行中的 QQ 进程内存扫描提取（qq_dump_key.py），缓存到 key_map.json
  2. 主库 nt_msg.db 为 SQLCipher 加密（1024B 自定义头 + AES-256-CBC 页加密）；
     本工具实现迷你 SQLite b-tree 读取器，按需解密少量页（秒级），
     直接从加密源文件读取 c2c_msg_table（单聊消息表），避免全量解密 1.4GB
  3. 联系人：解密小的 profile_info.db 后检索昵称/备注 → uid

用法（QQ 需保持登录运行；Python = comp_physics\\.venv）：
  python qq_extract.py keys                          # 刷新密钥（内存扫描，~1s）
  python qq_extract.py find-peer 调零                # 按昵称/备注找联系人 uid
  python qq_extract.py chat --peer <uid> [--limit N] [--since TS] [--new] [--out FILE]
  python qq_extract.py chat --peer <uid> --new       # 只输出上次之后的新消息（增量）

数据源：E:\\QQ\\Tencent Files\\<QQ号>\\nt_qq\\nt_db\\（可 --db-base / --qq 覆盖）
说明：读取的是主库文件快照（含最近一次 checkpoint 前的消息）；WAL 中更新的
      消息暂不可解（NTQQ 定制 WAL 加密未公开），但主库 checkpoint 较频繁，
      一般可覆盖到最近数小时。
"""
import argparse
import datetime
import hashlib
import hmac as hmac_mod
import json
import os
import struct
import subprocess
import sys

try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    HAVE_CRYPTO = True
except ImportError:
    HAVE_CRYPTO = False

# ── 常量 ──────────────────────────────────────────────────────────────────────
EXT_HEADER = 1024
PAGE_SIZE = 4096
RESERVE = 48
IV_SIZE = 16
HMAC_SIZE = 20

DEFAULT_DB_BASE = r"E:\QQ\Tencent Files"
DEFAULT_QQ = "<QQ号>"
WORK_DIR = os.path.dirname(os.path.abspath(__file__))
KEY_MAP = os.path.join(WORK_DIR, "..", "_raw", "qq", "key_map.json")
STATE_FILE = os.path.join(WORK_DIR, "..", "_raw", "qq", "state.json")
OUT_DIR = os.path.join(WORK_DIR, "output", DEFAULT_QQ)
PROFILE_PLAIN = os.path.join(OUT_DIR, "profile_info.db")

# ── 工具函数 ──────────────────────────────────────────────────────────────────

def ts_str(t):
    if not t:
        return "?"
    return datetime.datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S")


def read_shared(path):
    """读文件（允许其他进程同时读写，兼容 QQ 占用中的数据库）。"""
    with open(path, "rb") as f:
        return f.read()


def decrypt_page(page_data, aes_key, skip_salt=0):
    data = page_data[skip_salt:]
    encrypted = data[:len(data) - RESERVE]
    iv = data[len(data) - RESERVE:len(data) - RESERVE + IV_SIZE]
    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
    dec = cipher.decryptor()
    return dec.update(encrypted) + dec.finalize()


# ── 迷你 SQLite b-tree 读取器（在加密源文件上按页解密）─────────────────────

class CipherDb:
    """按需解密页的只读 SQLite 阅读器（针对 NTQQ 的 1024B 头 + SQLCipher 页）。"""

    def __init__(self, db_path, aes_key):
        self.f = open(db_path, "rb")
        self.aes_key = aes_key
        self.page_size = PAGE_SIZE
        self.page_cache = {}

    def close(self):
        self.f.close()

    def read_page(self, pgno):
        if pgno in self.page_cache:
            return self.page_cache[pgno]
        off = EXT_HEADER + (pgno - 1) * self.page_size
        self.f.seek(off)
        raw = self.f.read(self.page_size)
        if len(raw) < self.page_size:
            raise ValueError(f"page {pgno} truncated")
        dec = decrypt_page(raw, self.aes_key, skip_salt=16 if pgno == 1 else 0)
        if pgno == 1:
            dec = b"SQLite format 3\x00" + dec
        if len(dec) < self.page_size:
            dec += b"\x00" * (self.page_size - len(dec))
        self.page_cache[pgno] = dec
        return dec

    # SQLite varint
    @staticmethod
    def read_varint(buf, off):
        v = 0
        for i in range(8):
            b = buf[off + i]
            v = (v << 7) | (b & 0x7F)
            if not (b & 0x80):
                return v, off + i + 1
        b = buf[off + 8]
        return (v << 8) | b, off + 9

    def table_root(self, table_name):
        """遍历 sqlite_master 找目标表的 root 页与建表 SQL。"""
        root = 1
        stack = [(root, 100)]  # (pgno, btree_content_offset)
        while stack:
            pgno, boff = stack.pop()
            page = self.read_page(pgno)
            ptype = page[boff]
            ncell = struct.unpack(">H", page[boff + 3:boff + 5])[0]
            if ptype == 0x0D:  # leaf table
                cellptr = boff + 8
                for i in range(ncell):
                    cpos = struct.unpack(">H", page[cellptr + i * 2:cellptr + i * 2 + 2])[0]
                    plen, p = self.read_varint(page, cpos)
                    rowid, p = self.read_varint(page, p)
                    try:
                        record = self.parse_record(page, p, plen)
                    except Exception:
                        continue
                    if len(record) >= 5 and record[0] == "table" and record[1] == table_name:
                        return record[3], record[4]  # rootpage, sql
            elif ptype == 0x05:  # interior table
                right = struct.unpack(">I", page[boff + 8:boff + 12])[0]
                stack.append((right, 0))
                cellptr = boff + 12
                for i in range(ncell):
                    cpos = struct.unpack(">H", page[cellptr + i * 2:cellptr + i * 2 + 2])[0]
                    child = struct.unpack(">I", page[cpos:cpos + 4])[0]
                    stack.append((child, 0))
            else:
                raise ValueError(f"unexpected page type {ptype} at pgno {pgno}")
        raise KeyError(f"table {table_name} not found")

    @staticmethod
    def parse_record(page, off, total_len):
        """解析 SQLite 记录：返回列值列表。"""
        end = off + total_len
        hlen, p = CipherDb.read_varint(page, off)
        serial = []
        while p < off + hlen:
            st, p = CipherDb.read_varint(page, p)
            serial.append(st)
        vals = []
        for st in serial:
            if st == 0:
                vals.append(None)
            elif st == 1:
                vals.append(page[p]); p += 1
            elif st == 2:
                vals.append(struct.unpack(">h", page[p:p + 2])[0]); p += 2
            elif st == 3:
                vals.append(int.from_bytes(page[p:p + 3], "big", signed=True)); p += 3
            elif st == 4:
                vals.append(struct.unpack(">i", page[p:p + 4])[0]); p += 4
            elif st == 5:
                vals.append(int.from_bytes(page[p:p + 6], "big", signed=True)); p += 6
            elif st == 6:
                vals.append(struct.unpack(">q", page[p:p + 8])[0]); p += 8
            elif st == 7:
                vals.append(struct.unpack(">d", page[p:p + 8])[0]); p += 8
            elif st in (8, 9):
                vals.append(st - 8)
            elif st in (10, 11):
                vals.append(8 - st)
            elif st == 12:
                vals.append(b"")  # 0-length blob
            elif st >= 13:
                # SQLite 规则：长度 = (st-12)//2；奇数=text，偶数=blob
                ln = (st - 12) // 2
                if st % 2 == 1:
                    vals.append(page[p:p + ln].decode("utf-8", "replace")); p += ln
                else:
                    vals.append(page[p:p + ln]); p += ln
            else:
                raise ValueError(f"bad serial type {st}")
        if p > end:
            # 截断保护：不抛异常，丢弃越界部分
            p = end
        return vals

    def walk_table(self, root, columns, predicate=None, sort_key=None, limit=None):
        """遍历表（含 overflow 处理），返回行字典列表。"""
        rows = []
        stack = [(root, 0)]
        while stack:
            pgno, boff = stack.pop()
            page = self.read_page(pgno)
            ptype = page[boff]
            ncell = struct.unpack(">H", page[boff + 3:boff + 5])[0]
            if ptype == 0x0D:
                cellptr = boff + 8
                for i in range(ncell):
                    cpos = struct.unpack(">H", page[cellptr + i * 2:cellptr + i * 2 + 2])[0]
                    plen, p = self.read_varint(page, cpos)
                    rowid, p = self.read_varint(page, p)
                    try:
                        record = self.parse_record(page, p, plen)
                    except Exception:
                        continue
                    # overflow 恢复
                    record = self._fetch_overflow(record, page, p, plen)
                    if len(record) >= len(columns):
                        row = dict(zip(columns, record))
                        if predicate is None or predicate(row):
                            rows.append(row)
                            if limit and len(rows) >= limit:
                                return rows
            elif ptype == 0x05:
                right = struct.unpack(">I", page[boff + 8:boff + 12])[0]
                stack.append((right, 0))
                cellptr = boff + 12
                for i in range(ncell):
                    cpos = struct.unpack(">H", page[cellptr + i * 2:cellptr + i * 2 + 2])[0]
                    child = struct.unpack(">I", page[cpos:cpos + 4])[0]
                    stack.append((child, 0))
        return rows

    def _fetch_overflow(self, record, page, off, total_len):
        """把记录中的 overflow 页内容拼回。简单实现：对 40800 等 blob 列。
        本实现直接返回原 record（当前消息体较小，一般无 overflow）。
        如需支持大消息，可在此实现 overflow 链读取。"""
        return record


# ── 密钥管理 ──────────────────────────────────────────────────────────────────

def load_keys(qq, db_base):
    if not os.path.exists(KEY_MAP):
        refresh_keys(qq, db_base)
    with open(KEY_MAP, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["key_map"]


def refresh_keys(qq, db_base):
    """调用 qq_dump_key.py 从内存提取密钥（QQ 需运行）。"""
    script = os.path.join(WORK_DIR, "qq_dump_key.py")
    py = sys.executable
    subprocess.run([
        py, script, "--qq", qq, "--db-base", db_base, "--key-only", "-o", KEY_MAP
    ], check=True)


def key_for(db_name, key_map, qq=DEFAULT_QQ, db_base=DEFAULT_DB_BASE):
    """按文件名反查密钥：解密目标文件页 1，校验页大小字段（解密内容从
    SQLite 头第 16 字节起，即页大小字段位置）。"""
    path = os.path.join(db_base, qq, "nt_qq", "nt_db", db_name)
    head = read_shared(path)[EXT_HEADER:EXT_HEADER + PAGE_SIZE]
    for salt_hex, key_hex in key_map.items():
        aes = bytes.fromhex(key_hex)
        try:
            dec = decrypt_page(head, aes, skip_salt=16)
            if dec[0:2] == struct.pack(">H", PAGE_SIZE):
                return aes
        except Exception:
            continue
    raise RuntimeError(f"cannot find key for {db_name}")


# ── 联系人查找 ────────────────────────────────────────────────────────────────

def find_peer(keyword, qq, db_base):
    key_map = load_keys(qq, db_base)
    # 每次重新解密 profile_info.db（小，秒级；避免陈旧/损坏缓存）
    import sqlite3
    os.makedirs(OUT_DIR, exist_ok=True)
    aes = key_for("profile_info.db", key_map, qq, db_base)
    raw = read_shared(os.path.join(db_base, qq, "nt_qq", "nt_db", "profile_info.db"))
    out = bytearray()
    sc = raw[EXT_HEADER:]
    for pgno in range(1, len(sc) // PAGE_SIZE + 1):
        p = sc[(pgno - 1) * PAGE_SIZE: pgno * PAGE_SIZE]
        dec = decrypt_page(p, aes, skip_salt=16 if pgno == 1 else 0)
        if pgno == 1:
            dec = b"SQLite format 3\x00" + dec
        if len(dec) < PAGE_SIZE:
            dec += b"\x00" * (PAGE_SIZE - len(dec))
        out.extend(dec)
    with open(PROFILE_PLAIN, "wb") as f:
        f.write(out)
    con = sqlite3.connect(PROFILE_PLAIN)
    cur = con.cursor()
    # 列名从建表 SQL 取（避免 LIMIT 1 撞损坏页）
    cur.execute("SELECT sql FROM sqlite_master WHERE name='profile_info_v6'")
    sql = cur.fetchone()[0]
    import re
    cols = re.findall(r"\[(\d+)\]", sql)
    name_cols = [c for c in cols if c in ("1000", "1001", "20002", "20003", "20004", "20009", "20011", "24106", "24107", "24108", "24109")]
    hits = []
    rids = [r[0] for r in cur.execute("SELECT rowid FROM profile_info_v6")]
    for i in range(0, len(rids), 500):
        chunk = rids[i:i + 500]
        try:
            q = "SELECT " + ",".join(f"[{c}]" for c in name_cols) + " FROM profile_info_v6 WHERE rowid IN (%s)" % ",".join("?" * len(chunk))
            for r in cur.execute(q, chunk):
                if any(v and keyword in str(v) for v in r):
                    hits.append(dict(zip(name_cols, r)))
        except Exception:
            continue
    con.close()
    return hits


# ── 聊天读取 ──────────────────────────────────────────────────────────────────

def read_chat(peer_uid, since=None, limit=100, qq=DEFAULT_QQ, db_base=DEFAULT_DB_BASE):
    key_map = load_keys(qq, db_base)
    aes = key_for("nt_msg.db", key_map, qq, db_base)
    db = CipherDb(os.path.join(db_base, qq, "nt_qq", "nt_db", "nt_msg.db"), aes)
    try:
        root, sql = db.table_root("c2c_msg_table")
        # 解析列顺序（记录含 40001 槽位，其值为 NULL，rowid 在 b-tree key 中）
        import re
        cols = re.findall(r"\[(\d+)\]", sql)
        rows = db.walk_table(root, cols, predicate=lambda r: r.get("40021") == peer_uid or r.get("40020") == peer_uid)
    finally:
        db.close()
    rows.sort(key=lambda r: r.get("40050") or 0)
    if since:
        rows = [r for r in rows if (r.get("40050") or 0) > since]
    if limit:
        rows = rows[-limit:]
    return rows, cols


def pb_texts(blob, depth=0):
    """从 40800 protobuf 中提取可读中文文本片段。"""
    texts = []
    if not blob:
        return texts

    def parse_pb(data):
        out = []
        i = 0
        n = len(data)
        while i < n:
            tag = 0
            shift = 0
            while True:
                b = data[i]
                i += 1
                tag |= (b & 0x7F) << shift
                shift += 7
                if not (b & 0x80):
                    break
            field = tag >> 3
            wt = tag & 7
            if wt == 0:
                while True:
                    b = data[i]
                    i += 1
                    if not (b & 0x80):
                        break
            elif wt == 1:
                i += 8
            elif wt == 2:
                ln = 0
                shift = 0
                while True:
                    b = data[i]
                    i += 1
                    ln |= (b & 0x7F) << shift
                    shift += 7
                    if not (b & 0x80):
                        break
                out.append((field, data[i:i + ln]))
                i += ln
            elif wt == 5:
                i += 4
            else:
                break
        return out

    def walk(data, d):
        try:
            fields = parse_pb(data)
        except Exception:
            return
        for field, val in fields:
            try:
                s = val.decode("utf-8")
                if s and any('\u4e00' <= ch <= '\u9fff' for ch in s) and len(s) < 2000:
                    texts.append(s)
            except Exception:
                pass
            if d < 3:
                walk(val, d + 1)

    walk(blob, 0)
    return texts


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="NTQQ 聊天记录增量提取")
    ap.add_argument("cmd", choices=["keys", "find-peer", "chat"])
    ap.add_argument("--qq", default=DEFAULT_QQ)
    ap.add_argument("--db-base", default=DEFAULT_DB_BASE)
    ap.add_argument("--peer", default=None, help="联系人 uid（find-peer 得到）")
    ap.add_argument("--keyword", default=None, help="find-peer 搜索关键词")
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--since", type=int, default=None, help="只读该时间戳之后的消息")
    ap.add_argument("--new", action="store_true", help="只读上次之后的新消息（增量）")
    ap.add_argument("--out", default=None, help="输出到 UTF-8 文件")
    args = ap.parse_args()

    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    result = None

    if args.cmd == "keys":
        refresh_keys(args.qq, args.db_base)
        print("密钥已刷新:", KEY_MAP)

    elif args.cmd == "find-peer":
        if not args.keyword:
            ap.error("find-peer 需要 --keyword")
        hits = find_peer(args.keyword, args.qq, args.db_base)
        result = {"hits": [{"uid": h.get("1000"), "fields": {k: v for k, v in h.items()}} for h in hits]}
        print(json.dumps(result, ensure_ascii=False, indent=1))

    elif args.cmd == "chat":
        if not args.peer:
            ap.error("chat 需要 --peer <uid>")
        state = {}
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
        since = args.since
        if args.new:
            since = state.get(args.peer, {}).get("last_seq_ts", 0)
        rows, cols = read_chat(args.peer, since=since, limit=args.limit, qq=args.qq, db_base=args.db_base)
        msgs = []
        max_ts = 0
        for r in rows:
            max_ts = max(max_ts, r.get("40050") or 0)
            texts = pb_texts(r.get("40800"))
            msgs.append({
                "time": ts_str(r.get("40050")),
                "ts": r.get("40050"),
                "sender": r.get("40020"),
                "text": "\n".join(texts[:6]) if texts else "",
            })
        state[args.peer] = {"last_seq_ts": max_ts}
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=1)
        result = {"peer": args.peer, "count": len(msgs), "max_ts": max_ts, "messages": msgs}

    if result is not None:
        text = json.dumps(result, ensure_ascii=False, indent=1)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as f:
                f.write(text)
            print("已写入:", args.out)
        else:
            print(text)


if __name__ == "__main__":
    main()
