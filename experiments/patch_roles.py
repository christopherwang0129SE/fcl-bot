#!/usr/bin/env python3
"""Coordinate builder roles using more store slots.

README idea: "Coordinate builder roles (explorer vs builder vs defender) using
more store slots".

The 16 slots are currently spent like this:

    0            game data
    1,2,3        builder 4 scout   (env + close entities + far entities)
    4,5,6        builder 3 scout
    7            builder 3 order
    8,9,10       builder 2 scout
    11           builder 2 order
    12,13,14     builder 1 scout
    15           builder 1 order

Three slots of scouting per builder leaves room for only THREE concurrent build
orders, which is the measured bottleneck: we field 6-9 harvesters where the top
team fields 17-40, because most builders simply never have mining work.

Entity scouting is what eats the space, and it is largely redundant -- every
builder reports the same kind of local entity cross, and the core mainly uses it
for "is this ore near an enemy" plus a fallback opponent-core guess (symmetry
detection already finds the enemy core without it). So keep entity reporting for
ONE builder and give everyone else a single environment slot:

    0            game data
    1..6         build orders          <- 6 concurrent, was 3
    7..12        environment scout, one per builder
    13,14        entity scout (close/far), builder 1 only
    15           role assignment, 2 bits per builder

That doubles harvester concurrency and leaves a real role channel.
"""
import sys

p = sys.argv[1] + "/main.py"
s = open(p, newline="").read().replace("\r\n", "\n")

# ---------------------------------------------------------------- constants
s = s.replace("SLOT_GAME_DATA = 0",
"""SLOT_GAME_DATA = 0

# --- store layout (16 slots) ------------------------------------------------
# 0      game data          1..6   build orders, one per builder
# 7..12  environment scout  13,14  entity scout (builder 1 only)
# 15     role assignment, 2 bits per builder
MAX_ORDER_BUILDERS = 6
SLOT_ORDER_BASE = 1
SLOT_SCOUT_BASE = 7
SLOT_ENT_CLOSE = 13
SLOT_ENT_FAR = 14
SLOT_ROLES = 15

ROLE_ATTACKER = 0   # default: stage on the enemy core (where our wins come from)
ROLE_DEFENDER = 1   # fall back and cover our own core while it is being hurt""", 1)

# --------------------------------------------- env-only + entity-only readers
old = """def read_stored_env_scout(store_index: int, stored_map: Map, ct: Controller) -> None:
    bot_pos, scouted_env = parse_scout(ct.read_store(store_index))
    ct.write_store(store_index, 0)
    for tile, env in scouted_env.items():
        stored_map.set_environment_at(tile, env)"""
new = """def read_stored_env_scout(store_index: int, stored_map: Map, ct: Controller) -> Position:
    bot_pos, scouted_env = parse_scout(ct.read_store(store_index))
    ct.write_store(store_index, 0)
    for tile, env in scouted_env.items():
        stored_map.set_environment_at(tile, env)
    return bot_pos


def read_stored_entities(bot_pos: Position, stored_map: Map, ct: Controller) -> None:
    \"\"\"Fold the one entity-scout report into the shared map.\"\"\"
    close_entities = parse_entities(ct.read_store(SLOT_ENT_CLOSE))
    far_entities = parse_entities(ct.read_store(SLOT_ENT_FAR))
    ct.write_store(SLOT_ENT_CLOSE, 0)
    ct.write_store(SLOT_ENT_FAR, 0)
    for i in range(8):
        dx, dy = SCOUT_CLOSE_CROSS_OFFSETS[i]
        stored_map.set_entity_at(Position(bot_pos.x + dx, bot_pos.y + dy), close_entities[i])
        dx, dy = SCOUT_FAR_CROSS_OFFSETS[i]
        stored_map.set_entity_at(Position(bot_pos.x + dx, bot_pos.y + dy), far_entities[i])"""
assert s.count(old) == 1, "env scout reader anchor"
s = s.replace(old, new, 1)

# ------------------------------------------------------- builder slot claim
old = """        if self.am_builder_number < 4:
            self.build_order_slot = 19 - 4 * self.am_builder_number
            self.scout_store_slot = 18 - 4 * self.am_builder_number
        elif self.am_builder_number == 4:
            self.scout_store_slot = 3"""
new = """        if 1 <= self.am_builder_number <= MAX_ORDER_BUILDERS:
            self.build_order_slot = SLOT_ORDER_BASE + self.am_builder_number - 1
            self.scout_store_slot = SLOT_SCOUT_BASE + self.am_builder_number - 1"""
assert s.count(old) == 1, "builder slot anchor"
s = s.replace(old, new, 1)

# ------------------------------------------------------------ builder report
old = """        scout_close_entities_n = encode_entities(ct.get_position(), SCOUT_CLOSE_CROSS_OFFSETS, ct)
        scout_far_entities_n = encode_entities(ct.get_position(), SCOUT_FAR_CROSS_OFFSETS, ct)
        ct.write_store(self.scout_store_slot - 1, scout_close_entities_n)
        ct.write_store(self.scout_store_slot - 2, scout_far_entities_n)"""
new = """        # Only one builder reports entities; the rest of the slots are orders now.
        if self.am_builder_number == 1:
            ct.write_store(SLOT_ENT_CLOSE,
                           encode_entities(ct.get_position(), SCOUT_CLOSE_CROSS_OFFSETS, ct))
            ct.write_store(SLOT_ENT_FAR,
                           encode_entities(ct.get_position(), SCOUT_FAR_CROSS_OFFSETS, ct))"""
