"""Local-greedy economy rewrite of scouter2.

scouter2's core was the sole planner: it found ore, routed a belt chain, packed
the whole thing into one 31-bit store word and handed it to a builder, which
executed it blindly. Three store slots per builder went to scouting, leaving
room for exactly three build orders, so at most three harvesters were ever
under construction; every order routed a private chain home, costing 3-4 belts
per harvester; and when assignment stalled the builders' default job was a
cross-map march.

Here the core plans nothing economic. Each builder, every turn, in priority
order: build a harvester on adjacent ore that already touches our conveyor
network; else lay the one belt that extends the network toward the cheapest
unclaimed ore; else walk to where it could do one of those. See network.py for
why that is sound with no central bookkeeping.

What is deliberately unchanged: the sentinel siege on the enemy core. That is
the win condition, and every experiment that traded it away lost. Builders fall
through to it whenever there is no economic work in reach -- and a richer
economy feeds it directly, because the siege was measured to be money-limited
(a sentinel was affordable only ~66% of the turns one could have been placed).
"""
import random

from fcode import Controller, Team, EntityType, Environment, Direction, Position, GameError

from mapclass import Map
from network import plan_extension
from pathfind import bfs_path

# Builder bots move only in the four cardinal directions.
CARDINALS = [Direction.NORTH, Direction.SOUTH, Direction.EAST, Direction.WEST]
Environments = [0, Environment.EMPTY, Environment.WALL, Environment.ORE_TITANIUM]
ENV_MAP = Map()

SLOT_GAME_DATA = 0

# Freed by deleting the build-order system. Each of the first three builders
# owns one, and reports two things in it: the ore tile it is working toward (so
# the others leave it alone) and the belt tile it laid this turn.
#
# The belt half is what makes the network *shared*. A builder lays at most one
# belt per turn and every builder reads every slot every turn, so 11 bits per
# builder per turn is exactly enough to keep everyone's picture complete. Without
# it each builder only knew the belts it had personally laid or walked past, and
# two of them would run parallel 15-belt trunks to the same ore cluster.
CLAIM_SLOTS = [15, 11, 7]
CLAIM_BITS = 11

# Builders whose first choice is economy. Others go straight to the siege.
# The whole set by default; the econ/siege split is the main thing to sweep.
ECON_BUILDERS = (1, 2, 3, 4, 5, 6)

# Furthest a builder will walk to take a mining job at all. None = no limit.
MAX_WALK = None
# Longest belt run worth laying to reach one more ore tile. This is a reach
# budget for the *network*, not for one harvester: once a trunk has been pushed
# out to a cluster, every further ore in that cluster hooks on for a belt or
# two. Capping it at 12 stranded the bot after the ore around its own core ran
# out -- builders knew of 13 ore tiles and could plan for none of them.
MAX_BELTS = 25
# Turns of getting nowhere on one ore tile before writing it off.
STALL_LIMIT = 8
# A team-mate laying a belt or a tile coming into view marks the plan stale
# almost every turn, and a full re-search costs a large slice of the 10ms
# per-unit budget. A slightly stale plan just means a belt or two more, so
# re-search on a timer -- unless we have no plan at all, which is urgent.
REPLAN_EVERY = 5

#4 groups of 9 offsets reprsenting the edge of the scouted area after moving NSEW
SCOUT_EDGE_OFFSETS = [[(-4,-2), (-3,-3), (-2,-4), (-1,-4), (0,-4), (1,-4), (2,-4), (3,-3), (4,-2)],
           [(-4,2), (-3,3), (-2,4), (-1,4), (0,4), (1,4), (2,4), (3,3), (4,2)],
           [(2,4), (3,3), (4,2), (4,1), (4,0), (4,-1), (4,-2), (3,-3), (2,-4)],
           [(-2,4), (-3,3), (-4,2), (-4,1), (-4,0), (-4,-1), (-4,-2), (-3,-3), (-2,-4)]]

#8 offsets to of the cross around position
SCOUT_CLOSE_CROSS_OFFSETS = [(-2,0), (-1,0), (1,0), (2,0), (0,2), (0,1), (0,-2), (0,-1)]
SCOUT_FAR_CROSS_OFFSETS = [(-4,0), (-3,0), (3,0), (4,0), (0,4), (0,3), (0,-4), (0,-3)]


