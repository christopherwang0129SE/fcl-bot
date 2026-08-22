#!/usr/bin/env python3
"""A/B test scouter2-patched vs scouter2 across the competition map pool.

Run: python3 test_patched.py
"""
import argparse, json, os, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path.cwd()
FCODE = "fcode"  # Use system fcode
POOL = ["antler", "archipelago", "auroraveil", "drakkarfjord", "drumlin",
        "fjordgate", "frostgate", "glacierkeep", "icefloe", "midgard",
        "nordkap", "ragnarok", "royale", "valkyrie", "yulerune"]


def run_one(args):
    bot_a, bot_b, mapname, seed, tle = args
    fd, replay = tempfile.mkstemp(suffix=".replay26")
    os.close(fd)
    try:
        p = subprocess.run(
            [FCODE, "run", bot_a, bot_b, f"maps/{mapname}.map26",
             "--tle", str(tle), "--seed", str(seed), "--replay", replay, "--json"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=300)
        line = p.stdout.strip().split("\n")[-1] if p.stdout.strip() else ""
        try:
            return mapname, seed, json.loads(line)
        except json.JSONDecodeError:
            return mapname, seed, {"error": (line or p.stderr)[-300:]}
    except subprocess.TimeoutExpired:
        return mapname, seed, {"error": "TIMEOUT"}
    finally:
        if os.path.exists(replay):
            os.remove(replay)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bot-x", default="bots/scouter2-patched")
    ap.add_argument("--bot-y", default="bots/scouter2")
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--seed-start", type=int, default=1)
    ap.add_argument("--maps", default=None)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--tle", type=int, default=0)
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    maps = a.maps.split(",") if a.maps else POOL
    jobs = []
    for m in maps:
        for s in range(a.seed_start, a.seed_start + a.seeds):
            jobs.append((a.bot_x, a.bot_y, m, s, a.tle))
            jobs.append((a.bot_y, a.bot_x, m, s, a.tle))

    print(f"Running {len(jobs)} matches ({len(maps)} maps × {a.seeds} seeds × 2 sides)")
    print(f"  Bot X: {a.bot_x}")
    print(f"  Bot Y: {a.bot_y}\n")

    with ThreadPoolExecutor(max_workers=a.jobs) as ex:
        results = list(ex.map(run_one, jobs))

    xw = yw = dr = err = 0
    per = {}
    for job, (m, s, r) in zip(jobs, results):
        x_is_a = job[0] == a.bot_x
        if "error" in r:
            err += 1
            if not a.quiet:
                print(f"  ERROR {m} seed={s}: {r['error']}", file=sys.stderr)
            continue
        w = r.get("winner")
        pm = per.setdefault(m, [0, 0])
        if (w == "A") == x_is_a and w in ("A", "B"):
            xw += 1; pm[0] += 1
        elif w in ("A", "B"):
            yw += 1; pm[1] += 1
        else:
            dr += 1
    tot = xw + yw + dr
    print(f"\n{os.path.basename(a.bot_x)}  vs  {os.path.basename(a.bot_y)}")
    print(f"  games: {tot}  (errors: {err})")
    if tot:
        winrate = 100.0*xw/tot
        print(f"  X {xw}  Y {yw}  draws {dr}   -> X winrate {winrate:.1f}%")
    if not a.quiet:
        print(f"\n  Per-map breakdown:")
        for m in sorted(per):
            print(f"    {m:14s} {per[m][0]}-{per[m][1]}")


if __name__ == "__main__":
    main()
