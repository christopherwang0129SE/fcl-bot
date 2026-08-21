#!/usr/bin/env python3
"""Besiege the enemy core from outside gunner range.

Sentinels reach sqrt(32) = 5.66 tiles and their line shot ignores obstacles.
Gunners reach only sqrt(13) = 3.61 and are blocked by anything in the way. So
there is a standoff band, roughly 3.7 to 5.6 tiles from the enemy core, where a
sentinel can grind the core while no gunner defending it can answer.

The staging code picks whichever attack tile is nearest the *builder*, which
frequently means walking right up to the core and into that gunner envelope.
Prefer tiles in the standoff band instead, and only fall back to close ones when
nothing further out is available.
"""
import sys
p = sys.argv[1] + "/main.py"
s = open(p, newline="").read().replace("\r\n", "\n")

s = s.replace("SLOT_GAME_DATA = 0",
              "SLOT_GAME_DATA = 0\n\n"
              "# Gunners reach r^2=13; sentinels reach r^2=32 and ignore obstacles.\n"
              "# Stage beyond gunner reach so the siege cannot be answered.\n"
              "GUNNER_ENVELOPE_SQ = 13", 1)

old = """            attack_tiles = tiles_to_attack_core_ct_mode(self.opp_core_tiles, ct)
            if attack_tiles:
                best_tile = min(attack_tiles, key=lambda tile: tile.distance_squared(pos))
                self._bot_pathfind(best_tile, ct)"""
new = """            attack_tiles = tiles_to_attack_core_ct_mode(self.opp_core_tiles, ct)
            if attack_tiles:
                # Prefer tiles that still bear on the core but sit outside the
                # range of any gunner defending it.
                standoff = [t for t in attack_tiles
                            if min(t.distance_squared(c) for c in self.opp_core_tiles)
                            > GUNNER_ENVELOPE_SQ]
                candidates = standoff or attack_tiles
                best_tile = min(candidates, key=lambda tile: tile.distance_squared(pos))
                self._bot_pathfind(best_tile, ct)"""
assert s.count(old) == 1, "staging anchor"
s = s.replace(old, new, 1)
open(p, "w", newline="").write(s)
print(f"patched {p}")
