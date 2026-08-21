#!/usr/bin/env python3
"""Stop building sentinels we cannot feed.

Measured: sentinels get a live target and cannot fire ~65% of the time, and the
dominant blocker is an empty ammo pool. The arithmetic says that is structural,
not a buffer-tuning problem -- 7 sentinels firing on their 3-round reload demand
~23 ammo/turn, and passive income is 2.5 Ti/turn plus 2.5 per harvester. We
would need ~9 harvesters purely to feed the turrets. We field 2-5.

So the turrets are not ammo-starved because the buffer is small; they are
starved because we built more than the economy can ever supply. Every surplus
sentinel also adds +20% to the cost of everything else.

Expected shots are roughly unchanged (7 x 35% = 2.45 vs 3 x 80% = 2.40) at less
than half the scale cost. Cap per builder, since a builder has no view of the
team-wide sentinel count and every store slot is already spoken for.
"""
import sys
n = int(sys.argv[2])
p = sys.argv[1] + "/main.py"
s = open(p, newline="").read().replace("\r\n", "\n")

s = s.replace("SLOT_GAME_DATA = 0",
              f"SLOT_GAME_DATA = 0\n\n"
              f"# Sentinels each cost +20% on all future builds and 10 ammo per shot.\n"
              f"# Build only as many as the ammo economy can actually keep firing.\n"
              f"MAX_SENTINELS_PER_BUILDER = {n}", 1)

s = s.replace("        self.own_core_tiles = []",
              "        self.own_core_tiles = []\n        self.sentinels_built = 0", 1)

old = """            for tile in adjacent_tiles(pos):
                if ct.can_build_sentinel(tile, Direction.NORTH):
                    orientation = sentinel_could_hit_opp_core_from(tile, self.opp_core_tiles, ct)
                    if orientation:
                        ct.build_sentinel(tile, orientation)
                        return"""
new = """            if self.sentinels_built < MAX_SENTINELS_PER_BUILDER:
                for tile in adjacent_tiles(pos):
                    if ct.can_build_sentinel(tile, Direction.NORTH):
                        orientation = sentinel_could_hit_opp_core_from(tile, self.opp_core_tiles, ct)
                        if orientation:
                            ct.build_sentinel(tile, orientation)
                            self.sentinels_built += 1
                            return"""
assert s.count(old) == 1, "sentinel build anchor"
s = s.replace(old, new, 1)
open(p, "w", newline="").write(s)
print(f"patched {p} -> cap {n}/builder")
