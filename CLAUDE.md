# FCL bot — project context

Two parts: **project-specific findings** (measured here, not in the official docs),
then the **official game/API reference** copied from the Florent docs' AGENTS.md page.

---

# Part 1 — Project notes (read this first)

## What is live

- `bots/scouter2` is the **live ladder bot**. `bots/starter` and `bots/scouter` are not maintained.
- Submit: `fcode submit bots/scouter2 -n <name>` then `fcode submission activate <version>`.
- The CLI is not on the default path: `source /var/home/student/.venvs/fcode/bin/activate`.
- Unrated scrimmages always use the **active** submission, and are rate-limited to
  **5 per 20 minutes**.

## Cost scaling dominates everything

`cost = floor(scale * base)`, and scale rises **per entity built**:

| Category | Scale added each |
| --- | --- |
| conveyor / splitter / barrier | **+1%** |
| harvester | +5% |
| launcher | +10% |
| **builder bot / gunner / sentinel** | **+20%** |

Observed in play: 100% at round 0 → ~212% by round 25 → **340% by round 75**. A 4th
builder bot does not just cost its own inflated 30 Ti, it makes every future harvester,
belt and turret 20% dearer for the rest of the match. `destroy()` is free, has no
cooldown, and **removes that entity's scale contribution** — an unexploited lever.

This one fact retro-explains most failed experiments below. Belts are the *cheapest*
thing in the game; builder bots and turrets are the expensive ones.

## Measured results (all vs. the live bot, 15-map pool, sides swapped, `--tle 0`)

| Change | Games | Win rate |
| --- | --- | --- |
| Threat-scaled ammo buffer | 300 | 54.0% (58.0% then 50.0% — did **not** replicate) |
| Conveyor encoding + chain-cap fix | 240 | 50–52% |
| Chain cap only while economy is dead | 150 | 52.7% |
| Conveyor + ammo + watchdog stacked | 150 | 50.0% |
| Surplus titanium → gunners | 150 | 46.7% |
| Systematic exploration (frontier seeking) | 150 | 34.7% |
| Surplus titanium → builders + ammo | 150 | 32.7% |
| 6 order slots + long chains + wide assignment | 150 | 22.7% |
| Full economy + continuous gunners ("MIXED") | 150 | 21.3% |
| Sentinel cap (1 per builder) | 150 | 48.0% |
| Late builder cull (surplus bot self-destructs r150) | 150 | 48.7% |
| Demand-driven ammo pool | mechanism | rejected — firing rate fell 35% → 14% |
| Siege staging fix (stand beside firing tile) | 150 | 38.0% |

Builder-bot count is a genuine optimum at the current 4 — 2 → 38.7%, 3 → 44.0%,
**4 → baseline**, 5 → 30.7%, 6 → 22.7%. Do not touch it.

**Nothing has beaten the incumbent yet.** The pattern: every change that moves builders
off attacking, or that adds +20% entities, loses. This bot wins by pressure.

## Why the economy plateaus at ~6 harvesters (the deadlock)

Diagnosed by running a 1000-round game and printing the core's own state every
150 rounds. From round ~175 to round 925, on midgard (30x30), the live bot sits at:

    scouted=452/900   unplanned_ore=7   planned=6   queued_tickets=0
    builder_positions=[(0,0), (0,0), (0,0)]   titanium=6293 and climbing

It **knows about 7 unmined ore tiles, has thousands of titanium banked, and builds
nothing for 900 rounds.** Three bugs interlock to cause it:

1. A builder that does not move writes 0 to its scout slot → decodes to
   `Position(0, 0)`, so the core records every builder as standing on the map origin.
2. `dist = 63` is compared against `distance_squared`, so assignment is capped at
   ~8 tiles — of (0,0), a corner the builders are nowhere near. Nothing is ever
   assigned.
3. The 8-tile conveyor cap makes `plan_easiest_harvester` fail for the remaining
   ore, so `queued_tickets` stays 0.

Each of these was fixed individually earlier and each **lost** (43.3%, 50.0%,
50–52%). That is not a contradiction — see below.

## Game length is the hidden variable

Our games end at turn ~85 by core destruction; the Pantheon-vs-Pivot replay ran 364
turns. Economy compounds with time, so in an 85-turn game a harvester barely repays
its own cost and every titanium spent mining is titanium not spent on pressure.

| | harvesters | game length | lifetime income |
| --- | --- | --- | --- |
| us | 7 | 85 turns | ~1,500 Ti |
| Pantheon | 40 | 364 turns | ~36,400 Ti |

