#!/usr/bin/env python3
"""Aggregate our REAL ladder games by map, win condition and game length.

Every tuning decision so far came from mirror A/Bs on a 15-map pool. The ladder
draws from a much larger map set and pairs us against real bots, so this asks
the questions the mirror cannot: which maps do we actually lose on, and do we
lose by being rushed, by being out-mined, or by running out of clock?

Read-only -- lists completed matches and their per-game results. Touches no
submission and plays no games.
"""
import collections, json, subprocess, sys

FCODE = "/var/home/student/.venvs/fcode/bin/fcode"
US = "dc7cfe89-627d-44fd-849c-44bc8bfcae40"


def cli(*args):
    out = subprocess.run([FCODE, *args, "--json"], capture_output=True, text=True).stdout
    return json.loads(out.strip().split("\n")[-1])


limit = sys.argv[1] if len(sys.argv) > 1 else "60"
matches = cli("match", "list", "--mine", "--limit", limit)["matches"]
per_map = collections.defaultdict(lambda: [0, 0])
cond = collections.Counter()
turns = {"win": [], "loss": []}
opps = collections.defaultdict(lambda: [0, 0])
n = 0

for m in matches:
    if m.get("status") != "complete":
        continue
    info = cli("match", "info", m["id"])
    opp = m["teamBName"] if m["teamAId"] == US else m["teamAName"]
    for g in info.get("games", []):
        won = g.get("winnerId") == US
        n += 1
        per_map[g["mapName"]][0 if won else 1] += 1
        opps[opp][0 if won else 1] += 1
        turns["win" if won else "loss"].append(g.get("turnsPlayed") or 0)
        cond[("W " if won else "L ") + str(g.get("winCondition"))] += 1

print(f"{n} ladder games from {len(matches)} matches\n")
print("BY MAP (win-loss, sorted worst first)")
for mp, (w, l) in sorted(per_map.items(), key=lambda kv: (kv[1][0] / max(kv[1][0] + kv[1][1], 1), -kv[1][1])):
    bar = "#" * w + "." * l
    print(f"  {mp:16s} {w:2d}-{l:<2d} {100*w/max(w+l,1):5.1f}%  {bar}")

print("\nWIN CONDITIONS")
for k, v in cond.most_common():
    print(f"  {k:34s} {v}")

BANDS = [(0, 60, "rushed  <60"), (60, 100, "60-99"), (100, 200, "100-199"),
         (200, 500, "200-499"), (500, 1001, "500+ / tiebreak")]
for k in ("win", "loss"):
    t = sorted(turns[k])
    if not t:
        continue
    print(f"\nturns when we {k}: n={len(t)} median={t[len(t)//2]} "
          f"min={t[0]} max={t[-1]}")
    # How we lose matters more than the median: a bot that dies at turn 50 has a
    # different problem from one that is still alive at turn 500 and grinding.
    for lo, hi, label in BANDS:
        c = sum(1 for x in t if lo <= x < hi)
        print(f"    {label:16s} {c:3d}  {100*c/len(t):5.1f}%  {'#' * (c * 40 // len(t))}")

print("\nBY OPPONENT")
for o, (w, l) in sorted(opps.items(), key=lambda kv: kv[1][0] / max(kv[1][0] + kv[1][1], 1)):
    print(f"  {o[:26]:26s} {w:2d}-{l:<2d} {100*w/max(w+l,1):5.1f}%")
