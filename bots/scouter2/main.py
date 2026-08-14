import random

from fcode import Controller, Team, EntityType, Environment, Direction, Position, GameError

from mapclass import Map

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
0 (GAME DATA): builders_made (5-bit)

1 UNUSED
2 UNUSED
3 UNUSED

4-7 (B3)
8-11 (B2)
12 (B1): Entities scout far (32-bit)
13 (B1): Entities scout close (32-bit)
14 (B1): Environment scout (32-bit)
15 (B1): Buildorder (31-bit)
"""



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

def encode_game_data(bots_made: int) -> int:
    return bots_made

def parse_game_data(ct: Controller) -> list[int]:
    """Reads the store and returns (currently only) the number of bots made"""
    data_number = ct.read_store(SLOT_GAME_DATA)
    builders_made = data_number & 31
    return [builders_made]

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

def read_stored_scout(starting_store_index: int, stored_map: Map, ct: Controller):
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

    def run(self, ct: Controller) -> None:
        etype = ct.get_entity_type()
        if etype == EntityType.CORE:
            self._run_core(ct)

        elif etype == EntityType.BUILDER_BOT:
            print(f"{self.am_builder_number=}, {self.build_stage=}, {self.build_order_slot=}", flush=True)
            self._run_builder(ct)
            
    def _core_configure_map(self, ct: Controller) -> None:
        """Sets the parameters of the ENV_MAP and reads the cores own scouting into it"""
        ENV_MAP.configure(ct.get_map_width(), ct.get_map_height(), ct.get_position())

        for tile in ct.get_nearby_tiles():
            ENV_MAP.set_environment_at(tile, ct.get_tile_env(tile))
            ct.draw_indicator_dot(tile, 0, 255, 0)

        ENV_MAP.update_conveyor_distance_grid()
            
    def _run_core(self, ct: Controller) -> None:
        if not ENV_MAP.configured:
            self._core_configure_map(ct)

        for i in range(0,min(3,self.bots_made)):
            print(f"Reading {i=}")
            scout_slot = 14 - 4*i
            read_stored_scout(scout_slot, ENV_MAP, ct)

        ENV_MAP.update_conveyor_distance_grid()

        for i in range(0,min(3,self.bots_made+1)): #We can plan for the next bot
            print(f"Planning {i=}")
            order_slot = 15 - 4*i
            if ct.read_store(order_slot) == 0 and ENV_MAP.unplanned_ore: #Need order
                possible, go_to, build_direction, conveyor_path = ENV_MAP.plan_easiest_harvester()
                if not possible:
                    print(f"FAILED {go_to}")
                else:
                    print("PLAN MADE")
                    build_order_number = encode_build_order(go_to, EntityType.HARVESTER, build_direction,
                                                            conveyor_path)
                    print(f"{build_order_number=}")
                    ct.write_store(order_slot, build_order_number)

        if self.bots_made < 4:
            for pos in ct.get_nearby_tiles(dist_sq=2):
                if ct.can_spawn(pos):
                    ct.spawn_builder(pos)
                    self.bots_made += 1
                    break

        ct.write_store(SLOT_GAME_DATA,encode_game_data(self.bots_made))


    def _execute_buildplan(self, ct: Controller):
        bot_position = ct.get_position()
        if self.build_stage == 0:  # Has not yet built first conveyor
            print(f"STAGE 0")
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
                moves = sorted(adjacent_tiles(bot_position), key=lambda tile: tile.distance_squared(self.go_to))
                for move in moves:
                    if ct.can_move(bot_position.cardinal_direction_to(move)):
                        ct.move(bot_position.cardinal_direction_to(move))  # TODO handle failure
                        self.moved_direction = bot_position.cardinal_direction_to(move)
                        break

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

    def _configure_builder(self, ct: Controller) -> None:
        """The builder finds out who it is from store(game_data), the first 3 bots get scouting slots and build_orders"""
        game_data = parse_game_data(ct)
        self.am_builder_number = game_data[0]
        if self.am_builder_number < 4:
            self.build_order_slot = 19 - 4 * self.am_builder_number
            self.scout_store_slot = 18 - 4 * self.am_builder_number

    def _read_build_order(self, ct: Controller) -> None:
        """Reads build-order from ct.store"""
        self.go_to, self.build_type_n, self.build_direction, self.conveyor_path = parse_build_order(ct.read_store(self.build_order_slot))
        self.build_stage, self.path_index = 0,0

    def _bot_without_orders(self, ct: Controller) -> None:
        """When the builder does not have an order it can do this"""
        pos = ct.get_position()
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

        if self.build_stage < 0 and self.build_order_slot > 0: #Has no build order, and wants one
            if ct.read_store(self.build_order_slot) > 0:
                self._read_build_order(ct)
            else:
                print(f"BUILDER {self.am_builder_number} DID NOT FIND BUILD-ORDER")

        if self.build_stage >= 0:
            self._execute_buildplan(ct)
        else:
            self._bot_without_orders(ct)

        self._report_to_store(ct)

if __name__ == '__main__':
    bott = Player()
    print(parse_build_order(1478704))