#!/usr/bin/env python3
"""Raid enemy infrastructure on the way in, instead of walking past it.

Order-less builders march across the map to snipe a 500 HP core -- which costs
500 Ti of builder fire to kill -- while stepping right past enemy harvesters
(30 HP) and conveyors (20 HP) without touching them. Meanwhile we bank thousands
of titanium with nothing to spend it on: the siege is positioning-limited, not
money-limited, so surplus just piles up.

Killing a harvester costs 30 Ti of fire and denies 2.5 Ti/round forever, paying
back in twelve rounds. It also attacks the one thing the top teams beat us with:
compounding economy. Belts are even cheaper to cut, and a severed belt strands
everything upstream of it.

Priority: harvester, then splitter/conveyor, then anything else adjacent.
"""
import sys
p = sys.argv[1] + "/main.py"
s = open(p, newline="").read().replace("\r\n", "\n")

s = s.replace("SLOT_GAME_DATA = 0",
              "SLOT_GAME_DATA = 0\n\n"
              "# What a passing builder should wreck first. Harvesters compound, so they\n"
              "# hurt most; belts are cheapest to cut and strand everything upstream.\n"
              "RAID_PRIORITY = {EntityType.HARVESTER: 0, EntityType.SPLITTER: 1,\n"
              "                 EntityType.CONVEYOR: 2, EntityType.SENTINEL: 3,\n"
              "                 EntityType.GUNNER: 4, EntityType.LAUNCHER: 5,\n"
              "                 EntityType.BARRIER: 6}", 1)

old = """        if self.opp_core_tiles:
            for tile in adjacent_tiles(pos):
                if ct.can_build_sentinel(tile, Direction.NORTH):"""
new = """        # Wreck whatever enemy infrastructure we happen to be standing next to.
        # Their economy is the thing we cannot out-grow, so denying it is worth
        # more than the titanium, which we have no other use for anyway.
        raid = []
        for tile in adjacent_tiles(pos):
            bid = ct.get_tile_building_id(tile)
            if bid is None or ct.get_team(bid) == ct.get_team():
                continue
            kind = ct.get_entity_type(bid)
            if kind in RAID_PRIORITY and ct.can_fire(tile):
                raid.append((RAID_PRIORITY[kind], ct.get_hp(bid), tile))
        if raid:
            raid.sort()
            ct.fire(raid[0][2])
            return

        if self.opp_core_tiles:
            for tile in adjacent_tiles(pos):
                if ct.can_build_sentinel(tile, Direction.NORTH):"""
assert s.count(old) == 1, "raid anchor"
s = s.replace(old, new, 1)
open(p, "w", newline="").write(s)
print(f"patched {p}")
