# FCL Bot — Florent Code League

A competitive strategy bot for the Florent Code League hackathon using the `fcode` framework.

## Quick Start

### Prerequisites
- Python 3.12 or 3.13
- Homebrew (Mac) or equivalent package manager

### Setup

```bash
# Clone the repo
git clone <your-repo-url>
cd fcl-bot

# Create virtual environment with Python 3.13
python3.13 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install fcode

# Authenticate
fcode login
```

### Run a Test Match

```bash
# Run a match: your starter bot vs itself
fcode run starter starter

# Watch the replay
fcode watch replay.replay26
```

## Bot Structure

### Entity Types
- **Core** — Your base. Spawns builder bots and supplies ammo to gunners.
- **Builder Bot** — Explores the map, builds harvesters on ore, and lays conveyors.
- **Harvester** — A building that extracts titanium (resources) from ore tiles.
- **Conveyor** — Moves resources toward the core automatically.
- **Gunner** — A defensive turret that fires at enemies.

### Strategy
1. Core spawns 5 builder bots over time
2. Builders explore and find ore deposits
3. When ore is found, builders construct harvesters + conveyors for resource collection
4. Once economy is running (3+ harvesters), builders switch to building gunners for defense
5. Gunners defend the base by firing at approaching enemies

### Communication Store
Units coordinate via a shared 16-slot memory store:
- **Slots 0-1**: Core position (published by core)
- **Slot 2**: Harvester count (updated when builders build)
- **Slot 3**: Ore location (shared when builders spot ore)
- **Slots 4-15**: Available for your own coordination logic

## Bot Code

Main bot logic is in `bots/starter/main.py`:
- `_run_core()` — Core spawning and ammo management
- `_run_builder()` — Builder exploration, building, and movement
- `_run_gunner()` — Gunner targeting and firing

## Ideas for Improvement

- Coordinate builder roles (explorer vs builder vs defender) using more store slots
- Build complete conveyor chains from harvesters back to core
- Add sentinels or launchers for stronger defense
- Map exploration strategy (systematic vs random)
- Dynamic ammo buffer adjustment based on enemy proximity
- Smarter pathfinding to avoid getting stuck

## Files

- `bots/starter/main.py` — Main bot code
- `fcode.toml` — Bot configuration
- `maps/` — Competition map files

## Useful Commands

```bash
# Run starter bot vs another strategy
fcode run starter starter

# Watch a replay
fcode watch replay.replay26

# See available maps
ls maps/

# Run on a specific map
fcode run starter starter --map maps/fjord.map26
```

## Resources

- [Florent Code League Docs](https://game.code.florent.vc/docs/florent-code-league)
- [Quick Start Tutorial](https://game.code.florent.vc/tutorials/movement-sensing/01-welcome)
