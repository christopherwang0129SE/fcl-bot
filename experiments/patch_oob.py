#!/usr/bin/env python3
"""Stop the builder killing itself by asking about a tile off the edge.

Measured against the engine (probe in scratchpad/oob): every `can_*()` returns
False for an out-of-bounds Position, but `get_tile_env()` and
`get_tile_building_id()` RAISE GameError -- and an uncaught exception destroys
that unit permanently for the rest of the match.

The live bot has three unguarded calls, all the same shape:

    blocked_by_id = ct.get_tile_building_id(bot_position.add(self.build_direction))

`build_direction` comes from the build order and is applied to the *builder's*
tile, not the order's tile, so it reaches up to two tiles away from `go_to`. On
any order planned near a map edge that lands off the grid and the builder dies
on the spot. Everything else in the bot iterates `get_nearby_tiles()`, which
only ever yields in-bounds tiles, so these three are the whole exposure.

  python3 patch_oob.py <botdir>
"""
import sys

p = sys.argv[1] + "/main.py"
raw = open(p, newline="").read()
nl = "\r\n" if "\r\n" in raw else "\n"
s = raw.replace("\r\n", "\n")

helper = '''def building_id_at(tile: Position, ct: Controller) -> int | None:
    """get_tile_building_id() raises off the edge of the map, and an uncaught
    exception permanently destroys the unit. can_* calls are safe there, so the
    cheapest guard is an explicit bounds test."""
    if 0 <= tile.x < ct.get_map_width() and 0 <= tile.y < ct.get_map_height():
        return ct.get_tile_building_id(tile)
    return None


def tile_has_enemy('''
assert s.count("def tile_has_enemy(") == 1, "helper anchor"
s = s.replace("def tile_has_enemy(", helper, 1)

old = "blocked_by_id = ct.get_tile_building_id(bot_position.add(self.build_direction))"
new = "blocked_by_id = building_id_at(bot_position.add(self.build_direction), ct)"
assert s.count(old) == 3, "expected 3 unguarded lookups, found %d" % s.count(old)
s = s.replace(old, new)

open(p, "w", newline="").write(s.replace("\n", nl))
print("out-of-bounds guard -> " + sys.argv[1])
