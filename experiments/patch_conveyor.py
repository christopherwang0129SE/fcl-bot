#!/usr/bin/env python3
"""Make conveyor chains actually reach the core.

README idea: "Build complete conveyor chains from harvesters back to core".
Two defects stop that happening today.

1. A route made entirely of NORTH steps encodes as all-zero direction bits,
   because CARDINALS.index(NORTH) == 0. parse_build_order guards with
   `if (number >> 15) > 0`, which reads all-zero as "no path at all", so the
   builder lays no belts, builds the harvester anyway, and marks the order
   done. On glacierkeep (core due north of the ore) this means every chain
   dead-ends and the team mines 0 titanium in 263 turns against an opponent
   that does nothing. Fix: bit 31 is unused -- claim it as an explicit
   "this order carries a path" flag.

2. The planner rejects any route longer than 8 tiles, a limit that comes from
   how many directions fit in the order word rather than from the game. On
   drakkarfjord that rejected 609 of 609 plans -- zero harvesters all game.
   Fix: let the core plan longer routes, and have the builder finish the tail
   itself with its own BFS once the encoded steps run out.

Measured flat on its own (50-52% over 240 games); it is here because it
repairs a genuine catastrophic failure on 3+ of the 15 pool maps, and should
be judged stacked with other changes rather than alone.
"""
import sys

d = sys.argv[1]

# ---------------------------------------------------------------- main.py
p = d + "/main.py"
s = open(p, newline="").read().replace("\r\n", "\n")

s = s.replace("SLOT_GAME_DATA = 0",
              "SLOT_GAME_DATA = 0\n\n"
              "# Conveyor directions pack 2 bits each from bit 15 up, so this many\n"
              "# steps is all an order can carry; the builder finishes longer runs.\n"
              "MAX_ENCODED_CHAIN = 8\n"
              "# An all-NORTH run encodes as all-zero bits (NORTH is index 0), which is\n"
              "# indistinguishable from 'no path'. Bit 31 is free -- use it to say so.\n"
              "PATH_PRESENT_BIT = 1 << 31", 1)

old = """    if conveyor_path:
        shift = 15"""
new = """    if conveyor_path:
        number += PATH_PRESENT_BIT
        shift = 15"""
assert s.count(old) == 1, "encode anchor"
s = s.replace(old, new, 1)

old = "    if (number >> 15) > 0:"
new = "    if number & PATH_PRESENT_BIT:"
assert s.count(old) == 1, "parse anchor"
s = s.replace(old, new, 1)

s = s.replace("        self.conveyor_path: list[Direction] = []",
              "        self.conveyor_path: list[Direction] = []\n"
              "        self.chain_truncated: bool = False", 1)

old = """        self.go_to, self.build_type_n, self.build_direction, self.conveyor_path = parse_build_order(ct.read_store(self.build_order_slot))
        self.build_stage, self.path_index = 0,0"""
new = """        self.go_to, self.build_type_n, self.build_direction, self.conveyor_path = parse_build_order(ct.read_store(self.build_order_slot))
        self.build_stage, self.path_index = 0,0
        # A path that fills every encoded slot carries no terminator, so it was
        # probably cut short -- we finish routing to the core ourselves.
        self.chain_truncated = len(self.conveyor_path) >= MAX_ENCODED_CHAIN

    def _extend_conveyor_path(self, ct: Controller) -> bool:
        \"\"\"Route the rest of the belt run to the core using our own map.\"\"\"
        self.chain_truncated = False
        if not self.own_core_tiles or self.local_map is None:
            return False
        chain_end = self.go_to
        for step in self.conveyor_path:
            chain_end = chain_end.add(step)
        if chain_end in self.own_core_tiles:
            return False
        target = min(self.own_core_tiles, key=lambda t: t.distance_squared(chain_end))
        rest = bfs_path(self.local_map, chain_end, target, max_nodes=1500)
        if not rest:
            return False
        self.conveyor_path.extend(rest)
        return True"""
assert s.count(old) == 1, "read_build_order anchor"
s = s.replace(old, new, 1)

# stage-2 completion checks: try to extend before declaring the chain done
old = """        elif self.build_stage == 2:  # Has built harvester and first conveyor
            if len(self.conveyor_path) == self.path_index:"""
new = """        elif self.build_stage == 2:  # Has built harvester and first conveyor
            if len(self.conveyor_path) == self.path_index and self.chain_truncated:
                self._extend_conveyor_path(ct)
            if len(self.conveyor_path) == self.path_index:"""
assert s.count(old) == 1, "stage2 anchor A"
s = s.replace(old, new, 1)

old = """                    self.follow_path = direction_next
                    if len(self.conveyor_path) == self.path_index:"""
new = """                    self.follow_path = direction_next
                    if len(self.conveyor_path) == self.path_index and self.chain_truncated:
                        self._extend_conveyor_path(ct)
                    if len(self.conveyor_path) == self.path_index:"""
assert s.count(old) == 1, "stage2 anchor B"
s = s.replace(old, new, 1)

old = """    def _push_to_opposite_corner(self, ct: Controller) -> None:
        core_tile = self.own_core_tiles[0]"""
new = """    def _push_to_opposite_corner(self, ct: Controller) -> None:
        if not self.own_core_tiles:
            return
        core_tile = self.own_core_tiles[0]"""
assert s.count(old) == 1, "corner guard anchor"
s = s.replace(old, new, 1)

open(p, "w", newline="").write(s)

# ------------------------------------------------------------ mapclass.py
p = d + "/mapclass.py"
raw = open(p, newline="").read()
nl = "\r\n" if "\r\n" in raw else "\n"
s = raw.replace("\r\n", "\n")

s = s.replace("SYMMETRY_VERTICAL = 2",
              "SYMMETRY_VERTICAL = 2\n\n"
              "# Feasibility bound on a belt run, not an encoding bound: only the first\n"
              "# MAX_ENCODED_CHAIN steps travel in the order word, and the builder lays\n"
              "# the remainder itself.\n"
              "MAX_CONVEYOR_CHAIN = 20", 1)

old = "            if len(conveyor_path) > 8: return False, easiest_build, Direction.NORTH, []"
new = "            if len(conveyor_path) > MAX_CONVEYOR_CHAIN: return False, easiest_build, Direction.NORTH, []"
assert s.count(old) == 1, "cap anchor"
s = s.replace(old, new, 1)

s = s.replace('        print(f"{conveyor_path=}")\n\n', "", 1)   # per-plan debug spam on the core

open(p, "w", newline="").write(s.replace("\n", nl))
print(f"patched {d}")
