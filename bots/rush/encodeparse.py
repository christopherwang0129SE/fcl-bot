from fcode import Controller, Team, EntityType, Environment, Direction, Position, GameError
from mapclass import Map

SLOT_GAME_DATA = 0

KIA_CODE = 2**32-1

CARDINALS = [Direction.NORTH, Direction.SOUTH, Direction.EAST, Direction.WEST]

Environments = [0, Environment.EMPTY, Environment.WALL, Environment.ORE_TITANIUM]

ENTITIES_CODE = {EntityType.BUILDER_BOT: 1, EntityType.GUNNER: 2, EntityType.SENTINEL: 3,
                 EntityType.LAUNCHER: 4, EntityType.HARVESTER: 5, EntityType.CONVEYOR: 6,
                 EntityType.SPLITTER: 6, EntityType.BARRIER: 7, EntityType.CORE: 0}

BUILD_TYPES = {None: 0, EntityType.GUNNER: 1, EntityType.SENTINEL: 2, EntityType.LAUNCHER: 3, EntityType.HARVESTER: 4, EntityType.BARRIER: 5}

#4 groups of 9 offsets reprsenting the edge of the scouted area after moving NSEW
SCOUT_EDGE_OFFSETS = [[(-4,-2), (-3,-3), (-2,-4), (-1,-4), (0,-4), (1,-4), (2,-4), (3,-3), (4,-2)],
           [(-4,2), (-3,3), (-2,4), (-1,4), (0,4), (1,4), (2,4), (3,3), (4,2)],
           [(2,4), (3,3), (4,2), (4,1), (4,0), (4,-1), (4,-2), (3,-3), (2,-4)],
           [(-2,4), (-3,3), (-4,2), (-4,1), (-4,0), (-4,-1), (-4,-2), (-3,-3), (-2,-4)]]

#8 offsets to of the cross around position
SCOUT_CLOSE_CROSS_OFFSETS = [(-2,0), (-1,0), (1,0), (2,0), (0,2), (0,1), (0,-2), (0,-1)]
SCOUT_FAR_CROSS_OFFSETS = [(-4,0), (-3,0), (3,0), (4,0), (0,4), (0,3), (0,-4), (0,-3)]


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

def log_scout_to_map(pos: Position, direc: Direction, env_map: Map, ct: Controller) -> None:
    nearby = ct.get_nearby_tiles()
    direc_n = CARDINALS.index(direc)
    offsets = SCOUT_EDGE_OFFSETS[direc_n]
    for dx,dy in offsets:
        tile = Position(pos.x+dx, pos.y+dy)
        if tile in nearby:
            env_map.set_environment_at(tile, ct.get_tile_env(tile))

def log_entities_to_map(mp: Map, ct: Controller) -> None:
    for id in ct.get_nearby_entities():
        mp.set_entity_at(ct.get_position(id), ENTITIES_CODE[ct.get_entity_type(id)] + 8 * (ct.get_team() != ct.get_team(id)))


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

def encode_game_data(bots_made: int, opp_core_bottom_right: Position, save_money: bool) -> int:
    """Encodes game data"""
    data_number = bots_made
    if opp_core_bottom_right is not None:
        data_number += (opp_core_bottom_right.x << 10) + (opp_core_bottom_right.y << 5)
    if save_money:
        data_number += 1 << 15
    return data_number

def parse_game_data_number(data_number: int) -> list:
    builders_made = data_number & 31
    opp_core_bottom_right_x = (data_number & (31 << 10)) >> 10
    opp_core_bottom_right_y = (data_number & (31 << 5)) >> 5
    save_money = ((data_number & (1 << 15)) >> 15) == 1
    return [builders_made, Position(opp_core_bottom_right_x, opp_core_bottom_right_y), save_money]

def parse_game_data(ct: Controller) -> list[int|Position|bool]:
    """Reads the store and returns (currently only) the number of bots made"""
    data_number = ct.read_store(SLOT_GAME_DATA)
    builders_made = data_number & 31
    opp_core_bottom_right_x = (data_number & (31 << 10)) >> 10
    opp_core_bottom_right_y = (data_number & (31 << 5)) >> 5
    save_money = ((data_number & (1 << 15)) >> 15) == 1
    return [builders_made, Position(opp_core_bottom_right_x, opp_core_bottom_right_y), save_money]

def read_stored_env_scout(store_index: int, stored_map: Map, ct: Controller) -> None:
    bot_pos, scouted_env = parse_scout(ct.read_store(store_index))
    ct.write_store(store_index, KIA_CODE)
    for tile, env in scouted_env.items():
        stored_map.set_environment_at(tile, env)
        ct.draw_indicator_dot(tile, 0, 255, 0)

def read_stored_scout(starting_store_index: int, stored_map: Map, ct: Controller) -> tuple[Position,set[Position]]:
    """Reads data from ct.store (starting_index and decrementing) into the stored map and resets store-slots"""
    bot_pos, scouted_env = parse_scout(ct.read_store(starting_store_index))
    close_entities = parse_entities(ct.read_store(starting_store_index - 1))
    far_entities = parse_entities(ct.read_store(starting_store_index - 2))
    ct.write_store(starting_store_index, KIA_CODE)
    ct.write_store(starting_store_index - 1, 0)
    ct.write_store(starting_store_index - 2, 0)
    missing = set()

    for tile, env in scouted_env.items():
        stored_map.set_environment_at(tile, env)
        #ct.draw_indicator_dot(tile, 0, 255, 0)

    for i in range(8):
        dx, dy = SCOUT_CLOSE_CROSS_OFFSETS[i]
        close_entity_n = close_entities[i]
        tile = Position(bot_pos.x + dx, bot_pos.y + dy)
        if tile in stored_map.my_harvesters and close_entity_n != 5: missing.add(tile)
        if tile in stored_map.my_conveyors and close_entity_n != 6: missing.add(tile)
        stored_map.set_entity_at(tile, close_entity_n)

        dx, dy = SCOUT_FAR_CROSS_OFFSETS[i]
        far_entity_n = far_entities[i]
        tile = Position(bot_pos.x + dx, bot_pos.y + dy)
        if tile in stored_map.my_harvesters and far_entity_n != 5: missing.add(tile)
        if tile in stored_map.my_conveyors and far_entity_n != 6: missing.add(tile)
        stored_map.set_entity_at(tile, far_entity_n)

    return bot_pos, missing

def encode_build_order(go_to: Position, build_type: EntityType | None, build_direction: Direction, conveyor_path: list[Direction]) -> int:
    """goto(10-bit),type(3-bit),direction(2-bit)"""
    build_type_n = BUILD_TYPES[build_type]
    build_dir_n = CARDINALS.index(build_direction)
    number = go_to.x + (go_to.y << 5) + (build_type_n << 10) + (build_dir_n << 13)
    if conveyor_path:
        shift = 15
        conveyor_path.append(Direction.opposite(conveyor_path[-1])) # We add termination to path
        for belt_direction in conveyor_path:
            number += CARDINALS.index(belt_direction) << shift
            shift += 2
            if shift > 30: break
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

if __name__ == '__main__':
    print(encode_build_order(Position(14,13), EntityType.HARVESTER, Direction.SOUTH, [D]))
    print(parse_build_order(12718))