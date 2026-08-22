"""Adversarial test opponent: a bot that shoots builder bots.

Our own bot kills cores, not builders, so a mirror A/B never once kills an
enemy builder (measured: 0 builder deaths in 20 mirror games). That makes the
mirror structurally incapable of testing anything about losing units. Real
ladder opponents field dozens of forward turrets and do kill them.

This bot is not meant to be good. It is meant to apply the one pressure the
mirror cannot: a forward line of sentinels that shoots anything that walks in,
preferring builder bots over buildings.
"""
import random
from fcode import Controller, Direction, EntityType, Environment, Position

CARDINALS = [Direction.NORTH, Direction.SOUTH, Direction.EAST, Direction.WEST]
DIAGS = [Direction.NORTHEAST, Direction.SOUTHEAST, Direction.SOUTHWEST, Direction.NORTHWEST]


class Player:
    def __init__(self):
        self.spawned = 0
        self.core_pos = None
        self.post = None
        self.facing = None

    def run(self, ct: Controller) -> None:
        try:
            etype = ct.get_entity_type()
            if etype == EntityType.CORE:
                self._core(ct)
            elif etype == EntityType.BUILDER_BOT:
                self._builder(ct)
            else:
                self._turret(ct)
        except Exception:
            pass  # a test opponent must never remove itself from the match

    # ---------------------------------------------------------------- core --
    def _core(self, ct: Controller) -> None:
        # Keep a building reserve: converting everything leaves no turrets to
        # spend the ammo, which is how the first version of this bot ended a
        # game with 10 units and 0 buildings.
        if ct.get_global_ammo() < 60 and ct.get_global_resources() > 200:
            for want in (40, 20, 10):
                if ct.can_convert_ammo(want):
                    ct.convert_ammo(want)
                    break
        if self.spawned < 4:
            for pos in ct.get_nearby_tiles(dist_sq=8):
                if ct.can_spawn(pos):
                    ct.spawn_builder(pos)
                    self.spawned += 1
                    break

    # -------------------------------------------------------------- turret --
    def _turret(self, ct: Controller) -> None:
        best = None
        for tile in ct.get_attackable_tiles():
            bot_id = ct.get_tile_builder_bot_id(tile)   # attackable tiles are in bounds
            if bot_id and ct.get_team(bot_id) != ct.get_team():
                best = tile          # a builder bot is always the best target
                break
            if best is None:
                bid = ct.get_tile_building_id(tile)
                if bid and ct.get_team(bid) != ct.get_team():
                    best = tile
        if best is not None and ct.can_fire(best):
            ct.fire(best)

    # ------------------------------------------------------------- builder --
    def _builder(self, ct: Controller) -> None:
        pos = ct.get_position()
        if self.core_pos is None:
            for tile in ct.get_nearby_tiles():
                bid = ct.get_tile_building_id(tile)
                if bid and ct.get_entity_type(bid) == EntityType.CORE and ct.get_team(bid) == ct.get_team():
                    self.core_pos = tile
                    break
            if self.core_pos is None:
                self.core_pos = pos
            w, h = ct.get_map_width(), ct.get_map_height()
            far = Position(w - 1 - self.core_pos.x, h - 1 - self.core_pos.y)
            # Stand a third of the way toward the enemy and hold that line.
            self.post = Position((2 * self.core_pos.x + far.x) // 3 + random.randint(-2, 2),
                                 (2 * self.core_pos.y + far.y) // 3 + random.randint(-2, 2))
            self.post = Position(max(0, min(w - 1, self.post.x)), max(0, min(h - 1, self.post.y)))
            self.facing = self.core_pos.direction_to(far)

        # Shoot back at anything adjacent before anything else.  Note
        # get_tile_building_id RAISES out of bounds while every can_*() returns
        # False, so the can_fire() gate has to come first.
        for d in CARDINALS:
            tile = pos.add(d)
            if ct.can_fire(tile) and (bid := ct.get_tile_building_id(tile)) and ct.get_team(bid) != ct.get_team():
                ct.fire(tile)
                return

        if pos.distance_squared(self.post) > 4:
            self._step_toward(self.post, ct)
            return

        for d in CARDINALS:
            tile = pos.add(d)
            if ct.can_build_sentinel(tile, self.facing):
                ct.build_sentinel(tile, self.facing)
                return
        for d in CARDINALS:
            tile = pos.add(d)
            if ct.can_build_gunner(tile, self.facing):
                ct.build_gunner(tile, self.facing)
                return
        self._step_toward(self.post, ct)

    def _step_toward(self, target: Position, ct: Controller) -> None:
        pos = ct.get_position()
        want = pos.cardinal_direction_to(target)
        if want and want != Direction.CENTRE and ct.can_move(want):
            ct.move(want)
            return
        options = [d for d in CARDINALS if ct.can_move(d)]
        if options:
            ct.move(random.choice(options))