ENTITIES_CODE = {EntityType.BUILDER_BOT: 1, EntityType.GUNNER: 2, EntityType.SENTINEL: 3,
                 EntityType.LAUNCHER: 4, EntityType.HARVESTER: 5, EntityType.CONVEYOR: 6,
                 EntityType.SPLITTER: 6, EntityType.BARRIER: 7, EntityType.CORE: 0}

NETWORK_TYPES = (EntityType.CONVEYOR, EntityType.SPLITTER)

"""
0 (GAME DATA): OppCoreBottom (10-bit) builders_made (5-bit)

1 (B4): Entities scout far (32-bit)
2 (B4): Entities scout close (32-bit)
3 (B4) Environment scout (32-bit)

4-7 (B3)
8-11 (B2)
12 (B1): Entities scout far (32-bit)
13 (B1): Entities scout close (32-bit)
14 (B1): Environment scout (32-bit)
15 (B1): Ore claim (11-bit)
"""

def tiles_to_attack_with_sentinel_from(target: Position) -> list[Position]:
    tiles = []
    for direction in Direction:
        active_tile = target.add(direction)
        for i in range(4):
            tiles.append(active_tile)
            active_tile = active_tile.add(direction)
        if direction in CARDINALS: tiles.append(active_tile)
    return tiles

def tiles_to_attack_core_ct_mode(core_tiles: list[Position], ct: Controller) -> list[Position]:
    usable_tiles = []
    visible_tiles = ct.get_nearby_tiles()
    for core_tile in core_tiles:
        possible = tiles_to_attack_with_sentinel_from(core_tile)
        for tile in possible:
            if tile.x < 0 or tile.x >= ct.get_map_width() or tile.y < 0 or tile.y >= ct.get_map_height(): continue
            if tile in visible_tiles and not ct.is_tile_empty(tile): continue
            if tile not in core_tiles: usable_tiles.append(tile)
    return usable_tiles


def tile_has_enemy(tile: Position, ct: Controller) -> bool:
    building_id = ct.get_tile_building_id(tile)
    if building_id is not None and ct.get_team(building_id) != ct.get_team():
        return True
    bot_id = ct.get_tile_builder_bot_id(tile)
    if bot_id is not None and ct.get_team(bot_id) != ct.get_team():
        return True
    return False

def tile_has_enemy_core(tile: Position, ct: Controller) -> bool:
    return ct.get_tile_building_id(tile) and ct.get_team(ct.get_tile_building_id(tile)) != ct.get_team() and ct.get_entity_type(ct.get_tile_building_id(tile)) == EntityType.CORE

def sentinel_could_hit_opp_core_from(tile: Position, opp_core_tiles: list[Position], ct: Controller) -> Direction | None:
    for direction in Direction:
        for core_tile in opp_core_tiles:
            if ct.can_fire_from(tile, direction, EntityType.SENTINEL, core_tile):
                return direction
    return None

def adjacent_tiles(tile: Position) -> list[Position]:
    return [tile.add(direction) for direction in CARDINALS]

def encode_entities(pos: Position, offsets: list, ct: Controller) -> int:
    """Looks at the 8 tiles in the center-less cross and encodes entities found as 8-4bit numbers
        Buildings take priortiy if both a bot and building is present
        own core gets reported as empty"""
    nearby = ct.get_nearby_tiles()
    number = 0
    shift = 0
    for dx,dy in offsets:
        tile = Position(pos.x+dx, pos.y+dy)
        if tile in nearby: #This offset is a square on the board
            entity_id = ct.get_tile_building_id(tile)
            if entity_id is None: entity_id = ct.get_tile_builder_bot_id(tile)
            if entity_id is not None: #We found something
                entity = ct.get_entity_type(entity_id)
                is_opponents = ct.get_team() != ct.get_team(entity_id)
                entity_n = ENTITIES_CODE[entity] + 8 * is_opponents
                number += entity_n << shift
        shift += 4
    return number

def parse_entities(number: int) -> list[int]:
    """Convert a u32 number into an ordered list of 8 ints [0-15] that represent entities in offset positions"""
    entities = []
    for shift in range(0,32,4):
        entity_n = (number & 15 << shift) >> shift
        entities.append(entity_n)
    return entities

