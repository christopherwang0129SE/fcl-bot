#!/usr/bin/env python3
"""Profile what a team actually builds, and when, from ladder replays.

`fcode match list --team <id>` works for any team, and `match replay` downloads
their games, so the top of the ladder is fully observable. This turns a replay
into the numbers that matter for copying a build: unit composition, the turn
each kind first appears, and how far forward it is placed.

Kind comes from max HP. The 40-HP pair (builder bot / sentinel) is split by
whether the entity ever moves; a builder that dies before moving reads as a
sentinel, which is rare enough not to matter at this resolution.

  python3 profile_bot.py <replay...> [--team N]
"""
import sys, collections, statistics

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from replay_read import load, kind_of

KINDS = ["core", "builder", "SENTINEL", "gunner", "harvester/barrier", "conveyor"]


def profile(path, want=None):
    w, h, ents, moved, log, core_ids = load(path)
    cores = {ents[i]["team"]: ents[i]["pos"] for i in core_ids}
    end = max((t for t, _, _ in log), default=0)
    dead = {e["id"] for _, k, e in log if k == "DEATH"}
    loser = next((e.get("team") for _, k, e in log
                  if k == "DEATH" and e.get("maxhp") == 500), None)

    out = {}
    for team in (0, 1):
        if want is not None and team != want:
            continue
        built = [e for t, k, e in log if k == "SPAWN" and e["team"] == team]
        counts = collections.Counter(kind_of(e, moved) for e in built)
        first = {}
        fwd = collections.defaultdict(list)
        opp = cores.get(1 - team)
        own = cores.get(team)
        for t, k, e in log:
            if k != "SPAWN" or e["team"] != team:
                continue
            kd = kind_of(e, moved)
            first.setdefault(kd, t)
            if opp and own:
                d_opp = abs(e["pos"][0]-opp[0]) + abs(e["pos"][1]-opp[1])
                d_own = abs(e["pos"][0]-own[0]) + abs(e["pos"][1]-own[1])
                fwd[kd].append((d_own, d_opp))
        out[team] = {"counts": counts, "first": first, "fwd": fwd,
                     "won": loser is not None and loser != team, "end": end,
                     "map": f"{w}x{h}",
                     "sep": (abs(cores[0][0]-cores[1][0]) + abs(cores[0][1]-cores[1][1]))
                            if 0 in cores and 1 in cores else None}
    return out


def main():
    paths = [a for a in sys.argv[1:] if not a.startswith("--")]
    want = None
    if "--team" in sys.argv:
        want = int(sys.argv[sys.argv.index("--team") + 1])

    agg = collections.defaultdict(lambda: collections.defaultdict(list))
    for p in paths:
        pr = profile(p, want)
        for team, d in pr.items():
            tag = f"team{team}{' WON' if d['won'] else ' lost'}"
            print(f"\n=== {p.rsplit('/',1)[-1]}  map {d['map']}  cores {d['sep']} apart  "
                  f"{d['end']} turns  [{tag}]")
            for kd in KINDS:
                n = d["counts"].get(kd, 0)
                if not n:
                    continue
                ft = d["first"].get(kd)
                f = d["fwd"].get(kd, [])
                med_own = statistics.median([a for a, _ in f]) if f else 0
                print(f"   {kd:<18} n={n:<3} first turn {ft:<4} "
                      f"median {med_own:.0f} tiles from own core")
                agg[kd]["n"].append(n)
                if ft is not None:
                    agg[kd]["first"].append(ft)
                agg[kd]["fwd"] += [a for a, _ in f]

    if len(paths) > 1:
        print(f"\n=== AGGREGATE over {len(paths)} games")
        for kd in KINDS:
            if kd not in agg:
                continue
            a = agg[kd]
            print(f"   {kd:<18} median count {statistics.median(a['n']):.0f}   "
                  f"median first turn {statistics.median(a['first']) if a['first'] else float('nan'):.0f}   "
                  f"median dist from own core {statistics.median(a['fwd']) if a['fwd'] else float('nan'):.0f}")


if __name__ == "__main__":
    main()
