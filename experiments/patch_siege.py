#!/usr/bin/env python3
"""Build the siege sentinel before healing, not after.

Destroying the enemy core is how this bot wins, and a sentinel placed where it
can hit that core is the tool it wins with -- sentinels have r^2=32 reach and a
line shot that ignores obstacles, so they can grind a 500 HP core from outside
the defenders.

But _bot_without_orders checks heal FIRST and returns on success. Heal and
build share the one action cooldown, so a builder that has finally reached a
firing tile spends its action topping up 4 HP instead. The numbers fit: 115
heals per game against 1-4 sentinels ever built. Right where we want to build,
things are damaged, so heal always wins the race.

Swap the order: if we can place a sentinel that bears on the enemy core, that is
worth more than 4 HP.
"""
import sys
p = sys.argv[1] + "/main.py"
s = open(p, newline="").read().replace("\r\n", "\n")

heal_block = """        for tile in adjacent_tiles(pos):
            if ct.can_heal(tile):
                ct.heal(tile)
                return

        if self.opp_core_tiles:
            for tile in adjacent_tiles(pos):
                if ct.can_build_sentinel(tile, Direction.NORTH):
                    orientation = sentinel_could_hit_opp_core_from(tile, self.opp_core_tiles, ct)
                    if orientation:
                        ct.build_sentinel(tile, orientation)
                        return
"""
new_block = """        # Siege first: heal and build compete for the same action cooldown, and a
        # sentinel bearing on the enemy core is worth far more than 4 HP.
        if self.opp_core_tiles:
            for tile in adjacent_tiles(pos):
                if ct.can_build_sentinel(tile, Direction.NORTH):
                    orientation = sentinel_could_hit_opp_core_from(tile, self.opp_core_tiles, ct)
                    if orientation:
                        ct.build_sentinel(tile, orientation)
                        return

        for tile in adjacent_tiles(pos):
            if ct.can_heal(tile):
                ct.heal(tile)
                return

        if self.opp_core_tiles:
"""
assert s.count(heal_block) == 1, "siege/heal anchor"
s = s.replace(heal_block, new_block, 1)
open(p, "w", newline="").write(s)
print(f"patched {p}")