def encode_scout(pos: Position, direc: Direction | None, ct: Controller) -> int:
    """Moving a bot one step brings 9 new tiles into vision range, the encoded number stores
    the bots final position (10-bits), the direction it moved (2-bits) and the terrain at the 9 tiles (2*9=18-bit)

    A builder that stood still still reports its position, with no terrain bits
    set. scouter2 wrote a bare 0 here, which decoded to Position(0, 0) and made
    the core stamp that builder's entity readings onto the map origin.
    """
    number = (pos.x<<25) + (pos.y<<20)
    if direc is None:
        return number

    nearby = ct.get_nearby_tiles()
    direc_n = CARDINALS.index(direc)
    offsets = SCOUT_EDGE_OFFSETS[direc_n]
    number += (direc_n<<18)

    shift = 16
    for dx,dy in offsets:
        tile = Position(pos.x+dx, pos.y+dy)
        if tile in nearby:
            env_n = Environments.index(ct.get_tile_env(tile))
            number += env_n<<shift
        shift -= 2

    return number

def encode_game_data(bots_made: int, opp_core_bottom_right: Position,
                     ore_hint: Position | None = None) -> int:
    """Encodes game data.

    Bits 0-14 are the original payload; bits 15-25 carry one ore tile the core
    knows about. The core sees every builder's scouting, an individual builder
    sees only its own, so without this a builder plans against a fraction of the
    ore on the map -- and one tile per turn is more than enough to catch up.
    """
    data_number = bots_made
    if opp_core_bottom_right is not None:
        data_number += (opp_core_bottom_right.x << 10) + (opp_core_bottom_right.y << 5)
    return data_number + (encode_claim(ore_hint) << 15)

def parse_ore_hint(ct: Controller) -> Position | None:
    return parse_claim((ct.read_store(SLOT_GAME_DATA) >> 15) & 2047)

def parse_game_data(ct: Controller) -> list[int|Position]:
    """Reads the store and returns the number of bots made and the opponent core"""
    data_number = ct.read_store(SLOT_GAME_DATA)
    builders_made = data_number & 31
    opp_core_bottom_right_x = (data_number & (31 << 10)) >> 10
    opp_core_bottom_right_y = (data_number & (31 << 5)) >> 5
    return [builders_made, Position(opp_core_bottom_right_x, opp_core_bottom_right_y)]

def encode_claim(ore: Position | None) -> int:
    """0 means 'no claim'; the +1 keeps Position(0, 0) distinguishable from it."""
    if ore is None: return 0
    return 1 + ore.x + (ore.y << 5)

def parse_claim(number: int) -> Position | None:
    if number <= 0: return None
    number -= 1
    return Position(number & 31, (number >> 5) & 31)

def encode_report(claim_ore: Position | None, laid_belt: Position | None) -> int:
    return encode_claim(claim_ore) + (encode_claim(laid_belt) << CLAIM_BITS)

def parse_report(number: int) -> tuple[Position | None, Position | None]:
    mask = (1 << CLAIM_BITS) - 1
    return parse_claim(number & mask), parse_claim((number >> CLAIM_BITS) & mask)

def parse_scout(number: int) -> tuple[Position, dict[Position, Environment]]:
    """Unpack u32 into a position of the scouting bot and 9 environment data-pairs for the scouting edge"""
    x = (number & 31<<25) >> 25
    y = (number & 31<<20) >> 20
    direc_n = (number & 3<<18) >> 18 #NSEW
    offsets = SCOUT_EDGE_OFFSETS[direc_n]
    tiles: dict[Position, Environment] = {}
    shift = 16
    for dx,dy in offsets:
        env_n = (number & 3<<shift) >> shift
        if env_n > 0:
            tiles.update({Position(x+dx, y+dy): Environments[env_n]})
        shift-=2
    return Position(x,y), tiles

