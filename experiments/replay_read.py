#!/usr/bin/env python3
"""Decode a .replay26 into a readable event log -- what the opponent actually did.

Every measurement in this project until now came from mirror A/Bs and from the
engine's one-line JSON summary. Neither can tell you *how* a real opponent beat
us. The ladder hands back replays; this reads them.

Field numbering recovered by inspection of known games, so best-effort:

  header      f1 width, f2 height, f3* terrain rows, f4* starting entities
  turn.f1.f1  SPAWN   {1:id, 2:team, 3:{1:x,2:y}, 4:hp, 5:maxhp}
  turn.f1.f2  MOVE    {1:id, 2:pos}
  turn.f1.f3  DEATH   {1:id}
  turn.f1.f4  BUILD   {1:{2:kind, 2:pos, 3:dir}}
  turn.f1.f5  RESOURCE{1:team, 2:signed delta}
  turn.f1.f12 FIRE    {1:from_pos, 2:to_pos}

Entity kind comes from max HP; the 40-HP pair (builder bot / sentinel) is split
by whether the entity ever moves.

  python3 replay_read.py <file.replay26> [--us TEAM] [--verbose]
"""
import sys, collections

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from pbdump import parse

KIND = {500: "core", 30: "harvester/barrier", 25: "gunner", 20: "conveyor"}


def flds(buf):
    d = collections.defaultdict(list)
    for fn, wt, v in parse(buf):
        d[fn].append(v)
    return d


def pos(buf):
    p = flds(buf)
    return (p[1][0] if 1 in p else 0, p[2][0] if 2 in p else 0)


def load(path):
    top = parse(open(path, "rb").read())
    hdr = flds([v for fn, _, v in top if fn == 1][0])
    w, h = hdr[1][0], hdr[2][0]
    ents, moved = {}, set()

    def spawn(rec, turn):
        g = flds(rec)
        eid = g[1][0] if 1 in g else None
        ents[eid] = {"id": eid, "team": g[2][0] if 2 in g else 0,
                     "pos": pos(g[3][0]) if 3 in g else (0, 0),
                     "maxhp": g[5][0] if 5 in g else None, "born": turn}
        return ents[eid]

    core_ids = []
    for rec in hdr.get(4, []):
        e = spawn(rec, 0)
        e["maxhp"] = 500          # header entities carry no HP field; they are the cores
        core_ids.append(e["id"])

    log = []
    for turn, t in enumerate([v for fn, _, v in top if fn == 3]):
        for fn, wt, v in parse(t):
            if fn != 1 or not isinstance(v, (bytes, bytearray)):
                continue
            for ev, _w, payload in parse(v):
                if not isinstance(payload, (bytes, bytearray)):
                    continue
                g = flds(payload)
                if ev == 1 and 1 in g:
                    e = spawn(g[1][0], turn)
                    log.append((turn, "SPAWN", dict(e)))   # snapshot: pos is mutated by MOVE
                elif ev == 2 and 1 in g and 2 in g:
                    eid = g[1][0]
                    moved.add(eid)
                    if eid in ents:
                        ents[eid]["pos"] = pos(g[2][0])
                elif ev == 3 and 1 in g:
                    log.append((turn, "DEATH", dict(ents.get(g[1][0], {"id": g[1][0]}))))
                elif ev == 12 and 1 in g and 2 in g:
                    log.append((turn, "FIRE", (pos(g[1][0]), pos(g[2][0]))))
    return w, h, ents, moved, log, core_ids


def kind_of(e, moved):
    m = e.get("maxhp")
    if m == 40:
        return "builder" if e["id"] in moved else "SENTINEL"
    return KIND.get(m, f"hp{m}")


def main():
    path = sys.argv[1]
    us = int(sys.argv[sys.argv.index("--us") + 1]) if "--us" in sys.argv else 0
    w, h, ents, moved, log, core_ids = load(path)
    them = 1 - us

    cores = {ents[i]["team"]: ents[i]["pos"] for i in core_ids}
    print(f"{path.rsplit('/',1)[-1]}   map {w}x{h}   our core {cores.get(us)}   "
          f"their core {cores.get(them)}")

    deaths = [(t, e) for t, k, e in log if k == "DEATH"]
    end = max((t for t, _, _ in log), default=0)
    for t, e in deaths:
        if e.get("maxhp") == 500:
            print(f"   -> core of team {e.get('team')} destroyed on turn {t}")
    print()

    # what they built, and when
    print("THEIR BUILD ORDER")
    for t, k, e in log:
        if k == "SPAWN" and e["team"] == them:
            d = abs(e["pos"][0] - cores.get(us, (0, 0))[0]) + abs(e["pos"][1] - cores.get(us, (0, 0))[1])
            print(f"  turn {t:>3}  {kind_of(e, moved):<9} at {str(e['pos']):<9} "
                  f"{d:>2} tiles from our core")

    # shots that landed on our half
    fires = [(t, a, b) for t, k, v in log if k == "FIRE" for a, b in [v]]
    ours = cores.get(us, (0, 0))
    at_core = [(t, a, b) for t, a, b in fires
               if abs(b[0] - ours[0]) <= 2 and abs(b[1] - ours[1]) <= 2]
    print(f"\nSHOTS AT OUR CORE: {len(at_core)} of {len(fires)} total fire events")
    if at_core:
        first = at_core[0]
        print(f"  first on turn {first[0]} from {first[1]}")
        srcs = collections.Counter(a for _, a, _ in at_core)
        for src, n in srcs.most_common(8):
            d = abs(src[0] - ours[0]) + abs(src[1] - ours[1])
            print(f"  {n:>3} shots from {str(src):<9} ({d} tiles out)")
    per = collections.Counter(t for t, _, _ in at_core)
    if per:
        print("  shots per turn: " + " ".join(
            f"{t}:{per[t]}" for t in sorted(per)))


if __name__ == "__main__":
    main()