assert s.count(old) == 1, "report anchor"
s = s.replace(old, new, 1)

# --------------------------------------------------------- core: read scouts
old = """        for i in range(0,min(3,self.bots_made)):
            scout_slot = 14 - 4*i
            self.builder_positions[i] = read_stored_scout(scout_slot, ENV_MAP, ct)
            read_stored_scout(3, ENV_MAP, ct) #Bot 4 is special"""
new = """        for i in range(0, min(MAX_ORDER_BUILDERS, self.bots_made)):
            reported = read_stored_env_scout(SLOT_SCOUT_BASE + i, ENV_MAP, ct)
            self.builder_positions[i] = reported
            if i == 0:
                read_stored_entities(reported, ENV_MAP, ct)"""
assert s.count(old) == 1, "core scout loop anchor"
s = s.replace(old, new, 1)

# ------------------------------------------------- core: plan + assign orders
old = "        for i in range(0,3-len(self.build_orders_made)):"
new = "        for i in range(0, MAX_ORDER_BUILDERS - len(self.build_orders_made)):"
assert s.count(old) == 1, "plan count anchor"
s = s.replace(old, new, 1)

old = """        for i in range(0,min(3,self.bots_made+1)):#Plan also the new bot
            order_slot = 15 - 4*i"""
new = """        for i in range(0, min(MAX_ORDER_BUILDERS, self.bots_made + 1)):#Plan also the new bot
            order_slot = SLOT_ORDER_BASE + i"""
assert s.count(old) == 1, "assign loop anchor"
s = s.replace(old, new, 1)

# ------------------------------------------------------------- core: spawning
old = "        if self.bots_made < 4:"
new = "        if self.bots_made < MAX_ORDER_BUILDERS:"
assert s.count(old) == 1, "spawn cap anchor"
s = s.replace(old, new, 1)

old = "        if ct.get_hp() < ct.get_max_hp() and self.bots_made < 6:"
new = "        if ct.get_hp() < ct.get_max_hp() and self.bots_made < MAX_ORDER_BUILDERS + 2:"
assert s.count(old) == 1, "healer spawn anchor"
s = s.replace(old, new, 1)

s = s.replace("        self.builder_positions: list[Position|None] = [None, None, None]",
              "        self.builder_positions: list[Position|None] = [None] * MAX_ORDER_BUILDERS", 1)

# ------------------------------------------------------------- core: publish roles
old = "        ct.write_store(SLOT_GAME_DATA,encode_game_data(self.bots_made, self.opp_core_bottom_right))"
new = """        # Roles only steer builders with no build order. Default everyone to
        # attacker -- every experiment that pulled builders off the enemy core
        # lost -- and peel one back to defend only while the core is taking hits.
        hurt = ct.get_hp() < ct.get_max_hp()
        roles = 0
        for i in range(MAX_ORDER_BUILDERS):
            role = ROLE_DEFENDER if (hurt and i == 0) else ROLE_ATTACKER
            roles |= role << (2 * i)
        ct.write_store(SLOT_ROLES, roles)

        ct.write_store(SLOT_GAME_DATA,encode_game_data(self.bots_made, self.opp_core_bottom_right))"""
assert s.count(old) == 1, "game data write anchor"
s = s.replace(old, new, 1)

# ------------------------------------------------------- builder: act on role
old = """    def _bot_without_orders(self, ct: Controller) -> None:
        \"\"\"When the builder does not have an order it can do this\"\"\"
        pos = ct.get_position()"""
new = """    def _my_role(self, ct: Controller) -> int:
        if not (1 <= self.am_builder_number <= MAX_ORDER_BUILDERS):
            return ROLE_ATTACKER
        return (ct.read_store(SLOT_ROLES) >> (2 * (self.am_builder_number - 1))) & 3

    def _defend_core(self, ct: Controller) -> bool:
        \"\"\"Cover our own core. True if this consumed the turn.\"\"\"
        if not self.own_core_tiles:
            return False
        pos = ct.get_position()
        home = min(self.own_core_tiles, key=lambda t: t.distance_squared(pos))
        if pos.distance_squared(home) > 16:
            self._bot_pathfind(home, ct)
            return True
        target = None
        best = 1 << 30
        for entity_id in ct.get_nearby_units():
            if ct.get_team(entity_id) == ct.get_team():
                continue
            enemy = ct.get_position(entity_id)
            if enemy.distance_squared(pos) < best:
                best, target = enemy.distance_squared(pos), enemy
        if target is None:
            return False
        for tile in adjacent_tiles(pos):
            for facing in CARDINALS:
                if ct.can_fire_from(tile, facing, EntityType.SENTINEL, target) \\
                        and ct.can_build_sentinel(tile, facing):
                    ct.build_sentinel(tile, facing)
                    return True
        return False

    def _bot_without_orders(self, ct: Controller) -> None:
        \"\"\"When the builder does not have an order it can do this\"\"\"
        pos = ct.get_position()

        if self._my_role(ct) == ROLE_DEFENDER and self._defend_core(ct):
            return"""
assert s.count(old) == 1, "bot_without_orders anchor"
s = s.replace(old, new, 1)

open(p, "w", newline="").write(s)
print(f"patched {p}")
