"""Adversarial test opponent: a bot that walls itself in with barriers.

Tests the failure mode a mirror A/B cannot produce, because neither side of a
mirror ever builds an obstacle on purpose: an opponent whose core is ringed by
barriers. Our pathfinder treats only Environment.WALL as impassable, so a
barrier ring is invisible to it -- the route goes straight through and the
builder stops dead against it.

Barriers are 3 Ti and +1% cost scale, so a starting bank of 500 buys a lot of
wall. This bot does nothing else: it never attacks, so anything that beats it
beats it by getting through.
"""
import random
from fcode import Controller, Direction, EntityType, Position

CARDINALS = [Direction.NORTH, Direction.SOUTH, Direction.EAST, Direction.WEST]
RING_MIN, RING_MAX = 4, 13      # squared distance band the wall is built in


class Player:
    def __init__(self):
        self.spawned = 0
        self.core_pos = None
        self.post = None
        self.ring = []

    def run(self, ct: Controller) -> None:
        try:
            etype = ct.get_entity_type()
            if etype == EntityType.CORE:
                if self.spawned < 4:
                    for pos in ct.get_nearby_tiles(dist_sq=8):
                        if ct.can_spawn(pos):
                            ct.spawn_builder(pos)
                            self.spawned += 1
                            break
            elif etype == EntityType.BUILDER_BOT:
                self._builder(ct)
        except Exception:
            pass

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
            self.ring = [Position(x, y)
                         for x in range(max(0, self.core_pos.x - 4), min(w, self.core_pos.x + 5))
                         for y in range(max(0, self.core_pos.y - 4), min(h, self.core_pos.y + 5))
                         if RING_MIN <= Position(x, y).distance_squared(self.core_pos) <= RING_MAX]
            random.shuffle(self.ring)

        # Wall the nearest gap we are standing next to.
        for dr in CARDINALS:
            tile = pos.add(dr)
            if tile in self.ring and ct.can_build_barrier(tile):
                ct.build_barrier(tile)
                return

        gaps = [t for t in self.ring if ct.is_tile_empty(t)]
        if gaps:
            self._step_toward(min(gaps, key=lambda t: t.distance_squared(pos)), ct)
        else:
            self._step_toward(self.core_pos, ct)

    def _pick_post(self, ct: Controller) -> Position:
        w, h = ct.get_map_width(), ct.get_map_height()
        for _ in range(20):
            dx, dy = random.randint(-5, 5), random.randint(-5, 5)
            cand = Position(self.core_pos.x + dx, self.core_pos.y + dy)
            if 0 <= cand.x < w and 0 <= cand.y < h and RING_MIN <= cand.distance_squared(self.core_pos) <= RING_MAX:
                return cand
        return self.core_pos

    def _step_toward(self, target: Position, ct: Controller) -> None:
        pos = ct.get_position()
        want = pos.cardinal_direction_to(target)
        if want and want != Direction.CENTRE and ct.can_move(want):
            ct.move(want)
            return
        options = [dr for dr in CARDINALS if ct.can_move(dr)]
        if options:
            ct.move(random.choice(options))
