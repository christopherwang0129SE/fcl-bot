import random

from fcode import Controller, Team, EntityType, Environment, Direction, Position, GameError
from mapclass import Map

# Builder bots move only in the four cardinal directions.
CARDINALS = [Direction.NORTH, Direction.SOUTH, Direction.EAST, Direction.WEST]
Environments = [0, Environment.EMPTY, Environment.WALL, Environment.ORE_TITANIUM]
ENV_MAP = Map()
SCOUT_DATA1 = 15
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
                scouted = parse_scout(ct.read_store(SCOUT_DATA1))
                ct.write_store(SCOUT_DATA1, 0)
                for pos, env in scouted.items():
                    ENV_MAP.set_environment_at(pos, env)
                    ct.draw_indicator_dot(pos, 0, 255, 0)
                print(ENV_MAP)

        elif etype == EntityType.BUILDER_BOT:
            self._run_builder(ct)

    def _run_builder(self, ct: Controller) -> None:
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
            print(f"{scout_n=}")
            ct.write_store(SCOUT_DATA1, scout_n)


if __name__ == '__main__':
    print(parse_scout(170065921))