import random

from fcode import Controller, Team, EntityType, Environment, Direction, Position, GameError

from mapclass import Map
from pathfind import bfs_path

# Builder bots move only in the four cardinal directions.
CARDINALS = [Direction.NORTH, Direction.SOUTH, Direction.EAST, Direction.WEST]
Environments = [0, Environment.EMPTY, Environment.WALL, Environment.ORE_TITANIUM]
ENV_MAP = Map()

SLOT_GAME_DATA = 0


SCOUT_DATA1 = 15
BUILD_ORDER1 = 12

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
15 (B1): Buildorder (31-bit)
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

def tiles_to_attack_core_map_mode(core_tiles: list[Position], map: Map) -> list[Position]:
    tiles = []
    for core_tile in core_tiles:
        possible = tiles_to_attack_with_sentinel_from(core_tile)
        for tile in possible:
            if tile not in core_tiles and map.get_environment_at(tile) == Environment.EMPTY:
                tiles.append(tile)
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


def tiles_in_crosshair(ct: Controller) -> list[Position]:
    facing_dir = ct.get_direction()
    active_tile = ct.get_position().add(facing_dir)
    targets = []
    while ct.is_in_vision(active_tile):
        targets.append(active_tile)
        active_tile = active_tile.add(facing_dir)
    return targets

def tile_has_enemy(tile: Position, ct: Controller) -> bool:
    if ct.get_tile_building_id(tile) and ct.get_team(ct.get_tile_building_id(tile)) != ct.get_team():
        return True
    if ct.get_tile_building_id(tile) and ct.get_team(ct.get_tile_builder_bot_id(tile)) != ct.get_team():
        return True
    return False

def tile_has_enemy_core(tile: Position, ct: Controller) -> bool:
    return ct.get_tile_building_id(tile) and ct.get_team(ct.get_tile_building_id(tile)) != ct.get_team() and ct.get_entity_type(ct.get_tile_building_id(tile)) == EntityType.CORE

def tile_has_friend(tile: Position, ct: Controller) -> bool:
    if ct.get_tile_building_id(tile) and ct.get_team(ct.get_tile_building_id(tile)) == ct.get_team():
        return True
    if ct.get_tile_building_id(tile) and ct.get_team(ct.get_tile_builder_bot_id(tile)) == ct.get_team():
        return True
    return False

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

def encode_scout(pos: Position, direc: Direction, ct: Controller) -> int:
    """Moving a bot one step brings 9 new tiles into vision range, the encoded number stores
    the bots final position (10-bits), the direction it moved (2-bits) and the terrain at the 9 tiles (2*9=18-bit)
    """
    nearby = ct.get_nearby_tiles()
    direc_n = CARDINALS.index(direc)
    offsets = SCOUT_EDGE_OFFSETS[direc_n]

    number = (pos.x<<25) + (pos.y<<20) + (direc_n<<18)

    shift = 16
    for dx,dy in offsets:
        tile = Position(pos.x+dx, pos.y+dy)
        if tile in nearby:
            env_n = Environments.index(ct.get_tile_env(tile))
            number += env_n<<shift
        shift -= 2

    return number

def encode_game_data(bots_made: int, opp_core_bottom_right: Position) -> int:
    """Encodes game data"""
    data_number = bots_made
    if opp_core_bottom_right is not None:
        data_number += (opp_core_bottom_right.x << 10) + (opp_core_bottom_right.y << 5)
    return data_number

def parse_game_data_number(data_number: int):
    builders_made = data_number & 31
    opp_core_bottom_right_x = (data_number & (31 << 10)) >> 10
    opp_core_bottom_right_y = (data_number & (31 << 5)) >> 5
    return [builders_made, Position(opp_core_bottom_right_x, opp_core_bottom_right_y)]

def parse_game_data(ct: Controller) -> list[int|Position]:
    """Reads the store and returns (currently only) the number of bots made"""
    data_number = ct.read_store(SLOT_GAME_DATA)
    builders_made = data_number & 31
    opp_core_bottom_right_x = (data_number & (31 << 10)) >> 10
    opp_core_bottom_right_y = (data_number & (31 << 5)) >> 5
    return [builders_made, Position(opp_core_bottom_right_x, opp_core_bottom_right_y)]

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

