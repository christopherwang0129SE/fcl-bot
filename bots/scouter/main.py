import random

from fcode import Controller, Team, EntityType, Environment, Direction, Position, GameError, GameConstants
from mapclass import Map, pack_pos, unpack_pos

CARDINALS = [Direction.NORTH, Direction.SOUTH, Direction.EAST, Direction.WEST]
Environments = [0, Environment.EMPTY, Environment.WALL, Environment.ORE_TITANIUM]
ENV_MAP = Map()
SCOUT_SLOTS = list(range(8, 14))  # 6 slots for scouting, allows multiple builders to report simultaneously
FRONTIER_TARGET = 14
FRONTIER_COMPUTE_INTERVAL = 5
OFFSETS = [[(-4,-2), (-3,-3), (-2,-4), (-1,-4), (0,-4), (1,-4), (2,-4), (3,-3), (4,-2)],
           [(-4,2), (-3,3), (-2,4), (-1,4), (0,4), (1,4), (2,4), (3,3), (4,2)],
           [(2,4), (3,3), (4,2), (4,1), (4,0), (4,-1), (4,-2), (3,-3), (2,-4)],
           [(-2,4), (-3,3), (-4,2), (-4,1), (-4,0), (-4,-1), (-4,-2), (-3,-3), (-2,-4)]]


def encode_scout(pos: Position, direc: Direction, ct: Controller) -> int:
    """Moving a bot one step brings 9 new tiles into vision range, the encoded number stores
    the bots final position (10-bits), the direction it moved (2-bits) and the terrain at the 9 tiles (2*9=18-bit)
    """
    nearby = ct.get_nearby_tiles()
    direc_n = CARDINALS.index(direc)
    offsets = OFFSETS[direc_n]

    number = (pos.x<<25) + (pos.y<<20) + (direc_n<<18)

    shift = 16
    for dx,dy in offsets:
        tile = Position(pos.x+dx, pos.y+dy)
        if tile in nearby:
            env_n = Environments.index(ct.get_tile_env(tile))
            number += env_n<<shift
        shift -= 2

    return number

def parse_scout(number: int) -> dict[Position, Environment]:
    x = (number & 31<<25) >> 25
    y = (number & 31<<20) >> 20
    direc_n = (number & 3<<18) >> 18 #NSEW
    offsets = OFFSETS[direc_n]
    tiles: dict[Position, Environment] = {}
    shift = 16
    for dx,dy in offsets:
        env_n = (number & 3<<shift) >> shift
        if env_n > 0:
            tiles.update({Position(x+dx, y+dy): Environments[env_n]})
        shift-=2
    return tiles

class Player:
    def __init__(self):
        self.local_map = None
        self.last_pos = None
        self.stuck_count = 0
        self.frontier_target = None

    def run(self, ct: Controller) -> None:

        etype = ct.get_entity_type()
        if etype == EntityType.CORE:
            if not ENV_MAP.configured:
                ENV_MAP.configure(ct.get_map_width(), ct.get_map_height())
                b = 0
                for tile in ct.get_nearby_tiles():
                    ENV_MAP.set_environment_at(tile, ct.get_tile_env(tile))
                    ct.draw_indicator_dot(tile, 0, 255, b)
                    b+= 5

                for pos in ct.get_nearby_tiles(dist_sq=2):
                    if ct.can_spawn(pos):
                        ct.spawn_builder(pos)
                        break

            else:
                # Read all scout slots and update map
                for slot in SCOUT_SLOTS:
                    scout_data = ct.read_store(slot)
                    if scout_data > 0:
                        scouted = parse_scout(scout_data)
                        for pos, env in scouted.items():
                            ENV_MAP.set_environment_at(pos, env)
                            ct.draw_indicator_dot(pos, 0, 255, 0)
                        ct.write_store(slot, 0)  # Clear the slot after reading

                # Periodically compute and broadcast the nearest unscouted cell from core position
                if ct.get_current_round() % FRONTIER_COMPUTE_INTERVAL == 0:
                    core_pos = ct.get_position()
                    frontier = ENV_MAP.nearest_unscouted(core_pos, max_radius=30)
                    if frontier:
                        ct.write_store(FRONTIER_TARGET, pack_pos(frontier))

                print(ENV_MAP)

        elif etype == EntityType.BUILDER_BOT:
            self._run_builder(ct)

    def _run_builder(self, ct: Controller) -> None:
        pos = ct.get_position()

        # Initialize local map on first run
        if self.local_map is None:
            self.local_map = Map()
            self.local_map.configure(ct.get_map_width(), ct.get_map_height())

        # Update local map from nearby visible tiles
        for tile in ct.get_nearby_tiles():
            env = ct.get_tile_env(tile)
            self.local_map.set_environment_at(tile, env)

        # Detect stuck (if we didn't move last round, increment counter)
        if self.last_pos == pos:
            self.stuck_count += 1
        else:
            self.stuck_count = 0
        self.last_pos = pos

        # Pick a target: prefer local unscouted, fall back to frontier target from core, else random
        target = None

        # Try local unscouted nearby
        local_frontier = self.local_map.nearest_unscouted(pos, max_radius=8)
        if local_frontier:
            target = local_frontier
        else:
            # Read frontier target from core (broadcast every 5 rounds)
            frontier_packed = ct.read_store(FRONTIER_TARGET)
            frontier = unpack_pos(frontier_packed)
            if frontier:
                target = frontier
            else:
                # Fallback: random position
                target = Position(random.randint(0, ct.get_map_width() - 1),
                                  random.randint(0, ct.get_map_height() - 1))

        # Move toward target using cardinal direction
        if target and target != pos:
            direction = pos.cardinal_direction_to(target)
            if direction != Direction.CENTRE and ct.can_move(direction):
                ct.move(direction)
                new_pos = ct.get_position()
                print(f"round {ct.get_current_round()}: moved {direction.name} to {new_pos} toward {target}")
                scout_n = encode_scout(new_pos, direction, ct)
                # Write to this builder's assigned scout slot (based on entity ID)
                scout_slot = SCOUT_SLOTS[ct.get_id() % len(SCOUT_SLOTS)]
                ct.write_store(scout_slot, scout_n)


if __name__ == '__main__':
    print(parse_scout(170065921))