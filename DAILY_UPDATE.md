# Daily Update — August 2, 2026

## Project Status
**FCL Bot** — A competitive strategy bot for the Florent Code League hackathon using the `fcode` framework.

## Completed Today
✅ Set up project structure and environment  
✅ Initialized starter bot with core scaffolding  
✅ Configured bot strategy guide and documentation  
✅ Created comprehensive README with:
- Quick start setup instructions
- Bot entity types and roles (Core, Builder, Harvester, Conveyor, Gunner)
- Strategy outline: resource gathering → defense build-up
- Communication store coordination system (16-slot memory)
✅ Added maps directory with competition maps  
✅ Tested bot with initial match replay (replay.replay26)  

## Bot Architecture
- **Core**: Spawns builders and manages ammo
- **Builder Bots** (5): Explore, build harvesters + conveyors, transition to gunners at economy milestone
- **Harvester**: Resource extraction from ore tiles
- **Conveyor**: Automatic resource transport
- **Gunner**: Defensive turret against enemies

## Current Implementation
- Main bot logic in `bots/starter/main.py`
- Entity coordination via 16-slot communication store
- Basic strategy: Early economy focus → Transition to defense

## Next Steps / Ideas for Improvement
- Refine builder role coordination (explorer vs builder vs defender)
- Complete conveyor chain routing from harvesters to core
- Add advanced units (sentinels, launchers) for stronger defense
- Implement systematic map exploration strategy
- Optimize dynamic ammo buffering based on threat level
- Improve pathfinding to prevent bot blocking

## Setup Reminders
```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install fcode
fcode login
fcode run starter starter  # Test match
```

## Files Modified
- `README.md` — Added setup and strategy guide
- `bots/starter/main.py` — Starter bot implementation
- `fcode.toml` — Bot configuration
- `maps/` — Competition maps

---
Ready to continue development tomorrow. Bot framework is solid and ready for strategy refinement.

---

# Daily Update — August 12, 2026

## Project Status
**FCL Bot** — Scouter + Starter bot exploration and pathfinding overhaul. Three feature branches merged tonight.

## Completed Today (3 feature branches)

### Branch 1: Systematic Exploration (`feature/systematic-exploration`)
✅ Extended `Map` class with `nearest_unscouted(from_pos, max_radius)` frontier scanning  
✅ Gave each builder a `local_map` tracking its own scouted tiles (updated from `ct.get_nearby_tiles()` each round)  
✅ Core computes and broadcasts nearest unscouted frontier target via store slot 14, refreshed every 5 rounds  
✅ Builders prefer local frontier → core's frontier target → random exploration (was pure random walk before)  
✅ Added `pack_pos()`/`unpack_pos()` helpers to `mapclass.py` for efficient u32 encoding of positions  
**Impact:** Reduces re-scouting; introduces bidirectional map sharing (core → builders) via store.

### Branch 2: Multi-Slot Scouting (`feature/multi-slot-scouting`)
✅ Defined `SCOUT_SLOTS = range(8, 14)` (6 slots reserved for scout reports; leaves slot 14 for frontier, 15 free)  
✅ Each builder writes to `SCOUT_SLOTS[entity_id % len(SCOUT_SLOTS)]` instead of fixed slot 15  
✅ Core now loops over all scout slots, parses, updates map, and clears each slot after consuming  
**Impact:** Allows multiple builders to report simultaneously without write collisions (1 report/round → up to 6/round).  
**Known Limitation:** If builders > slots, `id % N` mod collisions still occur; flagged as future refinement (round-robin slot claiming).

### Branch 3: BFS Pathfinding (`feature/pathfinding`)
✅ Implemented `pathfind.py` with BFS algorithm (cardinal moves only; treats `WALL` as blocked, everything else passable)  
✅ Both `bots/scouter/` and `bots/starter/` now have their own `pathfind.py` + `mapclass.py` (copied due to engine's per-bot isolation)  
✅ Builders cache `self.path` (list of Directions) computed via BFS when target changes  
✅ Fall back to greedy cardinal_direction_to if path unreachable with known map  
✅ BFS capped at 500 nodes per path for CPU safety  
✅ Starter bot's `_move_toward_target()` replaced greedy loop with BFS + path-following + fallback  
**Impact:** Resolves "Improve pathfinding to prevent bot blocking" TODO; bots navigate around walls instead of getting permanently stuck.  
**Known Limitation:** Optimistic navigation assumes unscouted tiles (0) are passable; refined follow-up can improve this.

## Key Architectural Changes
- `bots/scouter/main.py`: Added frontier broadcasting (slot 14), multi-slot scouting (slots 8-13), pathfinding integration
- `bots/starter/main.py`: Added local map tracking, BFS pathfinding, fallback greedy movement
- New files: `bots/scouter/pathfind.py`, `bots/starter/pathfind.py`, `bots/starter/mapclass.py` (duplication noted below)

## Known Limitations & Tech-Debt
1. **mapclass.py / pathfind.py duplication**: Copied into both `bots/scouter/` and `bots/starter/` because `fcode` engine loads each bot folder in isolation (no cross-bot imports). Future improvement: build step to auto-copy shared modules before packaging, or single-folder monorepo structure.
2. **Multi-slot collisions**: With >6 builders, `id % 6` collisions drop scout reports. Mitigation: round-robin slot claiming or dynamically map builder IDs to slots (follow-up).
3. **Optimistic pathfinding**: BFS treats unscouted tiles (0) as passable; can lead to dead-end planning if hidden walls block the path. Refinement: track visited cells, retry BFS if a queued move is blocked by newly-scouted wall.
4. **Frontier computation CPU**: Core re-scans entire `ENV_MAP` every 5 rounds looking for nearest unscouted; could optimize with quadtree/spatial indexing for large maps (negligible for current competition maps).

## Testing
- ✅ `fcode run scouter scouter --seed 42` completes without exceptions
- ✅ `fcode run starter starter --seed 42` completes without exceptions; visible pathfinding around obstacles
- Both bots' local maps update correctly from scouting
- Multi-slot scouting demonstrated with both bots reporting simultaneously

## Next Steps
- Tune `FRONTIER_COMPUTE_INTERVAL` (currently 5 rounds) based on actual game pacing
- Monitor CPU time via `ct.get_cpu_time_elapsed()` on BFS-heavy maps; adjust `max_nodes` cap if needed
- Integrate scouter's frontier + multi-slot scouting patterns into starter bot's economy strategy (currently orthogonal)
- Consider adding a "last N turns" tile-decay for dynamic re-exploration (enemies may move/build on previously scouted terrain)

---
**Teammate note:** All three branches are merged to main and pushed to origin. Rough drafts validated via match tests; ready for feedback/refinement.