def read_stored_env_scout(store_index: int, stored_map: Map, ct: Controller) -> None:
    bot_pos, scouted_env = parse_scout(ct.read_store(store_index))
    ct.write_store(store_index, 0)
    for tile, env in scouted_env.items():
        stored_map.set_environment_at(tile, env)
        ct.draw_indicator_dot(tile, 0, 255, 0)

def read_stored_scout(starting_store_index: int, stored_map: Map, ct: Controller) -> Position:
    """Reads data from ct.store (starting_index and decrementing) into the stored map and resets store-slots"""
    bot_pos, scouted_env = parse_scout(ct.read_store(starting_store_index))
    close_entities = parse_entities(ct.read_store(starting_store_index - 1))
    far_entities = parse_entities(ct.read_store(starting_store_index - 2))
    ct.write_store(starting_store_index, 0)
    ct.write_store(starting_store_index - 1, 0)
    ct.write_store(starting_store_index - 2, 0)
    for tile, env in scouted_env.items():
        stored_map.set_environment_at(tile, env)
        ct.draw_indicator_dot(tile, 0, 255, 0)

    for i in range(8):
        dx, dy = SCOUT_CLOSE_CROSS_OFFSETS[i]
        tile = Position(bot_pos.x + dx, bot_pos.y + dy)
        stored_map.set_entity_at(tile, close_entities[i])
        ct.draw_indicator_dot(tile, 0, 0, 255)

        dx, dy = SCOUT_FAR_CROSS_OFFSETS[i]
        tile = Position(bot_pos.x + dx, bot_pos.y + dy)
        stored_map.set_entity_at(tile, far_entities[i])
        ct.draw_indicator_dot(tile, 255, 0, 255)

    return bot_pos

def encode_build_order(go_to: Position, build_type: EntityType | None, build_direction: Direction, conveyor_path: list[Direction]) -> int:
    build_type_n = {None: 0, EntityType.GUNNER: 1, EntityType.SENTINEL: 2, EntityType.LAUNCHER: 3, EntityType.HARVESTER: 4, EntityType.BARRIER: 5}[build_type]
    build_dir_n = CARDINALS.index(build_direction)
    number = go_to.x + (go_to.y << 5) + (build_type_n << 10) + (build_dir_n << 13)
    if conveyor_path:
        shift = 15
        conveyor_path.append(Direction.opposite(conveyor_path[-1])) # We add termination to path
        for belt_direction in conveyor_path:
            number += CARDINALS.index(belt_direction) << shift
            shift += 2
            if shift >= 30: break
    return number

def parse_build_order(number: int) -> tuple[Position, int, Direction, list[Direction]]:
    go_to_x = (number & 31)
    go_to_y = (number & 31 << 5) >> 5
    build_type_n = (number & 7 << 10) >> 10
    build_dir_n = (number & 3 << 13) >> 13
    conveyor_path_ns = []
    if (number >> 15) > 0:
        for shift in range(15,31,2):
            conveyor_path_ns.append((number & 3 << shift) >> shift)
            if len(conveyor_path_ns) > 1:
                last_two = conveyor_path_ns[-1] + conveyor_path_ns[-2]
                if last_two == 1 or last_two == 5: #If we see NS,SN or EW,WE we terminate
                    conveyor_path_ns.pop()
                    break
    conveyor_path = [CARDINALS[dir_n] for dir_n in conveyor_path_ns]
    return Position(go_to_x, go_to_y), build_type_n, CARDINALS[build_dir_n], conveyor_path

