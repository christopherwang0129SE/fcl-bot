#!/usr/bin/env python3
"""Stop Map.configure() from crashing a builder off the edge of the map.

configure() stamps a 2x2 core footprint at core_pos + (0..1). Builders call it
with their OWN spawn position rather than the core's, so a builder that spawns
against the right or bottom edge indexes past the end of the grid and raises
IndexError. An uncaught exception permanently destroys that unit for the rest
of the match, so we play the game a builder down.

Found by running the live bot against the do-nothing opponent on all 46 maps
with the time limit on: `bridge` raises on both seeds. A mirror A/B cannot see
this -- both sides lose a builder and it cancels out -- which is why 3,800
games never surfaced it.

  python3 patch_mapguard.py <botdir>
"""
import sys

p = sys.argv[1] + "/mapclass.py"
raw = open(p, newline="").read()
nl = "\r\n" if "\r\n" in raw else "\n"
s = raw.replace("\r\n", "\n")

old = """        for dx in 0,1:
            for dy in 0,1:
                self.own_core.append(Position(core_pos.x + dx, core_pos.y + dy))
                self.entity_grid[core_pos.y + dy][core_pos.x + dx] = 16
                self.buildplan_grid[core_pos.y + dy][core_pos.x + dx] = 16"""
new = """        for dx in 0,1:
            for dy in 0,1:
                x, y = core_pos.x + dx, core_pos.y + dy
                # Builders pass their own spawn tile here, not the core's, so
                # this runs off the grid for anything spawned on the last row
                # or column -- and an uncaught IndexError would destroy that
                # unit permanently.
                if not (0 <= x < width and 0 <= y < height):
                    continue
                self.own_core.append(Position(x, y))
                self.entity_grid[y][x] = 16
                self.buildplan_grid[y][x] = 16"""
assert s.count(old) == 1, "configure anchor"
s = s.replace(old, new, 1)
open(p, "w", newline="").write(s.replace("\n", nl))
print("patched " + sys.argv[1])
