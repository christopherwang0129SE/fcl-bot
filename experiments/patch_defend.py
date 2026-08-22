#!/usr/bin/env python3
"""Make the builders spawned *because we are being attacked* actually defend.

The core already reacts to a rush:

    if ct.get_hp() < ct.get_max_hp() and self.bots_made < 6:
        ... spawn a builder "towards the back"

but nothing tells that builder it is a defender. Builders 5 and 6 get no scout
slot and no build-order slot, so they fall through to `_bot_without_orders`,
which pushes to the opposite corner and marches at the ENEMY core. The bot's
entire answer to being rushed is therefore to send two more attackers away from
the fight, and the only defending it ever does is the incidental `can_heal` at
the top of the build plan.

This patch changes nothing about the four-builder siege force -- CLAUDE.md
records that count as a measured optimum and every variant that spent siege
turns on something else lost. It only redirects the builders that already exist
solely because our core is being hit: they hold station near the core, shoot
what is next to them, heal the core, and put a sentinel down facing the
intruder rather than facing an enemy core on the other side of the map.

  python3 patch_defend.py <botdir> [max_defenders]
"""
import sys

d = sys.argv[1]
max_defenders = int(sys.argv[2]) if len(sys.argv) > 2 else 2

p = d + "/main.py"
raw = open(p, newline="").read()
nl = "\r\n" if "\r\n" in raw else "\n"
s = raw.replace("\r\n", "\n")


def sub(old, new):
    global s
    assert s.count(old) == 1, "anchor: " + old.strip().split("\n")[0][:60]
    s = s.replace(old, new, 1)


sub("""        self.own_core_tiles = []""",
    """        self.own_core_tiles = []
        self.is_defender = False""")

# Anchored below the identity assignment rather than on it, so this composes
# with patch_respawn (which rewrites that same line).
sub("""        if self.am_builder_number < 4:
            self.build_order_slot = 19 - 4 * self.am_builder_number""",
    """        # Builders past the fourth exist only because the core is being hit.
        self.is_defender = self.am_builder_number > 4
        if self.am_builder_number < 4:
            self.build_order_slot = 19 - 4 * self.am_builder_number""")

sub("""        if self.build_stage >= 0:
            self._execute_buildplan(ct)
        else:
            self._bot_without_orders(ct)""",
    """        if self.is_defender:
            self._run_defender(ct)
        elif self.build_stage >= 0:
            self._execute_buildplan(ct)
        else:
            self._bot_without_orders(ct)""")

sub("""    def _report_to_store(self, ct: Controller) -> None:""",
    '''    def _nearest_intruder(self, ct: Controller) -> Position | None:
        """The closest enemy unit we can see, whether or not it is adjacent."""
        best, best_d2 = None, 10 ** 6
        pos = ct.get_position()
        for entity_id in ct.get_nearby_units():
            if ct.get_team(entity_id) == ct.get_team():
                continue
            where = ct.get_position(entity_id)
            d2 = where.distance_squared(pos)
            if d2 < best_d2:
                best, best_d2 = where, d2
        return best

    def _run_defender(self, ct: Controller) -> None:
        """Hold the ground around our own core instead of marching away."""
        pos = ct.get_position()
        if not self.own_core_tiles:
            for tile in ct.get_nearby_tiles():
                if bid := ct.get_tile_building_id(tile):
                    if ct.get_entity_type(bid) == EntityType.CORE and ct.get_team(bid):
                        self.own_core_tiles.append(tile)

        # 1. Hit whatever is already next to us.
        for tile in adjacent_tiles(pos):
            if ct.can_fire(tile):
                bid = ct.get_tile_building_id(tile)
                if bid is not None and ct.get_team(bid) != ct.get_team():
                    ct.fire(tile)
                    return

        # 2. Patch up whatever next to us is hurt -- the core first of all.
        for tile in adjacent_tiles(pos):
            if ct.can_heal(tile):
                ct.heal(tile)
                return

        intruder = self._nearest_intruder(ct)

        # 3. A sentinel that bears on the intruder, not on a core 30 tiles away.
        if intruder is not None:
            for tile in adjacent_tiles(pos):
                if ct.can_build_sentinel(tile, Direction.NORTH):
                    for direction in Direction:
                        if ct.can_fire_from(tile, direction, EntityType.SENTINEL, intruder):
                            ct.build_sentinel(tile, direction)
                            return

        # 4. Otherwise stay on station between the core and the threat.
        if self.own_core_tiles:
            home = self.own_core_tiles[0]
            if pos.distance_squared(home) > 8:
                self._bot_pathfind(home, ct)
                return
            if intruder is None:
                # Quiet: thicken the shell. Barriers are 10 HP per titanium
                # against healing's 4, and +1% cost scale against a turret's
                # +20%, so this is the cheap way to spend an idle defender.
                for tile in adjacent_tiles(pos):
                    if ct.can_build_barrier(tile):
                        ct.build_barrier(tile)
                        return
            else:
                self._bot_pathfind(intruder, ct)
                return

        for direction in CARDINALS:
            if ct.can_move(direction):
                ct.move(direction)
                self.moved_direction = direction
                return

    def _report_to_store(self, ct: Controller) -> None:''')

if max_defenders != 2:
    sub("""        if ct.get_hp() < ct.get_max_hp() and self.bots_made < 6:""",
        """        if ct.get_hp() < ct.get_max_hp() and self.bots_made < %d:""" % (4 + max_defenders))

open(p, "w", newline="").write(s.replace("\n", nl))
print("defenders (max %d) -> %s" % (max_defenders, d))