class Player:
    def __init__(self):
        self.am_builder_number = -1
        self.scout_store_slot = -1
        self.build_order_slot = -1

        self.build_stage: int = -1
        self.path_index: int = 0
        self.conveyor_path: list[Direction] = []
        self.build_direction: Direction|None = None
        self.build_type_n: int = 0
        self.follow_path: Direction|None = None

        self.bots_made = 0
        self.ammo_needed = 20
        self.builder_positions: list[Position|None] = [None, None, None]
        self.build_orders_made: list[tuple[Position, int]] = []

        self.own_core_tiles = []
        self.opp_core_tiles = []
        self.opp_core_bottom_right = None

        # Pathfinding state
        self.local_map: Map | None = None
        self.current_target: Position | None = None
        self.path: list[Direction] | None = None

    def run(self, ct: Controller) -> None:

        if self.opp_core_bottom_right is None:
            self._learn_opp_core(ct)
        print(f"{self.opp_core_tiles=}")
        etype = ct.get_entity_type()
        if etype == EntityType.CORE:
            self._run_core(ct)

        elif etype == EntityType.BUILDER_BOT:
            print(f"{self.am_builder_number=}, {self.build_stage=}, {self.build_order_slot=}", flush=True)
            self._run_builder(ct)

        elif etype == EntityType.SENTINEL:
            self._run_sentinel(ct)

    def _run_sentinel(self, ct: Controller) -> None:
        if self.opp_core_tiles is None:
            self._configure_turret(ct)
        target = None
        print(f"attackable: {ct.get_attackable_tiles()}")
        for tile in ct.get_attackable_tiles():
            if tile_has_enemy_core(tile, ct):
                target = tile
        if not target:
            for tile in ct.get_attackable_tiles():
                if tile_has_enemy(tile, ct):
                    target = tile
        print(f"target={target}")
        if target:
            if ct.can_fire(target):
                ct.fire(target)

    def _configure_turret(self, ct: Controller) -> None:
        game_data = parse_game_data(ct)
        discovered_bottom_core = game_data[1]
        if self.opp_core_bottom_right is None and discovered_bottom_core != Position(0, 0):
            self.opp_core_bottom_right = game_data[1]
            for dx in 0, -1:
                for dy in 0, -1:
                    self.opp_core_tiles.append(
                        Position(discovered_bottom_core.x + dx, discovered_bottom_core.y + dy))


            
    def _core_configure_map(self, ct: Controller) -> None:
        """Sets the parameters of the ENV_MAP and reads the cores own scouting into it"""
        ENV_MAP.configure(ct.get_map_width(), ct.get_map_height(), ct.get_position())

        for tile in ct.get_nearby_tiles():
            ENV_MAP.set_environment_at(tile, ct.get_tile_env(tile))
            ct.draw_indicator_dot(tile, 0, 255, 0)
            if ct.get_tile_building_id(tile) and ct.get_tile_building_id(tile) == ct.get_id():
                self.own_core_tiles.append(tile)
        ENV_MAP.update_conveyor_distance_grid()
            
    def _run_core(self, ct: Controller) -> None:

        if ct.get_global_ammo() < self.ammo_needed:
            if ct.can_convert_ammo(self.ammo_needed):
                ct.convert_ammo(self.ammo_needed)

        if not ENV_MAP.configured:
            self._core_configure_map(ct)

        for i in range(0,min(3,self.bots_made)):
            scout_slot = 14 - 4*i
            self.builder_positions[i] = read_stored_scout(scout_slot, ENV_MAP, ct)
            read_stored_scout(3, ENV_MAP, ct) #Bot 4 is special

        ENV_MAP.update_conveyor_distance_grid()
        if ENV_MAP.known_symmetry is None:
            if ENV_MAP.discover_symmetry():
                ENV_MAP.deduce_opp_core()
                self.opp_core_tiles = ENV_MAP.opp_core
                self.opp_core_bottom_right = max(self.opp_core_tiles, key=lambda tile: tile.x+tile.y)

        if len(self.opp_core_tiles)==0:
            if len(ENV_MAP.opp_core)==4:
                self.opp_core_tiles = ENV_MAP.opp_core
                self.opp_core_bottom_right = max(self.opp_core_tiles, key=lambda tile: tile.x + tile.y)


        print(f"{ENV_MAP.known_symmetry=}")

        for i in range(0,3-len(self.build_orders_made)):
            if not ENV_MAP.unplanned_ore: break
            possible, go_to, build_direction, conveyor_path = ENV_MAP.plan_easiest_harvester()
            if not possible:
                print(f"FAILED {go_to}")
            else:
                print(f"PLAN MADE {go_to=}")
                build_order_number = encode_build_order(go_to, EntityType.HARVESTER, build_direction,
                                                        conveyor_path)
                self.build_orders_made.append((go_to,build_order_number))
                for ticket in self.build_orders_made:
                    if ticket is not None: ct.draw_indicator_dot(ticket[0], 255, 0,0)

        for i in range(0,min(3,self.bots_made+1)):#Plan also the new bot
            order_slot = 15 - 4*i
            if ct.read_store(order_slot) == 0:  # Need order
                bot_pos = self.builder_positions[i] if self.builder_positions[i] else ct.get_position() #core position
                dist = 63
                best_ticket = None
                for ticket in self.build_orders_made:
                    ticket_distance = ticket[0].distance_squared(bot_pos)
                    if ticket_distance < dist:
                        dist = ticket_distance
                        best_ticket = ticket
                if best_ticket:
                    print(f"Assigning builder_bot {i + 1}: {best_ticket[0]}")
                    ct.write_store(order_slot, best_ticket[1])
                    if i == self.bots_made:
                        for tile in sorted(ct.get_nearby_tiles(dist_sq=2), key=lambda tile: tile.distance_squared(best_ticket[0])):
                            if ct.can_spawn(tile):
                                ct.spawn_builder(tile)
                                self.bots_made += 1
                                break
                    self.build_orders_made.remove(best_ticket)

        if self.bots_made < 4:
            for pos in sorted(ct.get_nearby_tiles(dist_sq=2), key=lambda tile: tile.distance_squared(Position(ct.get_map_width()//2, ct.get_map_height()//2))): #spawn extra bots towards center
                if ct.can_spawn(pos):
                    ct.spawn_builder(pos)
                    self.bots_made += 1
                    break

        if ct.get_hp() < ct.get_max_hp() and self.bots_made < 6:
            for pos in sorted(ct.get_nearby_tiles(dist_sq=2), key=lambda tile: tile.distance_squared(
                Position(ct.get_map_width() // 2, ct.get_map_height() // 2)), reverse=True):  # spawn extra healers towards back
                if ct.can_spawn(pos):
                    ct.spawn_builder(pos)
                    self.bots_made += 1
                    break

        #print(f"GAME_DATA: {self.bots_made=} CBR: {self.opp_core_bottom_right} Nr:{encode_game_data(self.bots_made, self.opp_core_bottom_right)}")
        ct.write_store(SLOT_GAME_DATA,encode_game_data(self.bots_made, self.opp_core_bottom_right))

    def _generate_move_path(self, target: Position, ct: Controller) -> Direction:
            bot_pos = ct.get_position()
            visible_tiles = ct.get_nearby_tiles()
            opened = sorted([tile for tile in adjacent_tiles(bot_pos) if tile in visible_tiles and ct.is_tile_passable(tile)], key=lambda tile: tile.distance_squared(target), reverse=True)
            if target in opened: return bot_pos.cardinal_direction_to(target)
            parents = {}
            for tile in opened: parents[tile] = bot_pos
            path = []

            while opened:
                active_tile = opened.pop()
                #print(f"{active_tile=}")
                neighbors = [tile for tile in adjacent_tiles(active_tile) if tile in visible_tiles and ct.is_tile_passable(tile)]
                for tile in neighbors:
                    if tile not in parents and tile not in opened:
                        parents[tile] = active_tile
                        opened.append(tile)
                if target in parents:
                    tile = target
                    while tile in parents:
                        path.append(tile)
                        tile = parents[tile]
                    print(f"Generated path: {path}")
                    return bot_pos.cardinal_direction_to(path.pop())
                opened.sort(key=lambda tile: tile.distance_squared(target), reverse=True)
            return False

    def _bot_pathfind(self, target: Position, ct: Controller) -> None:
        """Navigate toward target using BFS pathfinding with greedy fallback."""
        pos = ct.get_position()

        # If target changed, recompute path via BFS
        if target != self.current_target or not self.path:
            self.current_target = target
            self.path = bfs_path(self.local_map, pos, target, max_nodes=500)

        # Follow the path if we have one
        direction = None
        if self.path:
            direction = self.path.pop(0)

        # Fallback: greedy cardinal step if no path found
        if direction is None and target and target != pos:
            direction = pos.cardinal_direction_to(target)

        # Try to move
        if direction and direction != Direction.CENTRE and ct.can_move(direction):
            ct.move(direction)
            self.moved_direction = direction


    def _execute_buildplan(self, ct: Controller):
        bot_position = ct.get_position()
        if self.build_stage == 0 and len(self.conveyor_path) == 0: self.build_stage = 1
        if self.build_stage == 0:  # Has not yet built first conveyor
            print(f"STAGE 0, {self.go_to=}")
            if bot_position == self.go_to:  # Make any move:
                for direction in CARDINALS:
                    if ct.can_move(direction):
                        ct.move(direction)
                        self.moved_direction = direction
                        break

            elif self.go_to in adjacent_tiles(bot_position):
                if ct.can_build_conveyor(self.go_to, self.conveyor_path[self.path_index]):
                    ct.build_conveyor(self.go_to, self.conveyor_path[self.path_index])
                    self.path_index += 1
                    self.build_stage = 1
                else:
                    blocked_by_id = ct.get_tile_building_id(bot_position.add(self.build_direction))
                    if blocked_by_id and (ct.get_team() != ct.get_team(blocked_by_id)):
                        if ct.can_fire(bot_position.add(self.build_direction)):
                            ct.fire(bot_position.add(self.build_direction))
            else:
                self._bot_pathfind(self.go_to, ct)

        elif self.build_stage == 1:  # Has not built harvester
            print(f"STAGE 1")
            if bot_position != self.go_to:
                desired_move = bot_position.cardinal_direction_to(self.go_to)
                if ct.can_move(desired_move):
                    ct.move(desired_move)  # TODO handle failure
                    self.moved_direction = desired_move
            else:
                if ct.can_build_harvester(self.go_to.add(self.build_direction)):
                    ct.build_harvester(self.go_to.add(self.build_direction))
                    self.build_stage = 2
                else:
                    blocked_by_id = ct.get_tile_building_id(bot_position.add(self.build_direction))
                    if blocked_by_id and (ct.get_team() != ct.get_team(blocked_by_id)):
                        if ct.can_fire(bot_position.add(self.build_direction)):
                            ct.fire(bot_position.add(self.build_direction))

        elif self.build_stage == 2:  # Has built harvester and first conveyor
            if len(self.conveyor_path) == self.path_index:
                print("BUILD COMPLETE")
                ct.write_store(self.build_order_slot,0)
                self.build_stage = -1
                self.follow_path = None
                return True
            if self.follow_path:
                if ct.can_move(self.follow_path):
                    ct.move(self.follow_path)  # TODO else?
                    self.moved_direction = self.follow_path
                    self.follow_path = None

            else:
                direction_next = self.conveyor_path[self.path_index - 1]
                next_tile = bot_position.add(direction_next)  # pointed from last built conveyor

                if ct.can_build_conveyor(next_tile, self.conveyor_path[self.path_index]):
                    ct.build_conveyor(next_tile, self.conveyor_path[self.path_index])
                    self.path_index += 1
                    self.follow_path = direction_next
                    if len(self.conveyor_path) == self.path_index:
                        print("BUILD COMPLETE")
                        ct.write_store(self.build_order_slot, 0)
                        self.build_stage = -1
                        self.follow_path = None
                        return True
                else:
                    blocked_by_id = ct.get_tile_building_id(bot_position.add(self.build_direction))
                    if blocked_by_id and (ct.get_team() != ct.get_team(blocked_by_id)):
                        if ct.can_fire(bot_position.add(self.build_direction)):
                            ct.fire(bot_position.add(self.build_direction))

    def _configure_builder(self, ct: Controller) -> None:
        """The builder finds out who it is from store(game_data), the first 3 bots get scouting slots and build_orders"""
        game_data = parse_game_data(ct)
        self.am_builder_number = game_data[0]
        if self.am_builder_number < 4:
            self.build_order_slot = 19 - 4 * self.am_builder_number
            self.scout_store_slot = 18 - 4 * self.am_builder_number
        elif self.am_builder_number == 4:
            self.scout_store_slot = 3
        if not self.own_core_tiles:
            for tile in ct.get_nearby_tiles():
                if id := ct.get_tile_building_id(tile):
                    if ct.get_entity_type(id) == EntityType.CORE:
                        if ct.get_team(id):
                            self.own_core_tiles.append(tile)
        print(f"{self.own_core_tiles}")

    def _learn_opp_core(self, ct: Controller) -> None:

        game_data = parse_game_data(ct)
        discovered_bottom_core = game_data[1]
        print(f"LEARNING OPP CORE old:{self.opp_core_bottom_right}, new:{discovered_bottom_core}")
        if self.opp_core_bottom_right is None and discovered_bottom_core != Position(0,0):
            self.opp_core_bottom_right = discovered_bottom_core
            for dx in 0, -1:
                for dy in 0, -1:
                    self.opp_core_tiles.append(Position(discovered_bottom_core.x + dx, discovered_bottom_core.y + dy))

    def _read_build_order(self, ct: Controller) -> None:
        """Reads build-order from ct.store"""
        self.go_to, self.build_type_n, self.build_direction, self.conveyor_path = parse_build_order(ct.read_store(self.build_order_slot))
        self.build_stage, self.path_index = 0,0

    def _push_to_opposite_corner(self, ct: Controller) -> None:
        core_tile = self.own_core_tiles[0]
        other_side_x = ct.get_map_width() - core_tile.x
        other_side_y = ct.get_map_height() - core_tile.y
        self._bot_pathfind(Position(other_side_x, other_side_y), ct)

    def _bot_without_orders(self, ct: Controller) -> None:
        """When the builder does not have an order it can do this"""
        print("BOT WITHOUT ORDERS")
        pos = ct.get_position()

        if self.opp_core_bottom_right is None:
            self._push_to_opposite_corner(ct)

        for tile in adjacent_tiles(pos):
            if ct.can_heal(tile):
                print("HEALER")
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
            for tile in attack_tiles:
                ct.draw_indicator_dot(tile, 255,255,0)
            best_tile = min(attack_tiles, key=lambda tile: tile.distance_squared(pos))
            ct.draw_indicator_dot(best_tile, 255, 155, 255)
            print(f"Staging {best_tile=}")
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
            print(f"round {ct.get_current_round()}: moved {direction.name} to {ct.get_position()}")

    def _report_to_store(self, ct: Controller) -> None:
        """Writes scout data to ct.store"""
        if self.scout_store_slot < 0: return
        if self.moved_direction is None: #Write only environment-scout if moved
            ct.write_store(self.scout_store_slot, 0)
        else:
            scout_n = encode_scout(ct.get_position(), self.moved_direction, ct)
            ct.write_store(self.scout_store_slot, scout_n)
        scout_close_entities_n = encode_entities(ct.get_position(), SCOUT_CLOSE_CROSS_OFFSETS, ct)
        scout_far_entities_n = encode_entities(ct.get_position(), SCOUT_FAR_CROSS_OFFSETS, ct)
        ct.write_store(self.scout_store_slot - 1, scout_close_entities_n)
        ct.write_store(self.scout_store_slot - 2, scout_far_entities_n)

    def _run_builder(self, ct: Controller) -> None:
        self.moved_direction = None
        if self.am_builder_number < 0: self._configure_builder(ct)

        # Initialize local map on first run
        if self.local_map is None:
            self.local_map = Map()
            self.local_map.configure(ct.get_map_width(), ct.get_map_height(), ct.get_position())

        # Update local map from nearby visible tiles
        for tile in ct.get_nearby_tiles():
            env = ct.get_tile_env(tile)
            self.local_map.set_environment_at(tile, env)

        if self.build_stage < 0 and self.build_order_slot > 0: #Has no build order, and wants one
            if ct.read_store(self.build_order_slot) > 0:
                self._read_build_order(ct)
            else:
                print(f"BUILDER {self.am_builder_number} DID NOT FIND BUILD-ORDER")

        if self.build_stage >= 0:
            self._execute_buildplan(ct)
        else:
            self._bot_without_orders(ct)

        if self.scout_store_slot > 0: self._report_to_store(ct)

if __name__ == '__main__':
    bott = Player()
    print(tiles_to_attack_with_sentinel_from(Position(0,0)))