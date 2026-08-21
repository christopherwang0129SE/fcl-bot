#!/usr/bin/env python3
"""Put the guns up BEFORE the attack arrives.

The turtle's weakness is not the tiebreak, it is dying: on auroraveil all six
games ended core_destroyed between turn 65 and 126. Fortification is currently
reactive -- barriers and sentinels only go up once an enemy is already visible,
by which point a rush is already inside the base.

Sentinels reach r^2=32 and their line shot ignores obstacles, so one placed early
near the core, facing the enemy approach, covers the whole avenue. Build a small
standing garrison proactively, capped so we do not drown in +20% scale.
"""
import sys
p = sys.argv[1] + "/main.py"
s = open(p, newline="").read().replace("\r\n", "\n")

s = s.replace("FORTIFY_RESERVE = 60",
              "FORTIFY_RESERVE = 60\n"
              "# Standing garrison put up before anyone shows up, per builder.\n"
              "GARRISON_PER_BUILDER = 2", 1)

s = s.replace("        self.own_core_tiles = []",
              "        self.own_core_tiles = []\n        self.garrison_built = 0", 1)

old = """        # Come home if we have drifted out.
        if home_sq > BARRIER_MAX_SQ:"""
new = """        # Standing garrison: a sentinel facing the way the enemy will come, put up
        # before they arrive rather than after they are already in the base.
        if (self.garrison_built < GARRISON_PER_BUILDER and home_sq <= BARRIER_MAX_SQ
                and self.opp_core_tiles
                and ct.get_global_resources() > FORTIFY_RESERVE + ct.get_sentinel_cost()):
            approach = min(self.opp_core_tiles, key=lambda t: t.distance_squared(home))
            facing = nearest_cardinal_to(home, approach)
            for tile in adjacent_tiles(pos):
                if ct.can_build_sentinel(tile, facing):
                    ct.build_sentinel(tile, facing)
                    self.garrison_built += 1
                    return

        # Come home if we have drifted out.
        if home_sq > BARRIER_MAX_SQ:"""
assert s.count(old) == 1, "garrison anchor"
s = s.replace(old, new, 1)

# small helper: cardinal step from a toward b
s = s.replace("def adjacent_tiles(tile: Position) -> list[Position]:",
              """def nearest_cardinal_to(a: Position, b: Position) -> Direction:
    d = a.cardinal_direction_to(b)
    return d if d in CARDINALS else Direction.NORTH


def adjacent_tiles(tile: Position) -> list[Position]:""", 1)
open(p, "w", newline="").write(s)
print(f"patched {p}")
