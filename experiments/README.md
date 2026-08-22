# experiments/

Tooling and every strategy variant tried on `bots/scouter2`, kept so results are
reproducible without re-deriving them. Measured outcomes are in `../CLAUDE.md`;
this directory is the *how*.

## Tooling

| File | What it does |
| --- | --- |
| `ab.py` | A/B two bot directories over the 15-map pool, sides swapped. The main instrument. |
| `results.py` | Reads ladder/unrated match results, resolving which side we were on. |
| `pbdump.py` | Protobuf wire-format walker for `.replay26` — used to decode opponents' builds. |
| `firepower.sh` | Aggregates sentinel firing-rate / ammo-starvation over many games. |
| `idle/` | A do-nothing opponent. The single best debugging tool here. |
| `hunter/` | Lab opponent that builds a forward line of sentinels and **prefers builder-bot targets**. The only way to test losing units: the mirror kills 0 enemy builders in 20 games. |
| `waller/` | Lab opponent that rings its own core in barriers. Tests routing through obstacles, which no mirror game ever produces. |
| `map_audit.py` | Plays every map in `../maps` against a fixed opponent **with the TLE on**, flagging maps we lose, take >250 turns on, or mine nothing on — plus any traceback. Found the `bridge` crash. |
| `stall_check.py` | Aggregates N games per map against a fixed opponent (`--opp`). Use instead of `map_audit` whenever comparing two variants: 2 seeds is pure noise here. |
| `ladder_stats.py` | Aggregates our real ladder games by map, win condition and length. Read-only. |
| `patch_probe.py` | Makes a bot log every build it makes, one stderr line each. |
| `probe_stats.py` | Aggregates those over the pool: harvesters by turn N, belts each, titanium. |
| `patch_econdiag.py` | Dumps each `bots/econ` builder's planner state every N rounds. |

### The mirror measures strategy, not robustness

`ab.py` plays the bot against a copy of itself, so any defect both copies share
cancels and reads ~50%. Instrumented over 20 mirror games, our bot killed
**0** enemy builder bots — it shoots cores and things in its way, never units —
so no A/B in this repo has ever tested what happens when we lose a builder, and
neither side ever walls anything, so none has tested a blocked route either. For
anything in that class, measure against `hunter/` or `waller/` with
`stall_check.py`, and treat the mirror only as a check that the change does not
regress the strategy.

### Gate 1 before gate 2

`probe_stats.py` answers "did the mechanism actually move?" in about a minute,
against `idle/` so nothing else is in the way. Run it before committing to a
150-game A/B — three separate runs were saved that way, and the economy rewrite
was steered by it four times.

```bash
cp -r ../bots/econ /tmp/cand && python3 patch_probe.py /tmp/cand
python3 probe_stats.py /tmp/cand --seeds 2 --jobs 10
```

### Running an A/B

```bash
source /var/home/student/.venvs/fcode/bin/activate
cp -r ../bots/scouter2 /tmp/base            # the incumbent
cp -r ../bots/scouter2 /tmp/cand            # a candidate
python3 patch_conveyor.py /tmp/cand         # apply whichever patches
python3 ab.py /tmp/cand /tmp/base --seeds 5 --jobs 8 --tle 0
```

**Use `--tle 0`** or results depend on machine load. **150+ games**, then replicate on a
fresh `--seed-start`; one variant read 54.4% at 90 games and 50.7% at 150, another 58.0%
then 50.0%. The bot calls `random` unseeded, so single games are not reproducible at all.

## The patches

Each is a standalone, commented transform of a bot directory, and each docstring records
*why* the change was tried and what it measured. Applying several composes them.

**Robustness fixes (this batch).** `patch_mapguard` (an `IndexError` off the edge
of the map in `Map.configure`, which permanently destroys a builder — the `bridge`
traceback), `patch_oob` (three unguarded `get_tile_building_id()` calls; every
`can_*()` is safe out of bounds but that getter raises), `patch_giveup` (drop a
build order that has gone nowhere for 20 rounds and rejoin the siege — the fix for
builders frozen from round 100 to 1000), `patch_respawn` (replace builders that
die; the core's `bots_made` only ever increments), `patch_defend` (make the
builders spawned *because the core is being hit* defend instead of marching at the
enemy core), `patch_blocked` (feed known-unwalkable tiles to BFS, only spend a path
step that was actually taken, sidestep or break through when boxed in).

`patch_symcommit` is in the same family but **measured worse** — see CLAUDE.md.

**Bug fixes (all proven real).** `patch_conveyor` (all-NORTH routes silently dropped +
8-tile chain cap), `patch_dist` (the ~8-tile order radius), `patch_pos` (builders decoding
to `Position(0,0)`), `patch_guard` (an uncaught exception permanently destroys that unit),
`patch_unstick` (builder wedged on an unbuildable tile), `patch_ownteam` (own-core check
accepted the enemy core).

> The first three each *lower* win rate in isolation. They interlock into the economy
> deadlock described in CLAUDE.md, and only pay in a game long enough for economy to
> compound. Do not apply them one at a time and conclude they are bad.

**Strategy variants.** `patch_turtle` (+ `_def`, `_explore`, `patch_bank`) is the drastic
rewrite: fortify, mine, play the round-1000 tiebreak. `patch_raid` wrecks enemy
infrastructure in passing. `patch_lean` sweeps builder count. `patch_sentcap`,
`patch_ammo`, `patch_ammo2` address turret supply. `patch_roles` widens the store to 6
build orders. `patch_explore`, `patch_stage`, `patch_standoff`, `patch_siege`,
`patch_cull`, `patch_cheapbelt`, `patch_noattack` are the rest.

**The economy rewrite.** `../bots/econ` is not a patch but a separate bot: the core
plans no economy, and each builder greedily extends one shared conveyor network
(`network.py`). `patch_econsplit` sets how many builders mine and when they give
up and siege, `patch_reach` caps how far a belt run may go, `patch_ammo3` is the
ammo top-up rewritten to step down rather than convert nothing, and
`patch_pathstep` is the movement bug the rewrite uncovered, backported to
`scouter2` so it can be measured on its own.

Every one of them measured below the incumbent. See `../CLAUDE.md` for the table.
