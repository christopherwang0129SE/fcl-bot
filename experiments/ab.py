#!/usr/bin/env python3
"""A/B two bot directories over the competition map pool.

Plays every (map, seed) pair twice with sides swapped so side bias cancels.
Run with --tle 0 so results don't depend on machine load. >=150 games before
believing anything (see MEMORY: 90 games read 54.4% where 150 read 50.7%).
"""
import argparse, json, os, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor

ROOT = "/var/home/student/Florent/fcl-bot"
FCODE = "/var/home/student/.venvs/fcode/bin/fcode"
POOL = ["antler", "archipelago", "auroraveil", "drakkarfjord", "drumlin",
        "fjordgate", "frostgate", "glacierkeep", "icefloe", "midgard",
        "nordkap", "ragnarok", "royale", "valkyrie", "yulerune"]


def run_one(args):
    bot_a, bot_b, mapname, seed, tle = args
    fd, replay = tempfile.mkstemp(suffix=".replay26")   # parallel runs must not share
    os.close(fd)
    try:
        p = subprocess.run(
            [FCODE, "run", bot_a, bot_b, f"maps/{mapname}.map26",
             "--tle", str(tle), "--seed", str(seed), "--replay", replay, "--json"],
            cwd=ROOT, capture_output=True, text=True, timeout=300)
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
    ap.add_argument("bot_x"); ap.add_argument("bot_y")
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--seed-start", type=int, default=1,
                    help="first seed; use a fresh range to replicate a result")
    ap.add_argument("--maps", default=None)
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--tle", type=int, default=0)
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    maps = a.maps.split(",") if a.maps else POOL
    jobs = []
    for m in maps:
        for s in range(a.seed_start, a.seed_start + a.seeds):
            jobs.append((a.bot_x, a.bot_y, m, s, a.tle))
            jobs.append((a.bot_y, a.bot_x, m, s, a.tle))
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
        print(f"  X {xw}  Y {yw}  draws {dr}   -> X winrate {100.0*xw/tot:.1f}%")
    if not a.quiet:
        for m in sorted(per):
            print(f"    {m:14s} {per[m][0]}-{per[m][1]}")


if __name__ == "__main__":
    main()
