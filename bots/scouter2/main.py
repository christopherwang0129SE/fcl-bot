import random

from fcode import Controller, Team, EntityType, Environment, Direction, Position, GameError

from mapclass import Map

# Builder bots move only in the four cardinal directions.
CARDINALS = [Direction.NORTH, Direction.SOUTH, Direction.EAST, Direction.WEST]
Environments = [0, Environment.EMPTY, Environment.WALL, Environment.ORE_TITANIUM]
ENV_MAP = Map()
SCOUT_DATA1 = 15
BUILD_ORDER1 = 12

#4 groups of 9 offsets reprsenting the edge of the scouted area after moving NSEW
SCOUT_EDGE_OFFSETS = [[(-4,-2), (-3,-3), (-2,-4), (-1,-4), (0,-4), (1,-4), (2,-4), (3,-3), (4,-2)],
           [(-4,2), (-3,3), (-2,4), (-1,4), (0,4), (1,4), (2,4), (3,3), (4,2)],
           [(2,4), (3,3), (4,2), (4,1), (4,0), (4,-1), (4,-2), (3,-3), (2,-4)],
           [(-2,4), (-3,3), (-4,2), (-4,1), (-4,0), (-4,-1), (-4,-2), (-3,-3), (-2,-4)]]

#8 offsets to of the cross around position
SCOUT_CROSS_OFFSETS = [(-2,0), (-1,0), (1,0), (2,0), (0,2), (0,1), (0,-2), (0,-1)]

ENTITIES_CODE = {EntityType.BUILDER_BOT: 1, EntityType.GUNNER: 2, EntityType.SENTINEL: 3,
                 EntityType.LAUNCHER: 4, EntityType.HARVESTER: 5, EntityType.CONVEYOR: 6,
                 EntityType.SPLITTER: 6, EntityType.BARRIER: 7, EntityType.CORE: 0}

def adjacent_tiles(tile: Position) -> list[Position]:
    return [tile.add(direction) for direction in CARDINALS]

