#!/usr/bin/env python3
"""Stand NEXT TO the firing position, not on it.

Measured on ragnarok over 347 siege turns: 131 turns had a buildable adjacent
tile, 173 had a tile bearing on the enemy core, and only 5 had the SAME tile do
both -- which is the only case that actually places a sentinel.

The cause is an off-by-one in staging. tiles_to_attack_core_ct_mode() returns
tiles a sentinel could fire at the core FROM, and the builder paths onto one of
them. But builders may only build on an orthogonally adjacent tile, so once
parked on the good square it inspects its neighbours -- which generally do not
bear on the core. The bot walks to the perfect spot and is then unable to use it.

Target a tile adjacent to a firing position instead, so the firing position is
in build range when we arrive.
"""
import sys
p = sys.argv[1] + "/main.py"
s = open(p, newline="").read().replace("\r\n", "\n")

old = """            attack_tiles = tiles_to_attack_core_ct_mode(self.opp_core_tiles, ct)
            if attack_tiles:
                best_tile = min(attack_tiles, key=lambda tile: tile.distance_squared(pos))
                self._bot_pathfind(best_tile, ct)"""
new = """            attack_tiles = tiles_to_attack_core_ct_mode(self.opp_core_tiles, ct)
            if attack_tiles:
                # Stand beside a firing position, not on it: build range is the
                # four orthogonally adjacent tiles, so parking on the good square
                # puts it out of reach.
                core = set(self.opp_core_tiles)
                w, h = ct.get_map_width(), ct.get_map_height()
                stands = [n for t in attack_tiles for n in adjacent_tiles(t)
                          if n not in core and 0 <= n.x < w and 0 <= n.y < h]
                best_tile = min(stands or attack_tiles,
                                key=lambda tile: tile.distance_squared(pos))
                self._bot_pathfind(best_tile, ct)"""
assert s.count(old) == 1, "staging anchor"
s = s.replace(old, new, 1)
open(p, "w", newline="").write(s)
print(f"patched {p}")
