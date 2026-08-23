from xml.dom.minidom import Entity

from fcode import Controller, Team, EntityType, Environment, Direction, Position, GameError

CARDINALS = [Direction.NORTH, Direction.SOUTH, Direction.EAST, Direction.WEST]

SYMMETRY_ROTATIONAL = 0
SYMMETRY_HORIZONTAL = 1
SYMMETRY_VERTICAL = 2

def adjacent_tiles(tile: Position) -> list[Position]:
    return [tile.add(direction) for direction in CARDINALS]


class Map:
    """Stores and manages map data, location of obstacles and resources
    possibly structures units and pathfinding pre-compute.

    Environment_grid stores the Environment-type for each known tile, or 0 otherwise

    Entity_grid stores each tile as 4bits (own units 1-7, opp 8-15)
    0       - empty tile
    1/9     - builder bot
    2/10    - gunner
    3/11    - sentinel
    4/12    - launcher
    5/13    - harvester
    6/14    - conveyor OR splitter (to fit in 4 bits)
    7/15    - barrier
    8       - opp core
    16      - own core
    """

    def __init__(self):
        """Creates an map-object unusable until configured"""
        self.environment_grid = None
        self.entity_grid = None
        self.buildplan_grid = None
        self.conveyor_distance_grid = None
        self.height = None
        self.width = None
        self.configured = False
        self.own_core: list[Position] = None
        self.opp_core: list[Position] = None
        self.unplanned_ore: set[Position] = set()
        self.planned_ore: set[Position] = set()
        self.conveyor_load: dict[Position,int] = dict()
        self.conveyor_starts: set(Position) = set()
        self.conveyor_directions: dict[Position,Direction] = dict()
        self.my_conveyors: set[Position] = set()
        self.my_harvesters: set[Position] = set()

    def configure(self, width: int, height: int, core_pos: Position) -> None:
        """Sets the map as configured and creates a grid of Zeroes to represent unscouted terrain"""
        self.width = width
        self.height = height
        self.configured = True
        self.environment_grid = [[0 for col in range(width)] for row in range(height)]
        self.entity_grid = [[0 for col in range(width)] for row in range(height)]
        self.buildplan_grid = [[0 for col in range(width)] for row in range(height)]
        self.conveyor_distance_grid = [[63 for col in range(width)] for row in range(height)]
        self.own_core: list[Position] = []
        self.opp_core: list[Position] = []
        self.known_symmetry = None
        for dx in 0,1:
            for dy in 0,1:
                self.own_core.append(Position(core_pos.x + dx, core_pos.y + dy))
                self.entity_grid[core_pos.y + dy][core_pos.x + dx] = 16
                self.buildplan_grid[core_pos.y + dy][core_pos.x + dx] = 16

    def update_conveyor_loads(self, starting_conveyor: Position):
        active = starting_conveyor.add(self.conveyor_directions[starting_conveyor])
        while active in self.conveyor_load:
            self.conveyor_load[active] += 1
            active = active.add(self.conveyor_directions[active])

    def max_down_stream_load(self, starting_conveyor: Position) ->int:
        active = starting_conveyor
        next = active.add(self.conveyor_directions[active])
        while next in self.conveyor_load:
            if self.conveyor_load[next] > 3: return 4
            active = next
            next = active.add(self.conveyor_directions[active])
        return self.conveyor_load[active]

    def update_conveyor_distance_grid(self):
        opened: list[list[Position]] = [[]]
        visited: set[Position] = set()
        for core_tile in self.own_core:
            visited.add(core_tile)
            self.conveyor_distance_grid[core_tile.y][core_tile.x] = 0
            opened[0].append(core_tile)

        working_distance = 0
        while working_distance < 62:
            if not opened[working_distance]:
                working_distance += 1
                if working_distance == len(opened): break
                continue

            active = opened[working_distance].pop()
            near = adjacent_tiles(active)
            for tile in near:
                if tile not in visited:
                    visited.add(tile)
                    env = self.get_environment_at(tile)
                    if env == Environment.EMPTY:
                        distance = working_distance
                        if tile in self.conveyor_load: #Conveyour/Splitter we assume orientated right
                            if self.max_down_stream_load(tile) > 3:
                                self.conveyor_load[tile] = 4
                                distance = 62 #Overload
                        else:
                            distance += 1
                        self.conveyor_distance_grid[tile.y][tile.x] = distance
                        while len(opened) <= distance:
                            opened.append([])
                        opened[distance].append(tile)

    def plan_conveyor_to(self, target: Position, repeats = 0) -> tuple[bool, Position, Direction, EntityType|None, list[Direction]]:
        if repeats > 2: return False, Position(0,0), Direction.NORTH, None, []
        adjacent_to_target = [tile for tile in adjacent_tiles(target) if
                           self.get_environment_at(tile) == Environment.EMPTY]
        if not adjacent_to_target:
            return False, Position(0,0), Direction.NORTH, None, []
        first_conveyor = min(adjacent_to_target, key=lambda tile: self.get_conveyor_distance_at(tile))
        build_direction = first_conveyor.cardinal_direction_to(target)

        active_conveyor = first_conveyor
        conveyor_path: list[Position] = []
        path_directions = []
        while self.get_conveyor_distance_at(active_conveyor) > 0:  # This one needs building
            conveyor_path.append(active_conveyor)
            adjacents = [tile for tile in adjacent_tiles(active_conveyor) if
                         self.get_environment_at(tile) == Environment.EMPTY]
            if not adjacents:
                return False, first_conveyor, build_direction, None, path_directions
            active_conveyor = min(adjacents, key=lambda tile: self.get_conveyor_distance_at(tile))
            if len(conveyor_path) > 7:
                if self.get_conveyor_distance_at(conveyor_path[-1]) < 14:
                    return self.plan_conveyor_to(conveyor_path[-2], repeats+1)
                else:
                    return False, first_conveyor, build_direction, None, path_directions

        for tile in conveyor_path:
            self.set_buildplan_at(tile, 6)
            if tile in self.conveyor_load: self.conveyor_load[tile] += 1
            else: self.conveyor_load[tile] = 0
        while conveyor_path:
            path_directions.append(conveyor_path[-1].cardinal_direction_to(active_conveyor))
            self.conveyor_directions[conveyor_path[-1]] = path_directions[-1]
            active_conveyor = conveyor_path.pop()

        path_directions.reverse()
        self.update_conveyor_distance_grid()

        return True, first_conveyor, build_direction, None, path_directions



    def plan_easiest_harvester(self, dissallowed_ores: list[Position]) -> tuple[bool, Position, Direction, EntityType|None, list[Direction]]:
        """Finds the unplanned ore that require fewest conveyor to connect and produces a plan to build it
        moves the ore from unplanned to planned and updates the build_plan grid and conveyor_distance grid"""
        allowed_ore = [ore_tile for ore_tile in self.unplanned_ore if ore_tile not in dissallowed_ores]
        if not allowed_ore:
            return False, Position(-1,-1), Direction.NORTH, None, []
        easiest_build = min(allowed_ore, key=lambda ore_tile: (min([self.get_conveyor_distance_at(adjacent) for adjacent in adjacent_tiles(ore_tile)])))
        adjacent_to_ore = [tile for tile in adjacent_tiles(easiest_build) if self.get_environment_at(tile)==Environment.EMPTY]
        if not adjacent_to_ore:
            return False, easiest_build, Direction.NORTH, None, []
        first_conveyor = min(adjacent_to_ore, key=lambda tile: self.get_conveyor_distance_at(tile))
        build_direction = first_conveyor.cardinal_direction_to(easiest_build)

        active_conveyor = first_conveyor
        conveyor_path: list[Position] = []
        path_directions = []
        while self.get_conveyor_distance_at(active_conveyor) > 0: #This one needs building
            conveyor_path.append(active_conveyor)
            adjacents = [tile for tile in adjacent_tiles(active_conveyor) if self.get_environment_at(tile)==Environment.EMPTY]
            if not adjacents:
                return False, easiest_build, build_direction, None, path_directions
            active_conveyor = min(adjacents, key=lambda tile: self.get_conveyor_distance_at(tile))
            if len(conveyor_path) > 7:
                if self.get_conveyor_distance_at(conveyor_path[-1]) < 14:
                    return self.plan_conveyor_to(conveyor_path[-2])
                else: return False, easiest_build, build_direction, None, path_directions

        self.planned_ore.add(easiest_build)
        self.unplanned_ore.remove(easiest_build)
        self.set_buildplan_at(easiest_build, 5)
        for tile in conveyor_path:
            self.set_buildplan_at(tile, 6)
            if tile in self.conveyor_load: self.conveyor_load[tile] += 1
            else: self.conveyor_load[tile] = 1

        last_conveyor = conveyor_path[-1] if conveyor_path else first_conveyor
        while conveyor_path:
            path_directions.append(conveyor_path[-1].cardinal_direction_to(active_conveyor))
            self.conveyor_directions[conveyor_path[-1]] = path_directions[-1]
            active_conveyor = conveyor_path.pop()

        path_directions.reverse()
        if last_conveyor: self.update_conveyor_loads(last_conveyor)
        self.update_conveyor_distance_grid()

        return True, first_conveyor, build_direction, EntityType.HARVESTER, path_directions

    def environment_str(self) -> str:
        """Returns the environment grid as a multiline string"""
        if not self.configured: return "Map not configured!"
        return "\n".join(" ".join('*' if x == 0 else str(x.name)[0] for x in row) for row in self.environment_grid)

    def entities_str(self) -> str:
        """Returns the entities grid as a multiline string"""
        if not self.configured: return "Map not configured!"
        return "\n".join(" ".join('*' if x == 0 else hex(x)[2] for x in row) for row in self.entity_grid)

    def conveyor_str(self) -> str:
        """Returns the conveyor distance grid as a multiline string"""
        if not self.configured: return "Map not configured!"
        return "\n".join(" ".join('**' if x == 63 else '--' if x == 62 else f"{x:02}" for x in row) for row in self.conveyor_distance_grid)

    def set_environment_at(self, pos: Position, env: Environment) -> None:
        """Sets the specified position if valid, else does nothing"""
        if (not self.configured) or pos.x < 0 or pos.x >= self.width or pos.y < 0 or pos.y >= self.height: return
        self.environment_grid[pos.y][pos.x] = env
        if env == Environment.ORE_TITANIUM and pos not in self.planned_ore: self.unplanned_ore.add(pos)

    def set_buildplan_at(self, pos: Position, build_n: int) -> None:
        """Sets the specified position if valid, else does nothing"""
        if (not self.configured) or pos.x < 0 or pos.x >= self.width or pos.y < 0 or pos.y >= self.height: return
        self.buildplan_grid[pos.y][pos.x] = build_n

    def get_environment_at(self, pos: Position) -> Environment | None:
        if (not self.configured) or pos.x<0 or pos.x>=self.width or pos.y<0 or pos.y>=self.height: return None
        return self.environment_grid[pos.y][pos.x]

    def get_entity_code_at(self, pos: Position) -> int | None:
        if (not self.configured) or pos.x < 0 or pos.x >= self.width or pos.y < 0 or pos.y >= self.height: return None
        return self.entity_grid[pos.y][pos.x]

    def is_passable(self, pos: Position) -> bool:
        if (not self.configured) or pos.x < 0 or pos.x >= self.width or pos.y < 0 or pos.y >= self.height: return False
        env = self.get_environment_at(pos)
        if env == Environment.WALL: return False
        entity = self.get_entity_code_at(pos)
        return entity in [0, 6, 14]


    def set_entity_at(self, pos: Position, entity_n: int) -> None:
        """Sets the specified position if valid, else does nothing"""
        if (not self.configured) or pos.x < 0 or pos.x >= self.width or pos.y < 0 or pos.y >= self.height: return
        if pos in self.own_core: return
        if entity_n == 8 and pos not in self.opp_core: self.opp_core.append(pos)
        elif entity_n == 5:
            self.my_harvesters.add(pos)
            print(f"Add Harv ({pos.x},{pos.y}) n= {entity_n}")
        elif entity_n == 6:
            self.my_conveyors.add(pos)
            print(f"Add Conv ({pos.x},{pos.y}) n= {entity_n}")
        self.entity_grid[pos.y][pos.x] = entity_n

    def get_conveyor_distance_at(self, pos: Position) -> int:
        if (not self.configured) or pos.x < 0 or pos.x >= self.width or pos.y < 0 or pos.y >= self.height: return 63
        return self.conveyor_distance_grid[pos.y][pos.x]

    def get_buildplan_at(self, pos: Position) -> int:
        if (not self.configured) or pos.x < 0 or pos.x >= self.width or pos.y < 0 or pos.y >= self.height: return 0
        return self.buildplan_grid[pos.y][pos.x]

    def scouted_at(self, pos: Position) -> bool:
        if self.get_environment_at(pos): return True
        return False

    def get_unscouted_near(self, bot_pos: Position) -> Position | None:
        for dx in range(10):
            for dy in range(dx+1):
                #print(f"DX: {dx}, DY: {dy}")
                if self.get_environment_at(Position(bot_pos.x + dx,bot_pos.y+dy)) == 0:
                    return Position(bot_pos.x + dx,bot_pos.y + dy)
                if self.get_environment_at(Position(bot_pos.x - dx,bot_pos.y+dy)) == 0:
                    return Position(bot_pos.x - dx, bot_pos.y + dy)
                if self.get_environment_at(Position(bot_pos.x + dx,bot_pos.y-dy)) == 0:
                    return Position(bot_pos.x + dx, bot_pos.y - dy)
                if self.get_environment_at(Position(bot_pos.x - dx,bot_pos.y-dy)) == 0:
                    return Position(bot_pos.x - dx, bot_pos.y - dy)
        return None

    def test_for_symmetry_kind(self, symmetry_kind: int) -> bool:
        """Returns TRUE if the env-map supports the specified symmetry kind"""
        if symmetry_kind == SYMMETRY_HORIZONTAL:
            for y in range(self.height):
                for x in range(self.width//2):
                    if self.environment_grid[y][x] != 0 and self.environment_grid[y][self.width-x-1] != 0:
                        if self.environment_grid[y][x] != self.environment_grid[y][self.width-x-1]:
                            return False
        elif symmetry_kind == SYMMETRY_VERTICAL:
            for x in range(self.width):
                for y in range(self.height//2):
                    if self.environment_grid[y][x] != 0 and self.environment_grid[self.height -y -1][x] != 0:
                        if self.environment_grid[y][x] != self.environment_grid[self.height -y -1][x]:
                            return False
        elif symmetry_kind == SYMMETRY_ROTATIONAL:
            if self.width != self.height: return False
            for x in range(self.width):
                for y in range(self.height//2):
                    if self.environment_grid[y][x] != 0 and self.environment_grid[self.height -y -1][self.width -x -1] != 0:
                        if self.environment_grid[y][x] != self.environment_grid[self.height -y -1][self.width -x -1]:
                            return False
        return True

    def test_for_symmetry_by_cores(self, symmetry_kind: int) -> bool:
        """Returns TRUE if the known cores supports the specified symmetry kind"""
        if len(self.own_core) == 0 or len(self.opp_core) == 0: return True
        if symmetry_kind == SYMMETRY_HORIZONTAL:
            for core_tile in self.opp_core:
                if Position(self.width - core_tile.x -1, core_tile.y) not in self.own_core: return False

        if symmetry_kind == SYMMETRY_VERTICAL:
            for core_tile in self.opp_core:
                if Position(core_tile.x, self.height -core_tile.y-1) not in self.own_core: return False

        if symmetry_kind == SYMMETRY_ROTATIONAL:
            for core_tile in self.opp_core:
                if Position(self.width - core_tile.x - 1, self.height - core_tile.y - 1) not in self.own_core: return False
        return True

    def discover_symmetry(self) -> bool:
        possible = []
        for symmetry_kind in [SYMMETRY_ROTATIONAL, SYMMETRY_HORIZONTAL, SYMMETRY_VERTICAL]:
            if self.test_for_symmetry_kind(symmetry_kind) and self.test_for_symmetry_by_cores(symmetry_kind):
                possible.append(symmetry_kind)
        if len(possible) == 1:
            self.known_symmetry = possible[0]
            return True
        return False

    def deduce_opp_core(self):
        if self.known_symmetry == SYMMETRY_HORIZONTAL:
            for tile in self.own_core:
                self.opp_core.append(Position(self.width - tile.x -1, tile.y))
        elif self.known_symmetry == SYMMETRY_VERTICAL:
            for tile in self.own_core:
                self.opp_core.append(Position(tile.x, self.height - tile.y -1))
        elif self.known_symmetry == SYMMETRY_ROTATIONAL:
            for tile in self.own_core:
                self.opp_core.append(Position(self.width - tile.x -1, self.height - tile.y -1))



def print_conveyor_directions(mp:Map):
    print([f"({pos.x},{pos.y}):{direc.name[0]}" for pos,direc in mp.conveyor_directions.items()])
def print_conveyor_loads(mp:Map):
    print([f"({pos.x},{pos.y}):{val}" for pos,val in mp.conveyor_load.items()])
def print_conveyor_info(mp:Map):
    print("Conveyor".center(mp.width * 2 - 1, '-'))
    print(mp.conveyor_str())
    print_conveyor_directions(mp)
    print_conveyor_loads(mp)

if __name__ == '__main__':
    width, height = 9,6
    e_map = Map()
    e_map.configure(width,height, Position(0,0))
    for row in range(height):
        for col in range(width):
            pass
            e_map.set_environment_at(Position(col, row), Environment.EMPTY)
    #e_map.set_environment_at(Position(4, 0), Environment.WALL)
    #e_map.set_environment_at(Position(4, 1), Environment.WALL)
    for x in range(1,6): e_map.set_environment_at(Position(x, 3), Environment.ORE_TITANIUM)

    #e_map.buildplan_grid[2][1] = 6
    #e_map.buildplan_grid[2][2] = 6
    #e_map.buildplan_grid[2][3] = 6
    #e_map.buildplan_grid[2][1] = 6

    e_map.update_conveyor_distance_grid()
    print("Environment".center(width*2-1,'-'))
    print(e_map.environment_str())
    #print("Entities".center(width*2-1,'-'))
    #print(e_map.entities_str())
    #print("Conveyor".center(width*2-1,'-'))

    #print(e_map.conveyor_str())

    print_conveyor_info(e_map)

    print(f"{e_map.plan_easiest_harvester()=}")
    print_conveyor_info(e_map)

    print(f"{e_map.plan_easiest_harvester()=}")
    print_conveyor_info(e_map)

    print(f"{e_map.plan_easiest_harvester()=}")
    print_conveyor_info(e_map)

    print(f"{e_map.plan_easiest_harvester()=}")
    print_conveyor_info(e_map)

    print(f"{e_map.plan_easiest_harvester()=}")
    print_conveyor_info(e_map)