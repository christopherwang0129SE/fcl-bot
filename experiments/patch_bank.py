#!/usr/bin/env python3
"""Stop spending in the endgame, because the last tiebreak is titanium STORED.

On ragnarok all six turtle games reach round 1000 with titanium collected exactly
tied (4,980 each) and harvesters presumably tied too, so the match falls through to
the third tiebreak: titanium stored. We lose it 5 of 6 times because the turtle is
still buying barriers with the bank that decides the game.

After ENDGAME_ROUND, hold the money. Healing stays allowed -- being alive is a
precondition for winning any tiebreak -- but nothing else gets bought.
"""
import sys
p = sys.argv[1] + "/main.py"
s = open(p, newline="").read().replace("\r\n", "\n")

s = s.replace("FORTIFY_RESERVE = 60",
              "FORTIFY_RESERVE = 60\n"
              "# Round after which titanium is worth more banked than spent: the final\n"
              "# tiebreak is decided on titanium stored.\n"
              "ENDGAME_ROUND = 900", 1)

old = "        if enemy is not None and ct.get_global_resources() > FORTIFY_RESERVE + ct.get_barrier_cost():"
new = ("        if (enemy is not None and ct.get_current_round() < ENDGAME_ROUND\n"
       "                and ct.get_global_resources() > FORTIFY_RESERVE + ct.get_barrier_cost()):")
assert s.count(old) == 1, "fortify anchor"
s = s.replace(old, new, 1)
open(p, "w", newline="").write(s)
print(f"patched {p}")
