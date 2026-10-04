import json, io, sys

LOC = r"E:\__file\ak_kb\gamedata\levels\obt\main\level_main_01-01.json"
LUT = r"data\derived\prts_map_main_01-01.json"
MAA = r"D:\__soft\MAA\resource\Arknights-Tile-Pos\main_01-01-obt-main-level_main_01-01.json"

def load(p):
    with io.open(p, encoding="utf-8", errors="replace") as f:
        return json.load(f)

loc = load(LOC)
lut = load(LUT)
ma = load(MAA)

R = loc["mapData"]["map"].__len__()
C = len(loc["mapData"]["map"][0])
print("local mapData: rows=%d cols=%d tiles=%d" % (R, C, len(loc["mapData"]["tiles"])))
print("local mapId=%s levelId=%s" % (loc.get("mapId"), loc.get("levelId")))

L = [t["tileKey"] for t in loc["mapData"]["tiles"]]
U = [t["tileKey"] for row in lut["tiles"] for t in row]
M = [t["tileKey"] for row in ma["tiles"] for t in row]
print("lens: local=%d lut=%d maa=%d" % (len(L), len(U), len(M)))

def show(name, flat):
    print("=== %s ===" % name)
    for r in range(R):
        print("  %d : %s" % (r, " ".join("%-15s" % flat[r*C+c] for c in range(C))))

show("LOCAL (row0 = mapData.tiles[0..C-1])", L)
show("LUTONADA / MAA as stored", U)

def matches(flat):
    res = {}
    for label, (dr, dc) in {
        "identity": (0, 0),
        "vflip": (R-1, 0),
        "hflip": (0, C-1),
        "hvflip": (R-1, C-1),
    }.items():
        n = 0
        for r in range(R):
            for c in range(C):
                rr = abs(dr - r); cc = abs(dc - c) if dc else c
                rr = (R-1-r) if dr else r
                cc = (C-1-c) if dc else c
                if flat[rr*C+cc] == L[r*C+c]:
                    n += 1
        res[label] = n
    return res

print("match/63 (lut vs local):", matches(U))
print("match/63 (maa vs local):", matches(M))

print("=== start/end markers LOCAL ===")
for r in range(R):
    for c in range(C):
        if L[r*C+c] in ("tile_start", "tile_end"):
            print("  local[r%d][c%d] = %s" % (r, c, L[r*C+c]))
print("=== start/end markers LUTONADA ===")
for r in range(R):
    for c in range(C):
        if U[r*C+c] in ("tile_start", "tile_end"):
            print("  lut[r%d][c%d] = %s" % (r, c, U[r*C+c]))

print("=== routes (game local) start/end positions ===")
for i, rt in enumerate(loc["routes"]):
    sp = rt["startPosition"]; ep = rt["endPosition"]
    print("  route%-2d mode=%-5s start=(row=%s,col=%s) end=(row=%s,col=%s) cps=%s" % (
        i, rt["motionMode"], sp["row"], sp["col"], ep["row"], ep["col"],
        rt.get("checkpoints") and len(rt["checkpoints"]) or 0))

print("=== anchors ===")
for (r, c, name) in [(3,5,"D6"), (3,3,"D4")]:
    lt = loc["mapData"]["tiles"][r*C+c]
    ut = lut["tiles"][r][c]
    mt = ma["tiles"][r][c]
    print("  %s [r%d][c%d] local=%s/%s/%s  lut=%s/%s/%s  maa=%s/%s/%s" % (
        name, r, c,
        lt["tileKey"], lt["heightType"], lt["buildableType"],
        ut["tileKey"], ut["heightType"], ut["buildableType"],
        mt["tileKey"], mt["heightType"], mt["buildableType"]))

print("=== view fields ===")
print("  lut.view:", json.dumps(lut.get("view"), ensure_ascii=False))
print("  maa keys:", sorted(ma.keys()), "same file content as lut:", M == U)