def encode_entities(pos: Position, ct: Controller) -> int:
    """Looks at the 8 tiles in the center-less cross and encodes entities found as 8-4bit numbers
        Buildings take priortiy if both a bot and building is present
        own core gets reported as empty"""
    nearby = ct.get_nearby_tiles()
    number = 0
    shift = 0
    for dx,dy in SCOUT_CROSS_OFFSETS:
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
    """Convert a u32 number into an ordered list of 8 ints [0-15] that represent enteties if offset positions"""
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
    entities = parse_entities(ct.read_store(starting_store_index - 1))
    ct.write_store(starting_store_index, 0)
    ct.write_store(starting_store_index - 1, 0)
    for tile, env in scouted_env.items():
        stored_map.set_environment_at(tile, env)
        ct.draw_indicator_dot(tile, 0, 255, 0)

    for i in range(8):
        dx, dy = SCOUT_CROSS_OFFSETS[i]
        tile = Position(bot_pos.x + dx, bot_pos.y + dy)
        stored_map.set_entity_at(tile, entities[i])
        ct.draw_indicator_dot(tile, 0, 0, 255)

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
        self.build_stage: int = -1
        self.path_index: int = 0
        self.conveyor_path: list[Direction] = []
        self.build_direction: Direction|None = None
        self.build_type_n: int = 0
        self.follow_path: Direction|None = None

    def run(self, ct: Controller) -> None:
        etype = ct.get_entity_type()
        if etype == EntityType.CORE:
            if not ENV_MAP.configured:
                ENV_MAP.configure(ct.get_map_width(), ct.get_map_height(), ct.get_position())

                for tile in ct.get_nearby_tiles():
                    ENV_MAP.set_environment_at(tile, ct.get_tile_env(tile))
                    ct.draw_indicator_dot(tile, 0, 255, 0)

                ENV_MAP.update_conveyor_distance_grid()

                for pos in ct.get_nearby_tiles(dist_sq=2):
                    if ct.can_spawn(pos):
                        ct.spawn_builder(pos)
                        break

            else:
                read_stored_scout(SCOUT_DATA1, ENV_MAP, ct)
                print(ENV_MAP.unplanned_ore)
                #print(ENV_MAP.environment_str())
                #print(ENV_MAP.entities_str())

            if ct.read_store(BUILD_ORDER1) == 0:
                if ENV_MAP.unplanned_ore:
                    print(ENV_MAP.conveyor_str())
                    possible, go_to, build_direction, conveyor_path = ENV_MAP.plan_easiest_harvester()
                    if not possible:
                        print(f"FAILED {go_to}")
                    else:
                        print("PLAN MADE")
                        build_order_number = encode_build_order(go_to, EntityType.HARVESTER, build_direction, conveyor_path)
                        print(f"{build_order_number=}")
                        ct.write_store(BUILD_ORDER1, build_order_number)

        elif etype == EntityType.BUILDER_BOT:
            print(f"Run builder, stage={self.build_stage}", flush=True)
            self._run_builder(ct)

    def _execute_buildplan(self, ct: Controller):
        bot_position = ct.get_position()
        if self.build_stage == 0:  # Has not yet built first conveyor
            print(f"STAGE 0")
            if bot_position == self.go_to:  # Make any move:
                for direction in CARDINALS:
                    if ct.can_move(direction):
                        ct.move(direction)
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
                        break

        elif self.build_stage == 1:  # Has not built harvester
            print(f"STAGE 1")
            if bot_position != self.go_to:
                desired_move = bot_position.cardinal_direction_to(self.go_to)
                if ct.can_move(desired_move):
                    ct.move(desired_move)  # TODO handle failure
            else:
                if ct.can_build_harvester(self.go_to.add(self.build_direction)):
                    ct.build_harvester(self.go_to.add(self.build_direction))
                    self.build_stage = 2

        elif self.build_stage == 2:  # Has built harvester and first conveyor
            if len(self.conveyor_path) == self.path_index:
                print("BUILD COMPLETE")
                ct.write_store(BUILD_ORDER1,0)
                self.build_stage = -1
                self.follow_path = None
                return True
            if self.follow_path:
                if ct.can_move(self.follow_path):
                    ct.move(self.follow_path)  # TODO else?
                    self.follow_path = None
            else:
                direction_next = self.conveyor_path[self.path_index - 1]
                next_tile = bot_position.add(direction_next)  # pointed from last built conveyor
             
                if ct.can_build_conveyor(next_tile, self.conveyor_path[self.path_index]):
                    ct.build_conveyor(next_tile, self.conveyor_path[self.path_index])
                    self.path_index += 1
                    self.follow_path = direction_next

    def _run_builder(self, ct: Controller) -> None:
        if self.build_stage < 0:
            if ct.read_store(BUILD_ORDER1) > 0:
                self.go_to, self.build_type_n, self.build_direction, self.conveyor_path = parse_build_order(ct.read_store(BUILD_ORDER1))
                self.build_stage = 0
                self.path_index = 0
                print(f"Build loaded: {self.go_to=}\n{self.build_type_n=}\n{self.build_direction}\n{self.conveyor_path}")
                return

        if self.build_stage >= 0:
            self._execute_buildplan(ct)

        else:
            pos = ct.get_position()
            open_dirs = [
                d for d in CARDINALS
                if ct.can_move(d) and ct.get_tile_env(pos.add(d)) == Environment.EMPTY
            ]
            move_options = open_dirs or [d for d in CARDINALS if ct.can_move(d)]
            if move_options:
                direction = random.choice(move_options)
                ct.move(direction)
                print(f"round {ct.get_current_round()}: moved {direction.name} to {ct.get_position()}")
                scout_n = encode_scout(ct.get_position(), direction, ct)
                scout_entities_n = encode_entities(ct.get_position(), ct)
                print(f"{scout_n=}")
                print(f"{scout_entities_n=}")
                ct.write_store(SCOUT_DATA1, scout_n)
                ct.write_store(SCOUT_DATA1-1, scout_entities_n)

if __name__ == '__main__':
    bott = Player()
    print(parse_build_order(1478704))