That is a 25x gap, and only ~6x of it is harvester count. **The rest is that we die
early.** This is why every economy fix measured badly: they were tested inside a
game length where economy cannot pay. Alone on an empty map for 1000 rounds the
live bot mines 9,860 Ti — the capability is there, the time is not.

Corollary: the economy fixes and the survival strategy are only worth testing
*together*. Separately they each look like losses.

## Turrets: we own more than we can operate

Measured with a probe on `_run_sentinel` counting, per turn, whether a sentinel had a
live target and whether it could actually fire:

| | Opportunities | Fired | Blocked by ammo |
| --- | --- | --- | --- |
| live bot | 1231 | 445 (36%) | 479 |
| sentinel cap 1/builder | 585 | 271 (46%) | 87 |

**Sentinels are idle ~2/3 of the time and ammo is the dominant blocker.** This is
structural, not a buffer-tuning problem: 7 sentinels on a 3-round reload demand ~23
ammo/turn, while passive income is 2.5 Ti/turn and each harvester adds 2.5. Feeding them
would need ~9 harvesters; we field 2-5. No buffer size closes a 5x shortfall.

Capping turrets cures the starvation (479 → 87 blocked) but costs 40% of total shots
(445 → 271) and scores 48.0%. So the ammo-starved 7th sentinel still earns its +20%
scale. Do not "fix" this by building fewer turrets.

Two traps when tuning ammo, both hit here:
- `can_convert_ammo()` is **all-or-nothing** — asking for an unaffordable shortfall
  converts NOTHING, so a bigger target can leave turrets drier than a small one.
- A controller sized from ammo *burned* starves itself: during starvation nothing burns,
  so it reads "no demand" and decays. Treat an empty pool as the demand signal.

## destroy() as a cost-scale lever: measured, not worth it

Scale composition for one team in one game (ragnarok):

| Category | Built | Scale each | Points |
| --- | --- | --- | --- |
| conveyors | 4 | +1% | 4 |
| harvesters | 2 | +5% | 10 |
| builders + turrets | 11 | +20% | **220** |
| | | | 334% total |

**94% of cost scale sits in builders and turrets.** Everything `destroy()` could safely
reclaim (belts, harvesters) is 14 of 234 points — about a 4% discount. The mechanism is
real and unexploited, but there is almost nothing behind it. Culling the surplus builder
late (its +20%, kept through the economy phase, released before the turret push) is the
best available version and tests neutral at 48.7%.

## The siege is limited by money, not positioning

A real off-by-one exists in staging: `tiles_to_attack_core_ct_mode()` returns tiles a
sentinel could fire *from*, and the builder paths **onto** one — but builders may only
build on an orthogonally adjacent tile, so it parks on the good square and inspects
neighbours that do not bear on the core. Across 347 siege turns on ragnarok: 131 had a
buildable adjacent tile, 173 had a bearing tile, only **5** had the same tile do both.

But the bot converts ~100% of those rare chances (5 chances → 5 sentinels). The binding
constraint is money: a sentinel costs 58–105 Ti at our cost scale and we can afford one
only ~66% of the time. Fixing the off-by-one scores **38.0%** — worse, because chasing
stand-beside tiles scatters builders off the approach.

**Launchers are ruled out.** A launcher can only pick up an *adjacent* builder bot, and
enemy builders appear inside our core's vision 0–5 times per game (never on midgard).

## Real-opponent scrimmages (the benchmark that actually counts)

