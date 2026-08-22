#!/usr/bin/env python3
"""Aggregate BUILD lines from patch_probe over many games -> gate-1 numbers.

Runs a probed bot against experiments/idle (and optionally against a real
opponent) on the map pool and reports, per game and averaged: harvesters built
by a cutoff turn, belts laid, and belts per harvester.

  python3 probe_stats.py <botdir> [--opp DIR] [--seeds N] [--by 80] [--maps a,b]
"""
import argparse, collections, os, subprocess, tempfile
from concurrent.futures import ThreadPoolExecutor

ROOT = "/var/home/student/Florent/fcl-bot"
FCODE = "/var/home/student/.venvs/fcode/bin/fcode"
POOL = ["antler", "archipelago", "auroraveil", "drakkarfjord", "drumlin",
        "fjordgate", "frostgate", "glacierkeep", "icefloe", "midgard",
        "nordkap", "ragnarok", "royale", "valkyrie", "yulerune"]


def run_one(args):
    bot, opp, mapname, seed, by = args
    fd, replay = tempfile.mkstemp(suffix=".replay26")
    os.close(fd)
    try:
        p = subprocess.run(
            [FCODE, "run", bot, opp, f"maps/{mapname}.map26", "--tle", "0",
             "--seed", str(seed), "--replay", replay, "--json"],
            cwd=ROOT, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        return mapname, seed, None
    finally:
        if os.path.exists(replay):
            os.remove(replay)

    counts = collections.Counter()
    try:
        import json
        j = json.loads(p.stdout.strip().split("\n")[-1])
        counts["ti"] = j.get("a_titanium_collected", 0)
        counts["turns"] = j.get("turns", 0)
        counts["won"] = 1 if j.get("winner") == "A" else 0
    except Exception:
        pass
    last_round = 0
    for line in p.stderr.split("\n"):
        if not line.startswith("BUILD "):
            continue
        _, team, rnd, kind = line.split()
        if team != "Team.A":          # the bot under test is always side A here
            continue
        rnd = int(rnd)
        last_round = max(last_round, rnd)
        if rnd <= by:
            counts[kind] += 1
        counts[kind + "_all"] += 1
    return mapname, seed, counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bot")
    ap.add_argument("--opp", default="experiments/idle")
    ap.add_argument("--seeds", type=int, default=2)
    ap.add_argument("--seed-start", type=int, default=1)
    ap.add_argument("--by", type=int, default=80)
    ap.add_argument("--maps", default=None)
    ap.add_argument("--jobs", type=int, default=8)
    a = ap.parse_args()

    maps = a.maps.split(",") if a.maps else POOL
    jobs = [(a.bot, a.opp, m, s, a.by)
            for m in maps for s in range(a.seed_start, a.seed_start + a.seeds)]
    with ThreadPoolExecutor(max_workers=a.jobs) as ex:
        results = list(ex.map(run_one, jobs))

    print(f"{a.bot} vs {a.opp}   (harvesters/belts by turn {a.by})")
    print(f"  {'map':14s} {'harv':>5s} {'belt':>5s} {'b/h':>5s} {'ti':>7s} {'turns':>6s}")
    th = tb = tt = tu = 0
    per = collections.defaultdict(lambda: [0, 0, 0, 0])
    for m, s, c in results:
        if c is None:
            print(f"  {m:14s}  TIMEOUT"); continue
        h, b = c["harvester"], c["conveyor"]
        per[m][0] += h; per[m][1] += b; per[m][2] += c["ti"]; per[m][3] += c["turns"]
        th += h; tb += b; tt += c["ti"]; tu += c["turns"]
    for m in sorted(per):
        h, b, ti, tn = per[m]
        k = a.seeds
        print(f"  {m:14s} {h/k:5.1f} {b/k:5.1f} {(b/h if h else 0):5.2f} {ti/k:7.0f} {tn/k:6.0f}")
    games = sum(1 for _, _, c in results if c is not None)
    g = max(games, 1)
    print(f"  TOTAL games={games}  harv/game={th/g:.1f}  belts/game={tb/g:.1f}  "
          f"belts-per-harv={(tb/th if th else 0):.2f}  ti/game={tt/g:.0f}  turns={tu/g:.0f}")


if __name__ == "__main__":
    main()
