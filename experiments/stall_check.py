#!/usr/bin/env python3
"""How long does this bot take to beat a fixed opponent, aggregated.

`map_audit.py` runs two seeds per map, which is enough to spot a map that is
categorically broken but nowhere near enough to compare two variants: the bot
calls `random` unseeded, so the same map and seed gave 59 and 1000 turns on
consecutive runs. This plays N games per map and reports the distribution, so
"this patch fixed the stall" is a claim about a median rather than a coin flip.

A game that reaches round 1000 never found the enemy core at all.

Defaults to the do-nothing opponent; pass --opp to use one of the adversarial
test bots (`experiments/hunter` shoots builder bots, `experiments/waller` rings
its core in barriers) to probe a failure mode a mirror cannot produce.

  python3 stall_check.py <botdir> <n> [--opp DIR] <map> [map...]
"""
import json, os, statistics, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor

ROOT = "/var/home/student/Florent/fcl-bot"
FCODE = "/var/home/student/.venvs/fcode/bin/fcode"
BOT, N, rest = sys.argv[1], int(sys.argv[2]), sys.argv[3:]
OPP = "experiments/idle"
if "--opp" in rest:
    i = rest.index("--opp")
    OPP = rest[i + 1]
    rest = rest[:i] + rest[i + 2:]
MAPS = rest


def run(job):
    mapname, seed = job
    fd, replay = tempfile.mkstemp(suffix=".replay26"); os.close(fd)
    try:
        p = subprocess.run([FCODE, "run", BOT, OPP,
                            f"maps/{mapname}.map26", "--seed", str(seed),
                            "--tle", "0", "--replay", replay, "--json"],
                           cwd=ROOT, capture_output=True, text=True, timeout=900)
        try:
            return mapname, json.loads(p.stdout.strip().split("\n")[-1])
        except Exception:
            return mapname, {"turns": -1, "winner": "?"}
    finally:
        if os.path.exists(replay):
            os.remove(replay)


jobs = [(m, s) for m in MAPS for s in range(1, N + 1)]
rows = {}
with ThreadPoolExecutor(max_workers=12) as ex:
    for mapname, j in ex.map(run, jobs):
        rows.setdefault(mapname, []).append(j)

print(f"{BOT}  ({N} games/map vs {OPP})\n")
print(f"  {'map':14s} {'won':>6s} {'median':>7s} {'mean':>7s} {'units':>6s} {'stalls':>7s}")
tw = tg = 0
for m in MAPS:
    js = rows.get(m, [])
    turns = [j.get("turns", -1) for j in js]
    won = sum(1 for j in js if j.get("winner") == "A")
    units = statistics.mean([j.get("a_units", 0) for j in js])
    stalls = sum(1 for t in turns if t >= 1000)
    tw += won; tg += len(js)
    print(f"  {m:14s} {won:2d}/{len(js):<3d} {statistics.median(turns):7.0f} "
          f"{statistics.mean(turns):7.0f} {units:6.1f} {stalls:4d}/{len(js):<2d}")
print(f"\n  TOTAL {tw}/{tg} = {100.0*tw/max(tg,1):.1f}%")
