#!/usr/bin/env python3
"""TURTLE: stop rushing, fortify, out-mine, win on the round-1000 tiebreak.

A completely different playing style, motivated by three measurements:

  * Our games end at turn ~85 by core destruction. Pantheon vs Pivot ran 364.
    Economy compounds with time, so a short game is one where our economy can
    never pay. Their 40 harvesters are worth ~36,000 Ti of lifetime income;
    our 7 over 85 turns are worth ~1,500.
  * Alone on a map we mine 5,000-9,900 Ti in 1000 rounds -- the tiebreak is
    decided on titanium collected, and we have never once played for it.
  * Barriers are 3 Ti for 30 HP (10 HP/Ti) at +1% scale, while healing -- our
    single most common action, ~115x per game -- is 4 HP/Ti, and a turret costs
    +20% scale. We build zero barriers.

So: builders with mining orders keep mining, and builders without one stop
walking across the map to snipe the enemy core. They come home, wall the
approaches with cheap barriers, and put sentinels on anything that arrives.
"""
import sys
p = sys.argv[1] + "/main.py"
s = open(p, newline="").read().replace("\r\n", "\n")

s = s.replace("SLOT_GAME_DATA = 0",
              "SLOT_GAME_DATA = 0\n\n"
              "# Turtle parameters. Barriers ring the core between these squared radii,\n"
              "# leaving the spawn ring itself clear so the core can still make builders.\n"
              "BARRIER_MIN_SQ = 8\n"
              "BARRIER_MAX_SQ = 32\n"
              "# Keep this much titanium free for harvesters and belts.\n"
              "FORTIFY_RESERVE = 60", 1)

old = """    def _bot_without_orders(self, ct: Controller) -> None:
        \"\"\"When the builder does not have an order it can do this\"\"\"
        pos = ct.get_position()

        if self.opp_core_bottom_right is None:
            self._push_to_opposite_corner(ct)

        for tile in adjacent_tiles(pos):
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

            attack_tiles = tiles_to_attack_core_ct_mode(self.opp_core_tiles, ct)
            if attack_tiles:
                best_tile = min(attack_tiles, key=lambda tile: tile.distance_squared(pos))
                self._bot_pathfind(best_tile, ct)
"""
new = """    def _nearest_enemy(self, ct: Controller):
        target, best = None, 1 << 30
        for entity_id in ct.get_nearby_units():
            if ct.get_team(entity_id) == ct.get_team():
                continue
            ep = ct.get_position(entity_id)
            d = ep.distance_squared(ct.get_position())
            if d < best:
                best, target = d, ep
        return target

    def _bot_without_orders(self, ct: Controller) -> None:
        \"\"\"TURTLE: hold the base, fortify it, and let the economy win on points.\"\"\"
        pos = ct.get_position()

        if not self.own_core_tiles:
            for tile in ct.get_nearby_tiles():
                bid = ct.get_tile_building_id(tile)
                if bid and ct.get_entity_type(bid) == EntityType.CORE and ct.get_team(bid) == ct.get_team():
                    self.own_core_tiles.append(tile)

        if not self.own_core_tiles:
            for d in CARDINALS:
                if ct.can_move(d):
                    ct.move(d)
                    self.moved_direction = d
                    return
            return

        home = min(self.own_core_tiles, key=lambda t: t.distance_squared(pos))
        home_sq = pos.distance_squared(home)

        # Shoot back: a sentinel that bears on whatever is attacking us.
        enemy = self._nearest_enemy(ct)
        if enemy is not None:
            for tile in adjacent_tiles(pos):
                for facing in CARDINALS:
                    if ct.can_fire_from(tile, facing, EntityType.SENTINEL, enemy) \\
                            and ct.can_build_sentinel(tile, facing):
                        ct.build_sentinel(tile, facing)
                        return

        # Come home if we have drifted out.
        if home_sq > BARRIER_MAX_SQ:
            self._bot_pathfind(home, ct)
            return

        # Fortify, but ONLY while something is actually coming: barriers are
        # buildings, so walling in peacetime seals our own builders away from the
        # ore and the economy goes to zero.
        if enemy is not None and ct.get_global_resources() > FORTIFY_RESERVE + ct.get_barrier_cost():
            for tile in adjacent_tiles(pos):
                d = min(tile.distance_squared(c) for c in self.own_core_tiles)
                if (BARRIER_MIN_SQ <= d <= BARRIER_MAX_SQ
                        and tile.distance_squared(enemy) < pos.distance_squared(enemy)
                        and ct.can_build_barrier(tile)):
                    ct.build_barrier(tile)
                    return

        for tile in adjacent_tiles(pos):
            if ct.can_heal(tile):
                ct.heal(tile)
                return
"""
assert s.count(old) == 1, "bot_without_orders anchor"
s = s.replace(old, new, 1)
open(p, "w", newline="").write(s)
print(f"patched {p}")
