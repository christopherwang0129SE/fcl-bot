#!/usr/bin/env python3
"""Find maps where the bot is objectively broken, using the do-nothing opponent.

Why this and not another A/B: a mirror A/B scores ~50% on *every* map by
construction, so it is structurally incapable of revealing a map where our bot
is simply bad. The real ladder says we are 0-13 on longhouse, 0-10 on jotunheim
and 1-15 on valkyrie -- and two of those maps are not even in the 15-map A/B
pool. Against an opponent that does nothing, any map we cannot win quickly and
cheaply is a defect, and fixing it is a real gain the mirror cannot see.

Also greps the engine output for tracebacks and time-limit messages, with the
TLE left ON, which every previous A/B disabled.

  python3 map_audit.py [botdir] [oppdir] [nseeds]
"""
import json, os, re, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor

ROOT = "/var/home/student/Florent/fcl-bot"
FCODE = "/var/home/student/.venvs/fcode/bin/fcode"
BOT = sys.argv[1] if len(sys.argv) > 1 else "bots/scouter2"
OPP = sys.argv[2] if len(sys.argv) > 2 else "experiments/idle"
SEEDS = tuple(range(1, int(sys.argv[3]) + 1)) if len(sys.argv) > 3 else (1, 2)
MAPS = sorted(f[:-6] for f in os.listdir(ROOT + "/maps") if f.endswith(".map26"))
BAD = re.compile(r"Traceback|exceeded|time limit|destroyed permanently", re.I)


def run(job):
    mapname, seed = job
    fd, replay = tempfile.mkstemp(suffix=".replay26"); os.close(fd)
    try:
        p = subprocess.run([FCODE, "run", BOT, OPP, f"maps/{mapname}.map26",
                            "--seed", str(seed), "--replay", replay, "--json"],
                           cwd=ROOT, capture_output=True, text=True, timeout=900)
        try:
            j = json.loads(p.stdout.strip().split("\n")[-1])
        except Exception:
            j = {"error": (p.stdout or p.stderr)[-200:]}
        bad = [l.strip()[:120] for l in (p.stdout + p.stderr).split("\n") if BAD.search(l)]
        return mapname, seed, j, bad
    except subprocess.TimeoutExpired:
        return mapname, seed, {"error": "HARNESS_TIMEOUT"}, []
    finally:
        if os.path.exists(replay):
            os.remove(replay)


jobs = [(m, s) for m in MAPS for s in SEEDS]
rows = {}
problems = []
with ThreadPoolExecutor(max_workers=10) as ex:
    for mapname, seed, j, bad in ex.map(run, jobs):
        rows.setdefault(mapname, []).append((seed, j))
        for b in bad:
            problems.append(f"{mapname}/s{seed}: {b}")

print(f"{BOT} vs {OPP} -- TLE ON, {len(MAPS)} maps x {len(SEEDS)} seeds\n")
print(f"  {'map':16s} {'won':>4s} {'turns':>6s} {'ti':>7s} {'blds':>5s}   verdict")
broken = []
for m in MAPS:
    ws, ts, tis, bs = [], [], [], []
    for seed, j in rows.get(m, []):
        if "error" in j:
            ws.append(0); ts.append(-1); tis.append(-1); bs.append(-1); continue
        ws.append(1 if j.get("winner") == "A" else 0)
        ts.append(j.get("turns", 0)); tis.append(j.get("a_titanium_collected", 0))
        bs.append(j.get("a_buildings", 0))
    if not ts:
        continue
    won, turns, ti = sum(ws), sum(ts) / len(ts), sum(tis) / len(tis)
    flags = []
    if won < len(ws):   flags.append("LOSES/DRAWS vs idle")
    if turns > 250:     flags.append("very slow kill")
    if ti <= 0:         flags.append("mines NOTHING")
    if flags:
        broken.append(m)
    print(f"  {m:16s} {won}/{len(ws):<2d} {turns:6.0f} {ti:7.0f} {sum(bs)/len(bs):5.0f}   "
          + ", ".join(flags))

print(f"\n{len(broken)} maps flagged: {', '.join(broken)}")
if problems:
    print(f"\n{len(problems)} crash/TLE lines:")
    for p in problems[:20]:
        print("  " + p)
else:
    print("\nno tracebacks or time-limit messages")
