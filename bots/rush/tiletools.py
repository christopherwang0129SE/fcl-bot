from fcode import Controller, Team, EntityType, Environment, Direction, Position, GameError
from encodeparse import CARDINALS
from mapclass import Map

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

def tiles_in_crosshair(facing_dir: Direction, ct: Controller,) -> list[Position]:
    """Gets the outward moving list of tiles in the facing direction"""
    active_tile = ct.get_position().add(facing_dir)
    targets = []
    while ct.is_in_vision(active_tile):
        targets.append(active_tile)
        active_tile = active_tile.add(facing_dir)
    return targets

def gunner_target_in(facing_dir: Direction, ct:Controller) -> Position|None:
    """Return the tile on which an enemy could be hit in facing dir, else None if blocked or empty"""
    for tile in tiles_in_crosshair(facing_dir, ct):
        if tile_has_friend(tile, ct) or ct.get_tile_env(tile) == Environment.WALL: return None
        elif tile_has_enemy(tile, ct): return tile
    return None

def gunner_could_target_if_turned(gun_position: Position, gun_team: Team, ct: Controller) -> Direction|None:
    building_tiles = [ct.get_position(id) for id in ct.get_nearby_buildings() if ct.get_team(id) != ct.get_team()]
    unit_tiles = [ct.get_position(id) for id in ct.get_nearby_units() if ct.get_team(id) != gun_team]
    for tile in building_tiles:
        for direction in Direction:
            if ct.can_fire_from(gun_position, direction, EntityType.GUNNER, tile): return direction
    for tile in unit_tiles:
        for direction in Direction:
            if ct.can_fire_from(gun_position, direction, EntityType.GUNNER, tile): return direction

def tile_has_enemy(tile: Position, ct: Controller) -> bool:
    if not ct.is_in_vision(tile): return False
    if ct.get_tile_building_id(tile) and ct.get_team(ct.get_tile_building_id(tile)) != ct.get_team():
        return True
    if ct.get_tile_builder_bot_id(tile) and ct.get_team(ct.get_tile_builder_bot_id(tile)) != ct.get_team():
        return True
    return False

def tile_has_enemy_core(tile: Position, ct: Controller) -> bool:
    return ct.get_tile_building_id(tile) and ct.get_team(ct.get_tile_building_id(tile)) != ct.get_team() and ct.get_entity_type(ct.get_tile_building_id(tile)) == EntityType.CORE

def tile_has_friend(tile: Position, ct: Controller) -> bool:
    if not ct.is_in_vision(tile): return False
    if ct.get_tile_building_id(tile) and ct.get_team(ct.get_tile_building_id(tile)) == ct.get_team():
        return True
    if ct.get_tile_builder_bot_id(tile) and ct.get_team(ct.get_tile_builder_bot_id(tile)) == ct.get_team():
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

def hostile_buildings_near(ct:Controller) -> list[Position]:
    nearby_building_ids = ct.get_nearby_buildings()
    hostile_building_ids = [id for id in nearby_building_ids if (ct.get_team() != ct.get_team(id) and ct.get_entity_type(id) in [EntityType.GUNNER, EntityType.SENTINEL])]
    return [ct.get_position(id) for id in hostile_building_ids]

def friendly_gunners_near(ct: Controller) -> list[Position]:
    nearby_building_ids = ct.get_nearby_buildings()
    friendly_gunner_ids = [id for id in nearby_building_ids if
                           (ct.get_entity_type(id) == EntityType.GUNNER and ct.get_team() == ct.get_team(id))]
    return [ct.get_position(id) for id in friendly_gunner_ids]

def unmatched_hostiles_near(ct: Controller) -> list[Position]:
    unmatched = []
    hostile_tiles = hostile_buildings_near(ct)
    if not hostile_tiles: return []
    friendly_guns = friendly_gunners_near(ct)
    print(f"UNM {friendly_guns=}")
    if not friendly_guns: return hostile_tiles
    for hostile in hostile_tiles:
        matched = False
        for direction in Direction:
            if matched: break
            for friendly in friendly_guns:
                if ct.can_fire_from(friendly, direction, EntityType.GUNNER, hostile):
                    matched = True
                    break
        if not matched: unmatched.append(hostile)
    return unmatched



def gun_placement_to_match(target: Position, ct: Controller) -> Position|None:
    empty_near_target = [tile for tile in ct.get_nearby_tiles() if (tile.distance_squared(target) <=2 and ct.is_tile_empty(tile))]
    if not empty_near_target: return None
    empty_near_target.sort(key=lambda tile: tile.distance_squared(ct.get_position()))
    for tile in empty_near_target:
        if gunner_could_target_if_turned(tile, ct.get_team(), ct): return tile
    return None

def reachable_tiles(tile: Position, ct: Controller) -> list[Position]:
    pass

if __name__ == '__main__':
    print("HI")