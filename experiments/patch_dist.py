#!/usr/bin/env python3
"""Stop refusing build orders more than ~8 tiles away.

`dist = 63` seeds the best-so-far and is compared against distance_squared, so
it silently caps ticket assignment at sqrt(63) ~= 7.9 tiles. 63 is the sentinel
the conveyor-distance grid uses (a real distance), not a squared one.

On its own this LOWERS win rate (measured 50.0%) because it pulls builders off
attacking. It is only here as part of raising harvester throughput.
"""
import sys
p = sys.argv[1] + "/main.py"
s = open(p, newline="").read().replace("\r\n", "\n")
old = """                dist = 63
                best_ticket = None"""
new = """                dist = float('inf')  # squared distance -- 63 capped this at ~8 tiles
                best_ticket = None"""
assert s.count(old) == 1, "dist anchor"
open(p, "w", newline="").write(s.replace(old, new, 1))
print(f"patched {p}")
