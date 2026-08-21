#!/usr/bin/env python3
"""Idle turtle builders prospect for ore instead of standing guard.

With the turtle, games now reach round 1000 -- but base still out-mines it
(12,280 vs 9,880 on midgard), because base's roaming attackers double as
scouts. The core can only plan harvesters on ore somebody has reported, so
sitting at home caps the economy that the whole tiebreak plan depends on.

So while nothing is attacking, walk the map looking for unseen ground; the
moment an enemy shows up, fall back to fortifying. Apply after patch_turtle.
"""
import sys
p = sys.argv[1] + "/main.py"
s = open(p, newline="").read().replace("\r\n", "\n")

s = s.replace("FORTIFY_RESERVE = 60",
              "FORTIFY_RESERVE = 60\n"
              "# How far out an idle builder will look for unscouted ground.\n"
              "FRONTIER_SEARCH_RADIUS = 16", 1)

helper = '''    def _nearest_frontier(self, ct: Controller):
        """Closest tile we have never seen, searched in expanding rings."""
        if self.local_map is None:
            return None
        pos = ct.get_position()
        w, h = self.local_map.width, self.local_map.height
        for r in range(2, FRONTIER_SEARCH_RADIUS + 1):
            for dx in range(-r, r + 1):
                for dy in ((-r, r) if abs(dx) != r else range(-r, r + 1)):
                    x, y = pos.x + dx, pos.y + dy
                    if 0 <= x < w and 0 <= y < h and self.local_map.environment_grid[y][x] == 0:
                        return Position(x, y)
        return None

    def _nearest_enemy(self, ct: Controller):'''
old_helper = "    def _nearest_enemy(self, ct: Controller):"
assert s.count(old_helper) == 1
s = s.replace(old_helper, helper, 1)

# Replace the idle tail (heal-only) with prospecting.
old = """        for tile in adjacent_tiles(pos):
            if ct.can_heal(tile):
                ct.heal(tile)
                return
"""
new = """        for tile in adjacent_tiles(pos):
            if ct.can_heal(tile):
                ct.heal(tile)
                return

        # Nothing to fight or fix: go find ore. The core can only plan
        # harvesters on ore that somebody has actually reported.
        target = self._nearest_frontier(ct)
        if target is not None:
            self._bot_pathfind(target, ct)
            return
        for d in CARDINALS:
            if ct.can_move(d):
                ct.move(d)
                self.moved_direction = d
                return
"""
assert s.count(old) == 1, "idle tail anchor"
s = s.replace(old, new, 1)
open(p, "w", newline="").write(s)
print(f"patched {p}")