def read_stored_scout(starting_store_index: int, stored_map: Map, ct: Controller) -> Position:
    """Reads data from ct.store (starting_index and decrementing) into the stored map and resets store-slots"""
    raw = ct.read_store(starting_store_index)
    bot_pos, scouted_env = parse_scout(raw)
    close_entities = parse_entities(ct.read_store(starting_store_index - 1))
    far_entities = parse_entities(ct.read_store(starting_store_index - 2))
    ct.write_store(starting_store_index, 0)
    ct.write_store(starting_store_index - 1, 0)
    ct.write_store(starting_store_index - 2, 0)
    if raw == 0:  # that builder has not reported yet -- do not stamp the origin
        return bot_pos
    for tile, env in scouted_env.items():
        stored_map.set_environment_at(tile, env)

    for i in range(8):
        dx, dy = SCOUT_CLOSE_CROSS_OFFSETS[i]
        tile = Position(bot_pos.x + dx, bot_pos.y + dy)
        stored_map.set_entity_at(tile, close_entities[i])

        dx, dy = SCOUT_FAR_CROSS_OFFSETS[i]
        tile = Position(bot_pos.x + dx, bot_pos.y + dy)
        stored_map.set_entity_at(tile, far_entities[i])

    return bot_pos


class Player:
    def __init__(self):
        self.am_builder_number = -1
        self.scout_store_slot = -1
        self.claim_slot = -1

        self.bots_made = 0
        self.ammo_needed = 20
        self.ore_cycle: list[Position] = []
        self.ore_index = 0

        self.own_core_tiles = []
        self.opp_core_tiles = []
        self.opp_core_bottom_right = None

        # Pathfinding state
        self.local_map: Map | None = None
        self.current_target: Position | None = None
        self.path: list[Direction] | None = None
        self.moved_direction: Direction | None = None

        # Economy state (builders). `net` is every tile this builder knows to be
        # connected to our core: core tiles, belts it laid, belts it has seen.
        self.net: set[Position] = set()
        self.occupied_ore: set[Position] = set()
        self.blocked: set[Position] = set()
        self.skip_ore: set[Position] = set()
        self.plan = None
        self.plan_dirty = True
        self.stall = 0
        self.claimed: set = set()
        self.laid_belt: Position | None = None
        self.last_plan = -99

    def run(self, ct: Controller) -> None:
        if self.opp_core_bottom_right is None:
            self._learn_opp_core(ct)
        etype = ct.get_entity_type()
        if etype == EntityType.CORE:
            self._run_core(ct)

        elif etype == EntityType.BUILDER_BOT:
            self._run_builder(ct)

        elif etype == EntityType.SENTINEL:
            self._run_sentinel(ct)

    def _run_sentinel(self, ct: Controller) -> None:
        target = None
        for tile in ct.get_attackable_tiles():
            if tile_has_enemy_core(tile, ct):
                target = tile
        if not target:
            for tile in ct.get_attackable_tiles():
                if tile_has_enemy(tile, ct):
                    target = tile
        if target:
            if ct.can_fire(target):
                ct.fire(target)

    # ------------------------------------------------------------------ core

    def _core_configure_map(self, ct: Controller) -> None:
        """Sets the parameters of the ENV_MAP and reads the cores own scouting into it"""
        ENV_MAP.configure(ct.get_map_width(), ct.get_map_height(), ct.get_position())

        for tile in ct.get_nearby_tiles():
            ENV_MAP.set_environment_at(tile, ct.get_tile_env(tile))
            if ct.get_tile_building_id(tile) and ct.get_tile_building_id(tile) == ct.get_id():
                self.own_core_tiles.append(tile)

    def _run_core(self, ct: Controller) -> None:
        if ct.get_global_ammo() < self.ammo_needed:
            if ct.can_convert_ammo(self.ammo_needed):
                ct.convert_ammo(self.ammo_needed)

        if not ENV_MAP.configured:
            self._core_configure_map(ct)

        # The core keeps aggregating scout reports -- not to hand out work any
        # more, but because deducing the enemy core needs a global map.
        for i in range(0, min(3, self.bots_made)):
            read_stored_scout(14 - 4 * i, ENV_MAP, ct)
        if self.bots_made >= 4:
            read_stored_scout(3, ENV_MAP, ct)

        if ENV_MAP.known_symmetry is None:
            if ENV_MAP.discover_symmetry():
                ENV_MAP.deduce_opp_core()
                self.opp_core_tiles = ENV_MAP.opp_core
                self.opp_core_bottom_right = max(self.opp_core_tiles, key=lambda tile: tile.x+tile.y)

        if len(self.opp_core_tiles) == 0:
            if len(ENV_MAP.opp_core) == 4:
                self.opp_core_tiles = ENV_MAP.opp_core
                self.opp_core_bottom_right = max(self.opp_core_tiles, key=lambda tile: tile.x + tile.y)

        if self.bots_made < 4:
            for pos in sorted(ct.get_nearby_tiles(dist_sq=2), key=lambda tile: tile.distance_squared(Position(ct.get_map_width()//2, ct.get_map_height()//2))): #spawn extra bots towards center
                if ct.can_spawn(pos):
                    ct.spawn_builder(pos)
                    self.bots_made += 1
                    break

        elif ct.get_hp() < ct.get_max_hp() and self.bots_made < 6:
            for pos in sorted(ct.get_nearby_tiles(dist_sq=2), key=lambda tile: tile.distance_squared(
                Position(ct.get_map_width() // 2, ct.get_map_height() // 2)), reverse=True):  # spawn extra healers towards back
                if ct.can_spawn(pos):
                    ct.spawn_builder(pos)
                    self.bots_made += 1
                    break

        ct.write_store(SLOT_GAME_DATA, encode_game_data(
            self.bots_made, self.opp_core_bottom_right, self._next_ore_hint()))

    def _next_ore_hint(self) -> Position | None:
        """One known ore tile per turn, cycled, for the builders to pick up."""
        if self.ore_index >= len(self.ore_cycle):
            self.ore_cycle = list(ENV_MAP.unplanned_ore)
            self.ore_index = 0
            if not self.ore_cycle:
                return None
        hint = self.ore_cycle[self.ore_index]
        self.ore_index += 1
        return hint

    # --------------------------------------------------------------- builder

    def _configure_builder(self, ct: Controller) -> None:
        """The builder finds out who it is from store(game_data); the first 3 get a claim slot."""
        game_data = parse_game_data(ct)
        self.am_builder_number = game_data[0]
        if self.am_builder_number < 4:
            self.claim_slot = 19 - 4 * self.am_builder_number
            self.scout_store_slot = 18 - 4 * self.am_builder_number
        elif self.am_builder_number == 4:
            self.scout_store_slot = 3

    def _learn_opp_core(self, ct: Controller) -> None:
        game_data = parse_game_data(ct)
        discovered_bottom_core = game_data[1]
        if self.opp_core_bottom_right is None and discovered_bottom_core != Position(0,0):
            self.opp_core_bottom_right = discovered_bottom_core
            for dx in 0, -1:
                for dy in 0, -1:
                    self.opp_core_tiles.append(Position(discovered_bottom_core.x + dx, discovered_bottom_core.y + dy))

    def _observe(self, ct: Controller) -> None:
        """Fold everything in vision into the local map, the network and the blocklists."""
        for tile in ct.get_nearby_tiles():
            env = ct.get_tile_env(tile)
            before = self.local_map.get_environment_at(tile)
            self.local_map.set_environment_at(tile, env)
            if before != env:
                self.plan_dirty = True

            # Solidity is tracked separately from network membership: core
            # tiles are connected *and* impassable, and routing paths through
            # them once froze builders for the rest of the game. Belts are the
            # only buildings you can walk over.
            building_id = ct.get_tile_building_id(tile)
            if building_id is None:
                if tile in self.net:
                    self.net.discard(tile)      # a belt of ours was destroyed
                    self.plan_dirty = True
                self.occupied_ore.discard(tile)
                solid = env == Environment.WALL
            else:
                etype = ct.get_entity_type(building_id)
                mine = ct.get_team(building_id) == ct.get_team()
                solid = etype not in NETWORK_TYPES
                if mine and etype in NETWORK_TYPES:
                    if tile not in self.net:
                        self.net.add(tile)
                        self.plan_dirty = True
                elif mine and etype == EntityType.CORE:
                    self.net.add(tile)
                    if tile not in self.own_core_tiles:
                        self.own_core_tiles.append(tile)
                elif etype == EntityType.HARVESTER:
                    self.occupied_ore.add(tile) # that ore is taken, by either team

            if solid != (tile in self.blocked):
                self.blocked.symmetric_difference_update((tile,))
                self.plan_dirty = True

    def _read_reports(self, ct: Controller) -> set:
        """Absorb team-mates' new belts into our network; return their ore claims.

        Adding a belt we have not seen is safe: everyone builds under the same
        rule (only ever adjacent to something already connected), so anything a
        team-mate laid is connected to the core by construction.
        """
        claimed = set()
        for slot in CLAIM_SLOTS:
            if slot == self.claim_slot:
                continue
            ore, belt = parse_report(ct.read_store(slot))
            if ore is not None:
                claimed.add(ore)
            if belt is not None and belt not in self.net:
                self.net.add(belt)
                self.blocked.discard(belt)
                self.plan_dirty = True
        return claimed

    def _replan(self, ct: Controller) -> None:
        self.last_plan = ct.get_current_round()
        was = self.plan.ore if self.plan else None
        self.plan = plan_extension(
            self.local_map, self.net, self.local_map.unplanned_ore,
            self.occupied_ore, self.blocked, ct.get_position(),
            self.skip_ore, self.claimed, max_belts=MAX_BELTS, max_walk=MAX_WALK)
        self.plan_dirty = False
        # Only a genuinely new objective resets the patience counter. Replanning
        # happens most turns (a team-mate lays a belt, a tile comes into view),
        # so zeroing it here made the give-up rule unreachable and let a wedged
        # builder retry the same impossible step forever.
        if self.plan is None or self.plan.ore != was:
            self.stall = 0

    def _abandon(self, ct: Controller) -> None:
        """Give up on the current ore and pick something else next turn."""
        if self.plan is not None:
            self.skip_ore.add(self.plan.ore)
        self.plan = None
        self.plan_dirty = True
        self.stall = 0

    def _run_economy(self, ct: Controller) -> bool:
        """Returns True if this builder has economic work (acted, moved, or is waiting on money)."""
        pos = ct.get_position()

        # (a) Adjacent ore that already touches the network -- build on it.
        for tile in adjacent_tiles(pos):
            if tile in self.occupied_ore:
                continue
            if self.local_map.get_environment_at(tile) != Environment.ORE_TITANIUM:
                continue
            if not any(n in self.net for n in adjacent_tiles(tile)):
                continue
            if ct.can_build_harvester(tile):
                ct.build_harvester(tile)
                self.occupied_ore.add(tile)
                self.blocked.add(tile)
                self.plan = None
                self.plan_dirty = True
                self.stall = 0
                return True
            # Refused only because we are broke or on the action cooldown:
            # hold the spot for a while rather than wander off and come back.
            self.stall += 1
            if self.stall > STALL_LIMIT * 3:
                self._abandon(ct)
            return True

        if self.plan is None or (
                self.plan_dirty
                and ct.get_current_round() - self.last_plan >= REPLAN_EVERY):
            self._replan(ct)
        if self.plan is None:
            return False

        # (b) Lay the next belt of the plan. It always points back at the tile
        #     it hooks onto, so titanium flows toward the core down every branch.
        if self.plan.belts:
            head = self.plan.belts[0]
            if head in adjacent_tiles(pos):
                flow = head.cardinal_direction_to(self.plan.anchor)
                if ct.can_build_conveyor(head, flow):
                    ct.build_conveyor(head, flow)
                    self.net.add(head)
                    self.laid_belt = head
                    self.plan.belts.pop(0)
                    self.plan.anchor = head
                    self.stall = 0
                    return True
                if ct.get_global_resources() < ct.get_conveyor_cost():
                    self.stall += 1     # just poor; hold the spot rather than wander
                    if self.stall > STALL_LIMIT * 3:
                        self._abandon(ct)
                    return True
                if ct.get_tile_builder_bot_id(head) is not None:
                    self.stall += 1     # a team-mate is standing there; it will move
                    if self.stall > STALL_LIMIT:
                        self._abandon(ct)
                    return True
                # Something is already built on the site. If it is one of our
                # own belts a team-mate got there first, which is fine; anything
                # else is an obstacle. Either way this plan is dead -- drop it
                # now rather than re-attempting a refused build until the replan
                # timer happens to come round.
                if head not in self.net:
                    self.blocked.add(head)
                self.plan = None
                self.plan_dirty = True
                self.stall = 0
                return True
            site = head
        else:
            site = self.plan.ore        # network already reaches it; go build on it

        # (c) Walk at the build site. We stop one short of it, because the
        #     adjacency branches above fire before this one ever runs again.
        if not any(self._passable(n) for n in adjacent_tiles(site)):
            self._abandon(ct)       # walled in; nothing to build from
            return True
        self._bot_pathfind(site, ct)
        if self.moved_direction is None:
            self.stall += 1
            if self.stall > STALL_LIMIT:
                self._abandon(ct)
        else:
            self.stall = 0
        return True

    def _passable(self, tile: Position) -> bool:
        """Can a builder stand here, as far as this builder knows?"""
        if not (0 <= tile.x < self.local_map.width and 0 <= tile.y < self.local_map.height):
            return False
        if self.local_map.get_environment_at(tile) == Environment.WALL:
            return False
        return tile not in self.blocked

    def _bot_pathfind(self, target: Position, ct: Controller) -> None:
        """Navigate toward target using BFS pathfinding with greedy fallback.

        scouter2 popped the next step off the cached path whether or not the
        move happened. Builders move on a cooldown, so on every cooldown turn a
        step was silently thrown away and the rest of the path pointed at
        nonsense -- one builder sat on the same tile from turn 20 to turn 83.
        Consume a step only when the move succeeds.
        """
        pos = ct.get_position()

        if target != self.current_target or not self.path:
            self.current_target = target
            self.path = bfs_path(self.local_map, pos, target, max_nodes=800, blocked=self.blocked)

        direction = self.path[0] if self.path else None
        if direction is None and target and target != pos:
            direction = pos.cardinal_direction_to(target)   # greedy fallback
        if direction is None or direction == Direction.CENTRE:
            return

        if ct.can_move(direction):
            ct.move(direction)
            self.moved_direction = direction
            if self.path and self.path[0] == direction:
                self.path.pop(0)
        elif ct.get_move_cooldown() == 0:
            self.path = None    # not cooldown, so genuinely blocked -- reroute

    def _push_to_opposite_corner(self, ct: Controller) -> None:
        if not self.own_core_tiles:
            return
        core_tile = self.own_core_tiles[0]
        other_side_x = ct.get_map_width() - core_tile.x
        other_side_y = ct.get_map_height() - core_tile.y
        self._bot_pathfind(Position(other_side_x, other_side_y), ct)

    def _bot_without_orders(self, ct: Controller) -> None:
        """No economic work in reach: press the siege. Unchanged from scouter2."""
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

        open_dirs = [
            d for d in CARDINALS
            if ct.can_move(d) and ct.get_tile_env(pos.add(d)) == Environment.EMPTY
        ]
        move_options = open_dirs or [d for d in CARDINALS if ct.can_move(d)]
        if move_options:
            direction = random.choice(move_options)
            ct.move(direction)
            self.moved_direction = direction

    def _report_to_store(self, ct: Controller) -> None:
        """Writes scout data to ct.store"""
        if self.scout_store_slot < 0: return
        ct.write_store(self.scout_store_slot, encode_scout(ct.get_position(), self.moved_direction, ct))
        scout_close_entities_n = encode_entities(ct.get_position(), SCOUT_CLOSE_CROSS_OFFSETS, ct)
        scout_far_entities_n = encode_entities(ct.get_position(), SCOUT_FAR_CROSS_OFFSETS, ct)
        ct.write_store(self.scout_store_slot - 1, scout_close_entities_n)
        ct.write_store(self.scout_store_slot - 2, scout_far_entities_n)

    def _publish_report(self, ct: Controller) -> None:
        if self.claim_slot < 0: return
        ct.write_store(self.claim_slot,
                       encode_report(self.plan.ore if self.plan else None, self.laid_belt))

    def _run_builder(self, ct: Controller) -> None:
        self.moved_direction = None
        if self.am_builder_number < 0: self._configure_builder(ct)

        if self.local_map is None:
            self.local_map = Map()
            self.local_map.configure(ct.get_map_width(), ct.get_map_height(), ct.get_position())

        self.laid_belt = None
        self._observe(ct)
        hint = parse_ore_hint(ct)
        if hint is not None and self.local_map.get_environment_at(hint) != Environment.ORE_TITANIUM:
            self.local_map.set_environment_at(hint, Environment.ORE_TITANIUM)
            self.plan_dirty = True
        self.claimed = self._read_reports(ct)

        working = False
        if self.am_builder_number in ECON_BUILDERS:
            working = self._run_economy(ct)
        if not working:
            self.plan = None
            self._bot_without_orders(ct)

        self._publish_report(ct)
        if self.scout_store_slot > 0: self._report_to_store(ct)