Unrated scrimmage, best-of-5, same five opponents (Pantheon #1, Pivot #2, Lorem Ipsum #5,
Bean counters #9, OopsGotYourElo):

| Submission | Games | Matches |
| --- | --- | --- |
| **v4 (live)** | **6-19** | 1W-4L |
| v5 "MIXED" (economy + continuous gunners) | 1-19 | 0W-4L |
| v6 (conveyor fix + threat ammo + exception guard) | **1-24** | 0W-5L |

**The mirror-bias excuse does not hold.** It was tempting to argue that mirror matches
hide the conveyor bug — on glacierkeep/drakkarfjord/auroraveil both sides mine zero, so
the fix scores ~50% against a copy of itself. The prediction was that it would shine
against opponents with working economies. It did the opposite: 1-24. Fixing the bug still
makes the bot worse in real play. Mirror A/B and real opponents have agreed every time
they were both measured.

**Scrimmaging a candidate costs rating.** Unrated matches need the candidate *activated*,
which means ladder matches use it too. v6 was live ~40 minutes and cost ~18 rating
(1560 → 1542, #41 → #44). Budget for that before testing, and revert promptly.

## Two real bugs whose fixes make it WORSE

Both are genuine defects. Both are accidentally load-bearing — they starve builders of
mining orders, which pushes them into attacking. Do not "fix" either in isolation.

- `dist = 63` in the core's ticket loop is compared against `distance_squared`, so it
  caps order assignment at ~8 tiles (63 is the conveyor-grid sentinel, not a squared
  value). Fixing alone → 50.0%.
- A builder that does not move writes 0 to its scout slot, which decodes to
  `Position(0, 0)`, so the core thinks it is at the origin. Fixing alone → 43.3%.

## Proven bugs worth fixing (written, not merged)

- **All-NORTH conveyor routes are silently dropped.** `CARDINALS.index(NORTH) == 0`, so a
  pure-north route encodes as all-zero bits and `if (number >> 15) > 0` reads it as "no
  path". The builder lays no belts, builds the harvester anyway, and marks the order
  done. On `glacierkeep` this means **0 titanium in 263 turns against an idle opponent**.
  Fix: bit 31 is free — use it as an explicit "path present" flag.
- **8-tile conveyor cap** rejected 609/609 plans on `drakkarfjord` (zero harvesters all
  game). It is an encoding limit, not a game rule.

## Measurement discipline (learned the hard way)

- **150+ games minimum.** One variant read 54.4% at 90 games and 50.7% at 150; another
  read 58.0% then 50.0% on fresh seeds. Replicate on a **different seed range** before
  believing anything.
- Play every (map, seed) **twice with sides swapped**; side bias is large.
- Use `--tle 0` when comparing strategies, or results depend on machine load and
  penalise whichever variant computes more. Check the CPU budget separately with
  `get_cpu_time_elapsed()`.
- `fcode maps sync` first — the repo's `maps/` once held an entirely stale pool.
- **A do-nothing opponent bot is the best debugger.** If economy is still broken with
  nobody attacking, it is a bug, not pressure.
- Check which side you are: a score of `4-1` is team A's. Scrimmages were once misread
  as wins when they were losses.
- **Verify the mechanism before spending a 150-game run.** Expanding the store to 6 order
  slots did not raise harvester count at all — measuring that first saved the run.
- **The bot calls `random` unseeded, so runs are NOT reproducible** even at a fixed
  `--seed`. Identical probe invocations gave 73 vs 0 ammo-blocks on the same map. Never
  trust a single game; aggregate over 20+ before reading a mechanism.
- **Check the mechanism before spending a 150-game run.** Three times this saved a run:
  6 store slots did not raise harvester count, reordering heal/siege did not raise
  sentinel count, and the first ammo controller made firing *worse*.
- Source files are **CRLF**; `sed` patterns anchored with `$` fail silently.

## Where the top bots are ahead

From decoding a Pantheon (#1) vs Pivot (#2) replay, 20x20, 364 turns:

| | Pantheon (won) | Pivot (lost) | Us |
| --- | --- | --- | --- |
| Harvesters | 40 | 23 | 6–9 |
| Gunners | 38 | 23 | **0** |
| Belts per harvester | **1.0** | 2.7 | 3–4 |
| First gunner | turn 22 | turn 22 | never |
| Gunner distance from base | 13 (forward) | 8 (back) | — |

Our most common action is *healing* (115x/game). Copying their composition without their
economy failed badly (21.3%) — they fund 38 gunners with 40 harvesters.

---

# Part 2 — Official reference (from the Florent docs AGENTS.md page)

## What this game is

Two teams each control a fleet of robots on a rectangular grid (8x8 to 30x30, symmetric
by reflection or rotation). A competitor writes a single Python class:

```python
class Player:
    def run(self, ct: Controller) -> None:
        ...
```

`run()` is called once per round for every living unit on the team (the core and every
builder bot, gunner, sentinel, launcher — turrets included). `ct` (a `Controller`) is
unit-scoped: all of its methods act on or query relative to "this unit" unless an
explicit entity `id` is passed. There is no shared game-object; all state is read through
`Controller` getters.

**Win condition:** destroy the enemy core, or have the better tiebreakers after round 1000
(titanium delivered to core → harvesters alive → titanium stored → coinflip).

**Bot file requirements:** entry point must be `main.py` (at the zip root, or inside exactly
one top-level directory) containing a top-level `class Player`. Bots are Python only.
Auxiliary modules may be imported from other files in the same zip. Each unit gets **10ms
CPU time per turn** (with a small rolling 5% buffer) — if exceeded, that turn's `run()` is
interrupted and does not resume next turn. This is different from an uncaught exception:
if `run()` raises anything besides that timeout, the engine prints the traceback and
**permanently destroys that unit** — it will never run again for the rest of the match.

## Core game rules

- Map tiles: `Environment.EMPTY`, `Environment.WALL`, `Environment.ORE_TITANIUM`. Walls block
  building. Harvesters can only be built on ore tiles.
- Resources: one resource type, `ResourceType.TITANIUM`. Each team starts with 500 global
  titanium, plus 10 passive titanium every 4 rounds. Titanium also moves physically through
  the map in stacks of 10 via conveyors/splitters/harvesters, separate from the global pool
  used to pay build costs.
- Ammunition: each team also has a global ammunition balance that turrets fire from. Teams
  start with 0 ammo and there is no passive ammo income — the only source is the core
  converting global titanium into ammunition 1:1 via `convert_ammo(amount)`.
- Global communication store: 16 integer slots (`read_store(index)` / `write_store(index,
  value)`, index 0-15), private per team, shared by all of a team's units. Writes are
  buffered — visible only from the next round, so every unit sees a consistent snapshot
  for the whole round.
- Units vs. buildings: units = core, builder bots, gunners, sentinels, launchers (all except
  builder bots are also buildings). Buildings = everything except builder bots; they're
  immovable. Each team may have at most 50 living units at once
  (`GameConstants.MAX_TEAM_UNITS`), including the core — check with `get_unit_count()`.
- Cooldowns: every unit has an action cooldown and (builder bots only) a move cooldown, both
  nonnegative integers that decrease by 1 at end of round. Actions/movement require
  cooldown == 0, and acting or moving is mutually exclusive per round for builder bots —
  doing one blocks the other until next round.
- Cost scaling: every buildable entity's cost is `floor(scale * base_cost)`, where scale
  starts at 1.0 and rises as you build more of that category (conveyors/splitters/barriers
  +1% each, harvesters +5% each, launchers +10% each, builder bots/gunners/sentinels +20%
  each — destroying an entity removes its contribution). Use the `get_<entity>_cost()`
  getters rather than hardcoding base costs.
- Vision vs. action vs. attack radius: vision = what a unit can sense; the core has an action
  radius of sqrt(8), used to determine where it may spawn builder bots — no other unit has a
  radius-based action range: all builder bot actions (build/attack/heal/destroy) require an
  orthogonally adjacent tile; turrets additionally have an attack range for firing, separate
  from vision.
- Resource distribution happens once at end of round, after all units have acted.
  Conveyors/splitters/harvesters form a purely economic pipeline into the core — turrets do
  not participate and never hold or accept resources. Resources can still be pushed onto an
  opposing team's conveyor network or core.

## Entities

| Entity | HP | Base cost | Scale/build | Notes |
| --- | --- | --- | --- | --- |
| Core | 500 | — | — | 2x2 footprint; vision r²=36, action r²=8; spawns ≤1 builder bot/turn on an adjacent tile |
| Builder bot | 40 | 30 Ti | +20% | Only mobile unit; vision r²=20; build/attack/heal/destroy all require an orthogonally adjacent tile |
| Conveyor | 20 | 3 Ti | +1% | Faces a cardinal direction; accepts from 3 sides, outputs to the 4th |
| Splitter | 20 | 6 Ti | +1% | Accepts only from the back; rotates output among 3 directions, least-recently-used first |
| Harvester | 30 | 20 Ti | +5% | Built on ore; outputs a stack every 4 rounds (first stack immediately on build) |
| Barrier | 30 | 3 Ti | +1% | Cheap HP wall, no other function |
| Gunner | 25 | 20 Ti | +20% | Facing turret, vision/attack r²=13; straight-line shot, dmg 7, reload 1, 4 ammo/shot; `rotate()` costs 10 Ti + 1 cooldown |
| Sentinel | 40 | 30 Ti | +20% | Facing turret, vision/attack r²=32; single-tile-wide line shot that **ignores obstacles** (unlike Gunner), dmg 18, reload 2, 10 ammo/shot |
| Launcher | 30 | 20 Ti | +10% | Facing-independent, vision/attack r²=26; picks up an adjacent builder bot from either team and throws it to a passable tile |

Builder bot actions per turn (cooldown-gated, one per turn): **build** (any building type on
an orthogonally adjacent empty tile), **attack** (2 Ti → 2 dmg to the building on an
orthogonally adjacent tile), **heal** (1 Ti → +4 HP to all friendly entities on an
orthogonally adjacent tile), **destroy** (any allied building on an orthogonally adjacent
tile — unlimited per turn, no cooldown), **self-destruct** (no damage dealt).

Turrets fire from the team's global ammunition balance (gunner 4/shot, sentinel 10/shot;
launchers use no ammo). The core converts titanium into ammunition 1:1 with
`convert_ammo(amount)`: at most once per team per turn, usable the same turn, and it does
**not** use the core's action cooldown.

## Controller API

**Info/queries:** `get_team(id)`, `get_position(id)`, `get_id()`, `get_action_cooldown()`,
`get_move_cooldown()`, `get_vision_radius_sq(id)`, `get_hp(id)`, `get_max_hp(id)`,
`get_entity_type(id)`, `get_direction(id)`, `get_stored_resource(id)`,
`get_stored_resource_id(id)`, `get_tile_env(pos)`, `get_tile_building_id(pos)`,
`get_tile_builder_bot_id(pos)`, `is_tile_empty(pos)`, `is_tile_passable(pos)`,
`is_in_vision(pos)`, `get_nearby_tiles(dist_sq)`, `get_nearby_entities(dist_sq)`,
`get_nearby_buildings(dist_sq)`, `get_nearby_units(dist_sq)`, `get_map_width()`,
`get_map_height()`, `get_current_round()`, `get_global_resources()`, `get_global_ammo()`,
`get_scale_percent()`, `get_cpu_time_elapsed()`, `get_unit_count()`.

**Cost getters:** `get_conveyor_cost()`, `get_splitter_cost()`, `get_harvester_cost()`,
`get_barrier_cost()`, `get_gunner_cost()`, `get_sentinel_cost()`, `get_launcher_cost()`,
`get_builder_bot_cost()`. Always prefer these over hardcoded base costs.

**Movement (builder bots only):** `can_move(direction)`, `move(direction)`.

**Building:** `can_build_*(...)` / `build_*(...)` for conveyor, splitter, harvester, barrier,
gunner, sentinel, launcher — conveyor/splitter/gunner/sentinel need `(position, direction)`;
harvester/barrier/launcher need only `(position)`. Position must be orthogonally adjacent,
not diagonal, not the builder's own tile. Generic forms: `can_build(type, pos, extra)` /
`build(type, pos, extra)`.

**Healing/destruction (builder bots only):** `can_heal(pos)` / `heal(pos)`,
`can_destroy(building_pos)` / `destroy(building_pos)` (free, no cooldown, unlimited per
turn), `self_destruct()`, `resign(message)`.

**Store:** `read_store(index)` / `write_store(index, value)`, index 0..15, buffered until
next round.

**Turrets:** `can_fire(target)` / `fire(target)`,
`can_fire_from(position, direction, turret_type, target)`, `can_rotate(direction)` /
`rotate(direction)` (gunner only, 10 Ti), `get_gunner_target()`, `get_attackable_tiles()`,
`get_attackable_tiles_from(position, direction, turret_type)`,
`can_launch(bot_pos, target)` / `launch(bot_pos, target)`.

**Core:** `can_spawn(position)`, `spawn_builder(position)`, `can_convert_ammo(amount)`,
`convert_ammo(amount)`.

**Debugging:** `draw_indicator_line(a, b, r, g, b)`, `draw_indicator_dot(pos, r, g, b)`.
`print()` is captured into the replay; use **stderr** for console-only output (and note that
per-unit-per-round printing is a measurable CPU cost).

## Key types

- `Direction`: NORTH, NORTHEAST, EAST, SOUTHEAST, SOUTH, SOUTHWEST, WEST, NORTHWEST, CENTRE.
  `(0, 0)` is the map's **northwest** corner, x grows east, y grows south, so **NORTH is
  (0, −1)**. Methods: `.delta()`, `.rotate_left()`, `.rotate_right()`, `.opposite()`,
  `.is_cardinal()`. Builder bots may only **move** cardinally; all 8 directions are valid for
  turret facing and building orientation.
- `Position(x, y)` (NamedTuple): `.add(direction)`, `.distance_squared(other)`,
  `.direction_to(other)` (may be diagonal), `.cardinal_direction_to(other)` (use this for
  builder moves). Note `Position(0, 0)` is **truthy**, which has caused a real bug here.
- `EntityType`, `Environment`, `Team`, `ResourceType`, `GameConstants`.
- `GameError` is raised by any illegal action. Always gate with the matching `can_*()`.
  **An uncaught exception permanently destroys that unit for the rest of the match.**

## Notes for the coding agent

- Entry point is always a top-level `class Player` with `run(self, ct)` in `main.py`.
- Always gate actions with the matching `can_*()` check — the engine raises `GameError`
  rather than silently no-opping.
- Prefer `get_*_cost()` and `GameConstants` over hardcoded numbers.
- Branch on `ct.get_entity_type()` at the top of `run()`.
- Each unit has its own 10ms budget; avoid unbounded loops or whole-map recomputation
  every round.
- Stay consistent with this API rather than inventing methods.
