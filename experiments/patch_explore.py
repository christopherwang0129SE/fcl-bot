#!/usr/bin/env python3
"""Systematic exploration instead of a corner-rush and a random walk.

README idea: "Map exploration strategy (systematic vs random)".

Today an order-less builder walks to the geometric opposite corner while the
enemy core is unknown, and otherwise steps in a random legal direction. Both
re-cover ground we have already seen. The core can only plan harvesters on ore
that somebody has actually reported, so slow scouting directly caps harvester
count -- which is the measured bottleneck.

Every builder already maintains `self.local_map`, where unscouted tiles are 0.
Walk to the nearest such tile instead. Deliberately narrow: this replaces only
the corner-rush and the random fallback. The sentinel/staging attack behaviour
is untouched, because that is where this bot's wins currently come from and
every change that traded attack for economy has lost.
"""
import sys

path = sys.argv[1] + "/main.py"
s = open(path, newline="").read().replace("\r\n", "\n")

s = s.replace("SLOT_GAME_DATA = 0",
              "SLOT_GAME_DATA = 0\n\n"
              "# How far out a builder will look for unscouted ground (chebyshev rings).\n"
              "FRONTIER_SEARCH_RADIUS = 14", 1)

# --- nearest-unscouted search on the builder's own map ---------------------
helper = '''    def _nearest_frontier(self, ct: Controller) -> Position | None:
        """Closest tile we have never seen, searched in expanding rings.

        mapclass.get_unscouted_near only sweeps a triangular slice, so do it
        properly here: ring by ring outward, first hit wins, capped so this
        stays cheap enough for the per-turn budget.
        """
        if self.local_map is None:
            return None
        pos = ct.get_position()
        w, h = self.local_map.width, self.local_map.height
        for r in range(2, FRONTIER_SEARCH_RADIUS + 1):
            for dx in range(-r, r + 1):
                for dy in (-r, r) if abs(dx) != r else range(-r, r + 1):
                    x, y = pos.x + dx, pos.y + dy
                    if not (0 <= x < w and 0 <= y < h):
                        continue
                    if self.local_map.environment_grid[y][x] == 0:
                        return Position(x, y)
        return None

    def _explore(self, ct: Controller) -> bool:
        """Head for unscouted ground. True if this consumed the turn."""
        target = self._nearest_frontier(ct)
        if target is None:
            return False
        self._bot_pathfind(target, ct)
        return self.moved_direction is not None

    def _bot_without_orders(self, ct: Controller) -> None:'''
old_def = "    def _bot_without_orders(self, ct: Controller) -> None:"
assert s.count(old_def) == 1
s = s.replace(old_def, helper, 1)

# --- replace the opposite-corner rush --------------------------------------
old_corner = """        if self.opp_core_bottom_right is None:
            self._push_to_opposite_corner(ct)"""
new_corner = """        if self.opp_core_bottom_right is None:
            # Sweep unseen ground rather than beelining for the far corner --
            # finding ore early is what the core is starved of.
            if not self._explore(ct):
                self._push_to_opposite_corner(ct)"""
assert old_corner in s, "corner anchor"
s = s.replace(old_corner, new_corner, 1)

# --- replace the random-walk fallback --------------------------------------
old_rand = """        open_dirs = [
            d for d in CARDINALS
            if ct.can_move(d) and ct.get_tile_env(pos.add(d)) == Environment.EMPTY
        ]
        move_options = open_dirs or [d for d in CARDINALS if ct.can_move(d)]
        if move_options:
            direction = random.choice(move_options)
            ct.move(direction)
            self.moved_direction = direction"""
new_rand = """        if self.moved_direction is None and self._explore(ct):
            return

        open_dirs = [
            d for d in CARDINALS
            if ct.can_move(d) and ct.get_tile_env(pos.add(d)) == Environment.EMPTY
        ]
        move_options = open_dirs or [d for d in CARDINALS if ct.can_move(d)]
        if move_options:
            direction = random.choice(move_options)
            ct.move(direction)
            self.moved_direction = direction"""
assert old_rand in s, "random-walk anchor"
s = s.replace(old_rand, new_rand, 1)

open(path, "w", newline="").write(s)
print(f"patched {path}")
