#!/usr/bin/env python3
"""How fast does this bot get a sentinel shooting at the enemy core?

Replay forensics on three real ladder losses (Jacobs Code, 23 Aug) showed all
three were decided by the same thing: the opponent had a sentinel firing at our
core by turn 8-12, and we did not answer until turn 30+. They build almost no
economy; we build seven conveyors and three harvesters first.

A mirror A/B is structurally blind to this -- both copies are equally slow, so
the tempo difference cancels to ~50%. This measures it directly.

Reports, per map, the turn of our first sentinel and of its first shot that
lands on the enemy core.

  python3 tempo.py <botdir> [--opp DIR] [--seeds N] <map> [map...]
"""
import os, statistics, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from replay_read import load, kind_of

ROOT = "/var/home/student/Florent/fcl-bot"
FCODE = "/var/home/student/.venvs/fcode/bin/fcode"

args = sys.argv[1:]
BOT = args.pop(0)
OPP = "experiments/idle"
SEEDS = 3
if "--opp" in args:
    i = args.index("--opp"); OPP = args[i + 1]; del args[i:i + 2]
if "--seeds" in args:
    i = args.index("--seeds"); SEEDS = int(args[i + 1]); del args[i:i + 2]
MAPS = args


def one(job):
    mapname, seed = job
    fd, rp = tempfile.mkstemp(suffix=".replay26"); os.close(fd)
    try:
        subprocess.run([FCODE, "run", BOT, OPP, f"maps/{mapname}.map26",
                        "--seed", str(seed), "--tle", "0", "--replay", rp, "--json"],
                       cwd=ROOT, capture_output=True, text=True, timeout=900)
        w, h, ents, moved, log, core_ids = load(rp)
        cores = {ents[i]["team"]: ents[i]["pos"] for i in core_ids}
        us, them = 0, 1
        sent = [t for t, k, e in log
                if k == "SPAWN" and e["team"] == us and kind_of(e, moved) == "SENTINEL"]
        tgt = cores.get(them, (0, 0))
        shots = [t for t, k, v in log if k == "FIRE"
                 and abs(v[1][0] - tgt[0]) <= 2 and abs(v[1][1] - tgt[1]) <= 2]
        died = [t for t, k, e in log if k == "DEATH" and e.get("maxhp") == 500]
        return mapname, (min(sent) if sent else None), (min(shots) if shots else None), \
               (min(died) if died else None)
    except Exception as e:
        return mapname, None, None, None
    finally:
        if os.path.exists(rp):
            os.remove(rp)


jobs = [(m, s) for m in MAPS for s in range(1, SEEDS + 1)]
with ThreadPoolExecutor(max_workers=8) as ex:
    res = list(ex.map(one, jobs))

print(f"{BOT}  vs {OPP}   ({SEEDS} seeds/map)\n")
print(f"{'map':<15}{'1st sentinel':>13}{'1st shot on core':>18}{'game ends':>11}")
allsent, allshot = [], []
for m in MAPS:
    rows = [r for r in res if r[0] == m]
    s = [r[1] for r in rows if r[1] is not None]
    f = [r[2] for r in rows if r[2] is not None]
    d = [r[3] for r in rows if r[3] is not None]
    allsent += s; allshot += f
    fmt = lambda v: f"{statistics.median(v):.0f}" if v else "never"
    print(f"{m:<15}{fmt(s):>13}{fmt(f):>18}{fmt(d):>11}")
if allsent:
    print(f"\nmedian first sentinel {statistics.median(allsent):.0f}   "
          f"median first shot on core {statistics.median(allshot) if allshot else float('nan'):.0f}")
