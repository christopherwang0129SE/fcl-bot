# FCL bot — project context

Two parts: **project-specific findings** (measured here, not in the official docs),
then the **official game/API reference** copied from the Florent docs' AGENTS.md page.

---

# Part 1 — Project notes (read this first)

## Start here (new session)

- **Read the measured-results table below before proposing anything.** 15 changes have been
  tested over ~3,000 games and none beat the incumbent; most "obvious" fixes are in there
  already, several of them measured *worse*.
- Reproduce any of it with `experiments/` — `ab.py` is the A/B harness, and every variant
  is a commented patch script that says why it was tried and what it scored.
- Full write-up with charts: https://claude.ai/code/artifact/d7262cab-eb7e-452a-a24c-c7da7e29972a
- Before testing: `source /var/home/student/.venvs/fcode/bin/activate` and `fcode maps sync`.
- The `origin` remote uses SSH (HTTPS has no credentials here).

## What is live

- `bots/scouter2-robust` is the **live ladder bot** (submission **v8 `robust-ecocap5`**,
  activated 2026-08-22; an earlier version of this file wrongly named `scouter3`). It is
  `scouter2` plus six patch scripts: `patch_mapguard`, `patch_oob`, `patch_blocked`,
  `patch_siegepick`, `patch_respawn`, `patch_ecocap 5`. Rebuild it from scratch at any
  time by applying those six to a copy of `bots/scouter2`.
- `bots/scouter2` is the v4 bot and the **A/B baseline** for every measurement in the big
  table below. Newer work is measured against `scouter2-robust` instead — say which.
- `bots/starter` and `bots/scouter` are not maintained.

- Submit: `fcode submit <botdir> -n <name>` — note this **auto-activates** the new version,
  it is not a two-step process any more. `fcode submission activate <version>` reverts.
- `fcode submit` has no `--json`. `fcode ladder --json` returns only the top 20; use
  `fcode ladder --around --json` for the teams either side of us, which are the ones worth
  scrimmaging (against a 2100-rated bot we lose whatever we change).
- The CLI is not on the default path: `source /var/home/student/.venvs/fcode/bin/activate`.
- Unrated scrimmages always use the **active** submission, and are rate-limited to
  **5 per 10 minutes** (the CLI error says 10, not the 20 previously recorded here).

### The two lineages (there are two people working on this)

| Bot | Lineage | What it is |
| --- | --- | --- |
| `scouter2` | — | v4, the old baseline |
| `scouter2-robust` | ours | **v8, live.** scouter2 + the 6 robustness/ecocap patches |
| `scouter2-patched` | theirs | **scouter2-robust + `patch_conveyor`. The best bot measured.** |
| `scouter3` | theirs | economy rewrite; 48.7% vs v4, loses 71.3% to v8, stalls 12/12 on longhouse |
| `scouter4` | theirs | scouter3 + gunner units, defensive builders, KIA detection, save-money |
| `scouter4-patched` | theirs | scouter4 + ecocap5 |
| `scouter5` | ours | scouter4-patched + `patch_robustpath` (v8's pathfinding ported across) |
| `econ` | ours | the abandoned economy rewrite, 10.7% — kept as evidence, do not revive |

The two lineages are **complementary, not competing**, and the per-map records prove it:
scouter4 beats v8 10-0 on drakkarfjord, 9-1 on fjordgate and nordkap (its planner handles
long belt runs), and loses 0-10 on yulerune, midgard, royale and archipelago (its builders
keep no map, so they cannot plan a march longer than their vision radius). Merge in both
directions rather than picking a side.

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
| Raid enemy harvesters/belts in passing | 150 | 32.0% |
| Turtle: fortify + mine + play the round-1000 tiebreak | 90 | 36.7% |
| Turtle + all three economy fixes | 90 | **42.2%** |
| **Economy rewrite** (local-greedy, `bots/econ`) | 150 | **10.7%** |
| ...2 of 4 builders mine | 60 | 28.3% |
| ...1 of 4 builders mines | 60 | 30.0% |
| ...all mine, all siege from turn 30 | 60 | 33.3% |
| ...all mine, all siege from turn 50 | 60 | 36.7% |
| ...all mine, belt runs capped at 4 / 2 / 0 | 60 ea | 21.7% / 18.3% / 16.7% |
| ...5 builders, 1 mines (siege force kept at 4) | 60 | 33.3% |
| ...6 builders, 1 mines / 2 mine | 60 ea | 23.3% / 15.0% |
| ...detour cap of 5 / 8 tiles on taking a mining job | mechanism | rejected — still 0-2 sentinels |
| Path-step fix (don't spend a step you didn't move) | 60 | 40.0% |
| Ammo top-up stepped down instead of all-or-nothing, target 40 | 150 | 45.3% (55.0% at 60 — did **not** replicate) |
| ...same, target 20 (isolates the step-down alone) | 60 | 41.7% |
| ...same, target 80 | 60 | 50.0% |
| Crash guards only (`patch_mapguard` + `patch_oob`) | 150 | 52.7% |
| Blocked-tile pathfinding + path-step fix (`patch_blocked`) | 300 | 54.3% (54.0 / 54.7) |
| Robustness bundle (guards + blocked + siegepick + respawn) | 450 | 53.3% (58.0 / 52.7 / 49.3) |
| Conveyor fix alone (`patch_conveyor`) | 450 | 56.9% (60.0 / 56.7 / 54.0) |
| **Economy capped at 4 harvester orders** (`patch_ecocap 4`) | **450** | **65.1%** (60.7 / 65.3 / 69.3) |
| **Economy capped at 5** (`patch_ecocap 5`) | **450** | **69.6%** (68.0 / 70.7 / 70.0) |
| ...cap 1 / 2 / 3 / 6 / 8 | 150 ea | 27.3% / 51.3% / 57.3% / 60.0% / 52.0% |
| Robustness + conveyor | 450 | 62.4% (58.7 / 68.0 / 60.7) |
| **Robustness + economy cap** | **450** | **66.9%** (68.0 / 67.3 / 65.3) |
| No new harvester orders after round 40 (`patch_ecocap 99 40`) | 150 | 52.0% |
| Siege-target picking alone (`patch_siegepick`) | 150 | 48.0% |
| Replace builders that die (`patch_respawn`) | 150 | 48.7% |
| Drop a build order going nowhere (`patch_giveup`) | 150 | 48.0% |
| ...crash guards + give-up together | 150 | 43.3% |
| **Defend with the damage-response builders** (`patch_defend`) | 150 | **35.3%** |
| Commit to a map symmetry (`patch_symcommit`) | 12/map | rejected — yulerune stalls 8/12 → **12/12** |

### Measured against **`scouter2-robust` (v8)**, not scouter2 — 2026-08-23

Everything above is vs the v4 baseline. These are vs the live v8, legacy 15-map
pool, seeds 1-5, `--tle 0`:

| Change | Games | Win rate |
| --- | --- | --- |
| `scouter4` (their gunner/defence bot) | 150 | 42.7% |
| `scouter4-patched` (+ `patch_ecocap 5`) | 150 | 53.3% |
| **`scouter2-patched` (v8 + `patch_conveyor`)** | **450** | **62.0%** (66.7 / 59.3 / 60.0) |
| `scouter5` (`scouter4-patched` + `patch_robustpath`) | 150 | 50.0% |
| `scouter5` vs `scouter2-patched` | 150 | 44.0% |
| `scouter4-patched` vs `scouter2-patched` | 150 | 46.7% |

**Beware the baseline when someone quotes a win rate.** Two figures circulated in the team
chat and they are not the same kind of error:

- *"scouter2-patched is 88% (132-18)"* — a **correct measurement against the wrong
  baseline**. Reproduced here at **79.3%** (119-31) vs `bots/scouter2`, i.e. v4, two
  submissions old. Against the bot that is actually live it is 62%. Both numbers are real;
  only the second one tells you whether to ship.
- *"80%, scouter4 vs scouter2, both patched"* — **contradicted by direct measurement**.
  `scouter4-patched` vs `scouter2-patched` is **46.7%** (70-80): it loses. See the
  side-confusion warning in the measurement-discipline section.

Always name the opponent directory when quoting a win rate.

Two things to take from this:

- **`patch_ecocap 5` transfers across the lineage split.** It is the single most
  portable change in the project: +10.6 points dropped into a bot it was never
  written for, enough to carry it past v8. Try it on anything new.
**`scouter2-patched` replicates, on both pools.** Three independent seed ranges on the
legacy pool (1-5, 11-15, 21-25) give 66.7 / 59.3 / 60.0, pooled **62.0% over 450 games**;
two ranges on the ladder pool give 57.3 / 59.3, pooled **58.3% over 300 games**. As always
the first range was the optimistic one — but unlike every previous promising result in
this file it settled at ~60% instead of decaying to 50%.

The per-map pattern is stable across every run:

| Consistently won | Consistently lost |
| --- | --- |
| glacierkeep **10-0** (all three runs) | **paths 0-10** (both ladder runs) |
| jotunheim **10-0**, bifrost **10-0** | valkyrie 3-7 / 2-8 |
| ragnarok 10-0, fimbulwinter 9-1/10-0 | |
| drakkarfjord 8-2 | |

`paths` is a genuine, reproducible cost — we are 12-5 on it on the ladder today. It is one
map against glacierkeep + jotunheim + bifrost, which are **8-46** on the ladder, so the
trade is heavily favourable, but it is a real trade and not noise. Neither map stalls: vs
the idle bot both bots win `longhouse` and `paths` in the same turn count (102 vs 104, 54
vs 56), so the mirror losses there are a race, not a defect.

- **`patch_robustpath` is a real fix that does not pay.** Porting v8's local-map
  BFS into the scouter4 line did exactly what it was designed to do — yulerune
  0-10 → 2-8, midgard 0-10 → 2-8, auroraveil 6-4 → 10-0, frostgate 0-10 → 4-6 —
  and lost more than it gained elsewhere: icefloe 5-5 → **0-10**, drumlin 5-5 →
  **0-10**, royale 10-0 → 5-5, ragnarok 10-0 → 6-4. Net 53.3% → 50.0%. This is
  the same shape as the `dist = 63` and `Position(0,0)` findings: the defect is
  genuine and the wandering it causes is accidentally load-bearing. The patch is
  kept in `experiments/` as evidence, not as a candidate.

Builder-bot count is a genuine optimum at the current 4 — 2 → 38.7%, 3 → 44.0%,
**4 → baseline**, 5 → 30.7%, 6 → 22.7%. Do not touch it.

**No change to *strategy* has ever beaten the incumbent, across 25 changes and ~4,500
games.** That pattern is unambiguous: *any* use of a builder's action other than "walk at
the enemy core and place a sentinel that bears on it" loses. Mining loses, exploring
loses, defending loses (35.3% — measured again this session, in its narrowest form),
healing more loses, raiding their belts loses (32.0% — firing costs the action cooldown,
so a raiding builder stops advancing and stops sieging), and even *better siege
positioning* loses (38.0%). Adding +20% entities loses. This bot wins by pressure, and it
is a sharp local optimum.

**Robustness is a different axis, and it is not exhausted.** The first changes to beat
the incumbent on a replicated measurement are not strategy at all — they are fixes for
builders that stop working: `patch_blocked` at 54.3% over 300 games across two
independent seed ranges, and the bundle around it at 55.3%. They do not change what a
builder wants to do; they stop it wandering, freezing or dying to an exception on the way
to doing it. Every previous session searched the strategy axis, which is why ~3,800 games
found nothing: the wins were not there.

**What that implies for the economy.** Pantheon's shape is 17 harvesters by turn 82 at ~1
belt each, funding continuous gunners from turn 22. Our architecture cannot reach that:
one harvester per build order, three orders, a chain per harvester, and builders whose
default job is a cross-map march. Closing that gap is a rewrite, not a patch. But note
that the economy plateau and the freezes share a cause — a builder rattling between two
tiles for 900 rounds is not mining either — so some of what looked like an economy
ceiling was builders that had simply stopped.

## Reading real opponents' replays (new tooling, 2026-08-23)

`fcode match list --team <id>` works for **any** team, and `fcode match replay`
downloads their games. So the whole ladder is observable and nobody had looked.

- `experiments/replay_read.py` — decodes a `.replay26` into an event log
  (spawns, moves, deaths, fire events with source and target).
- `experiments/profile_bot.py` — turns replays into composition and timing:
  what each side built, on what turn, how far forward.
- `experiments/tempo.py` — turn of our first sentinel and of its first shot on
  the enemy core. The mirror is blind to tempo, because both copies are equally
  slow.
- `experiments/rusher` — lab opponent: our bot with the economy switched off.

Validated by reproducing a known game spawn-for-spawn. Caveat: on some replays
it reports impossible states (a winner with zero conveyors), so cross-check
before trusting a single game.

### Why we lose the fast games

Three real losses to Jacobs Code, all the same shape: their sentinel is firing
on our core by turn 8-12, ours does not answer until turn 30+. But the fix is
not what it looks like:

| | measured |
| --- | --- |
| our median first sentinel | **turn 34** |
| ...with the economy removed entirely | turn 30 |
| movement rate, both teams | ~0.85 tiles/turn — identical |
| our bot vs `experiments/rusher` (4 builders, no economy) | **150-0** |

So economy costs ~4 turns, not 20, and a naive economy-free rush is simply bad.
On midgard the trace shows our builder walking 38 tiles in 40 turns in a
straight line and planting a sentinel the instant it is in range: **the march is
geometry, not a bug.**

### Copying the winning composition: 26th failed strategy experiment

Profiling Ouroboros (#33, swept us 0-5) and `not adgato` (#1) shows the same
shape in every game from both teams: **1 builder, 0 conveyors, 1 harvester beside
their own core on turn 3, then 4 sentinels planted 18-22 tiles out on our core**,
game over by turn 37-48. We field 4-6 builders, 15-20 conveyors and manage 1-2
sentinels. The cost-scale arithmetic is compelling — at one builder their scale
sits near 120% so four sentinels cost ~180 Ti, against our 230-260% where each
costs 69-78.

It does not transfer. Against the live v10 on the ladder pool, 150 games each:

| builders / harvester orders | win rate |
| --- | --- |
| **1 / 1 (the exact copy)** | **5.3%** |
| 1 / 2 | 30.7% |
| 2 / 1 | 30.0% |
| 2 / 2 | 33.3% |

Monotone, and continuous with the existing builder sweep (2 -> 38.7%, 3 -> 44.0%,
4 -> baseline). **Builder count 4 is confirmed optimal from below as well as
above.** `experiments/patch_minimal.py` reproduces it.

The composition is downstream of execution we do not have: Ouroboros gets **four
sentinels out of one builder**, we place one or two even with four. CLAUDE.md
already measured why — of 347 siege turns only **5** had a tile that was both
buildable-adjacent and bearing on the core. That ratio, not builder count, is the
real gap. Do not copy a top bot's composition again; that is now 0 for 4
(Pantheon's composition 21.3%, the econ rewrite 10.7%, MIXED 1-19 in real games,
this 5.3%).

### The launcher catapult: the mechanism works, the win rate does not

`experiments/patch_catapult.py`. The bot implements CORE, BUILDER_BOT and
SENTINEL only -- the launcher had never been given any code. The dismissal in
this file covers only the *defensive* use (throwing enemy builders away from our
core, which needs enemy builders to appear there). The offensive use is the one
thing in the API that changes **geometry**, which is the bottleneck this session
measured: a launcher picks up an adjacent builder from either team and throws it
r^2=26, about 5.1 tiles, for 20 Ti and **+10% scale -- half a turret's**. Five
tiles for one turn's work against 0.85 tiles/turn on foot.

It works mechanically. Instrumented over 3 games: **11 launches against 0 for the
incumbent**, and on `yggdrasil` time-to-first-sentinel went **67 -> 31 turns**.
Note the first implementation *lost* tempo (median 43 vs 34) because the builder
laid the launcher behind itself and marched out of range before the launcher's
turn; it has to build **ahead** and hold position one turn to be picked up.

Measured against the live v10, ladder pool, 150 games each:

| max launchers | win rate |
| --- | --- |
| 2 | 25.3% |
| 3 | 24.7% |
| 5 | 20.0% |

Monotone in the wrong direction, which is the signature of cost scale: the siege
is money-limited (a sentinel costs 58-105 Ti at our scale and we can afford one
only ~66% of the time), so spending on *transport* makes the thing being
transported to more expensive. Faster arrival with less money to spend on arrival
is not a trade that pays.

**Every offensive option in the API has now been tried.** Gunner 18.7% (and it
cannot even reach the core from a sentinel tile), launcher 20-25%, builder attack
is 2 damage for 2 Ti so 250 hits kill a core, and `SELF_DESTRUCT_DAMAGE = 0`.
The sentinel-only siege the incumbent already runs is the whole of the good news.

### Gunners cannot reach the core from a sentinel siege tile

Measured while building `experiments/patch_hailmary.py`, and it closes off a
whole family of ideas: **gunner range is r^2=13 (3.6 tiles), sentinel range is
r^2=32 (5.6 tiles)**. Our builders stand at *sentinel* standoff, so
`can_fire_from(tile, dir, GUNNER, core_tile)` is False everywhere they ever
stand -- the first version of the patch built **zero** gunners in every game.
A gunner is only placeable against the enemy's *forward buildings*, which is
exactly why Bean counters puts its eight gunners 26 tiles out rather than on
our core. That placement is forced by the range, not chosen.

Retargeted at any enemy building in sight the mechanism does fire -- 11-14
gunners against 4-5 sentinels per 3 games, i.e. Bean counters' shape -- and it
still loses: **18.7% over 150 games**, with or without deferring the heal.
That is within noise of v5 MIXED's 21.3%, the same idea measured a year of
experiments earlier.

**Copying a top team's composition is now 0 for 5**: Pantheon's composition
21.3% (1-19 in real games as v5), the econ rewrite 10.7%, Ouroboros' 1-builder
shape 5.3%, forward gunners 18.7%. The composition is always downstream of an
economy or an execution we do not have. Stop trying this.

### What the cutoff band actually looks like

Unrated scrimmages, v10 active, against the teams on the top-32 line:
**10-15 = 40.0%**, where Elo predicts 31% for our rating. We take the series off
**Atlas (#31) 3-2** and **0033 (#32) 3-2**, and get swept 0-5 by Ouroboros (#33).
Two loss shapes: fast (turns 38-53, tempo) and long grinds (250-420 turns,
attrition). Scrimmage the #28-36 band, not the top five — against a bot 600-800
points above us we lose whatever we change.

## The ladder after v8: 37.7% -> 51.0% (300 games, `experiments/ladder_stats.py`)

Re-run 2026-08-23, one day after activating v8 `robust-ecocap5`, over the 300
most recent ladder games. This is the same instrument as the v4 baseline below
and it is the strongest evidence in this file that the robustness axis was the
right one:

| | v4 baseline | **v8 now** |
| --- | --- | --- |
| Ladder record | 113-187 = **37.7%** | 153-147 = **51.0%** |
| Rank / rating | #54 / 1409 | **#44 / 1539** |
| Median turns when we lose | 154 | **81** |
| Losses running past turn 200 | 37.9% | **29.9%** |
| longhouse | **1-18 (5.3%)** | **13-4 (76.5%)** |

`longhouse` — the map `patch_blocked` was diagnosed on, and our worst map on the
board — went from 5.3% to 76.5%. The stall diagnosis and its fix are confirmed
on real opponents, not just against the idle bot.

### What is left, and it is concentrated

| Map | v8 ladder | Note |
| --- | --- | --- |
| glacierkeep | **1-13 (7.1%)** | mines **0** titanium — conveyor encoding |
| jotunheim | **2-18 (10.0%)** | mines **0** titanium — conveyor encoding |
| bifrost | 5-15 (25.0%) | new; not in either audit yet |
| midgard | 23-4 (85.2%) | best map |
| longhouse | 13-4 (76.5%) | was 1-18 |
| paths | 12-5 (70.6%) | |

**glacierkeep + jotunheim are 3-31 between them.** They are exactly the two maps
the audit calls "mines NOTHING", and 16 of our 147 losses were decided on
`titanium_collected` — which is automatic on a map where we mine zero. Verified
directly against the do-nothing opponent (one game each, seed 3):

| map | v8 | v8 + `patch_conveyor` |
| --- | --- | --- |
| glacierkeep | **0 Ti**, 109 turns | **330 Ti**, 63 turns |
| jotunheim | **0 Ti**, 77 turns | **220 Ti**, 55 turns |
| bifrost | 270 Ti, 61 turns | 390 Ti, 59 turns |

This is the largest identified lever left on the live bot. Note the earlier
warning in this file — v6 (conveyor fix on top of *v4*) scrimmaged 1-24 — was
measured before any of the robustness work existed, on the top-tier opponent set
we lose to regardless.

**Caution on the loss-shape table below.** Under v8 the share of losses ending
before turn 60 is 34.0%, not 6.5%. That is not a new vulnerability to rushes:
games are simply much shorter now in both directions (median win 71, median loss
81), so the same absolute number of fast losses is a much larger share. The
absolute stall tail is what shrank.

## What the v4 baseline ladder said (300 games, kept for comparison)

Read-only, costs nothing, and nobody had looked before. Overall **113-187 =
37.7%**, and the per-map record lines up almost exactly with what the
do-nothing-opponent audit flags:

| Map | Ladder | What the audit says about it |
| --- | --- | --- |
| longhouse | **1-18 (5.3%)** | median 1000 turns vs idle, 8/12 games never end |
| glacierkeep | 3-20 (13.0%) | mines **0** titanium (all-NORTH conveyor routes dropped) |
| jotunheim | 3-19 (13.6%) | mines **0** titanium |
| valkyrie | 2-12 (14.3%) | mines 130 Ti, lowest non-zero on the board |
| icefloe | 5-17 (22.7%) | — |
| stavkirke | 15-7 (68.2%) | normal |
| midgard | 11-6 (64.7%) | normal |

Two more things fall out of it:

- **We are not being rushed down.** Only **12 of 185 losses (6.5%) end before
  turn 60**. The distribution of our losses:

  | turns | share of losses |
  | --- | --- |
  | <60 (rushed) | 6.5% |
  | 60-99 | 19.5% |
  | 100-199 | 36.2% |
  | 200-499 | 24.9% |
  | 500+ / tiebreak | 13.0% |

  Median turns when we **win**: 87. Median when we **lose**: 154. We win fast and
  lose slow — 38% of losses run past turn 200. That is the signature of a bot
  that stops making progress and gets ground down, not one that gets killed early.
  Anyone proposing defensive play as the fix should look at this table first.
- **18 losses were decided at the round-1000 tiebreak** (17 on titanium
  collected, 1 on titanium stored). Those are the stall games.

Note `longhouse` and `jotunheim` are not in the 15-map A/B pool at all, so no
amount of A/B tuning could ever have seen our two worst maps.

## The A/B pool and the ladder pool are different pools

Measured 2026-08-23 from 300 real games: the ladder draws from

    auroraveil bifrost fimbulwinter glacierkeep helheim holmgang icefloe
    jotunheim longhouse midgard paths skald stavkirke valkyrie yggdrasil

and the 15-map A/B pool shares only **five** of them (auroraveil, glacierkeep,
icefloe, midgard, valkyrie). Ten of the maps we tune on are never played, and
ten of the maps we are scored on are never tested — including `jotunheim` and
`longhouse`, two of the three worst. Every win rate in this file was measured on
the wrong two-thirds of the board, which is a large part of why mirror A/Bs and
real results have disagreed.

`experiments/ab.py` now takes `--pool ladder` (or `--pool both`). **Use it.** The
legacy pool is kept as `--pool ab` only so old numbers remain reproducible.

## The mirror A/B is blind to whole classes of defect

Every number in the table above comes from playing the bot against a copy of
itself. That measures *strategy* well and **cannot measure robustness at all**,
because any failure both copies share cancels out and reads ~50%.

Measured, not argued:

- **Our bot never kills an enemy builder.** Across 20 mirror games, instrumented
  for it, the count of enemy builder-bot deaths was **0**. The bot shoots cores
  and buildings in its way; builders are simply never targeted. So no mirror A/B
  has ever exercised losing a unit — while real ladder opponents field dozens of
  forward turrets and do kill them.
- **Neither side ever builds an obstacle on purpose**, so no mirror game has ever
  tested what happens when a route is walled.
- **A crash that kills a unit reads as neutral.** `bridge` raises an `IndexError`
  out of `Map.configure` on both seeds, killing a builder outright, and 3,800
  mirror games never surfaced it.

Two lab opponents now exist to apply exactly the pressure the mirror cannot, and
neither is meant to be good — they are instruments:

| Bot | What it does | What it tests |
| --- | --- | --- |
| `experiments/idle` | nothing | economy and pathing without pressure |
| `experiments/hunter` | forward line of sentinels, prefers builder-bot targets | losing units |
| `experiments/waller` | rings its own core in barriers | routing through obstacles |

Use `experiments/stall_check.py <bot> <n> [--opp DIR] <maps...>`, which aggregates
N games per map, because single games are worthless here: the bot calls `random`
unseeded, and the same map and seed gave **59 and 1000 turns** on consecutive
runs. A 2-seed reading suggested `patch_symcommit` cut `string` from 530 to 55
turns; at 12 games per map the same patch was a clear **regression**.

## The builders freeze, and it costs whole games

Diagnosed on `yulerune` against a do-nothing opponent by printing every
builder's position, stage and cached route every 100 rounds:

    BOT r100 n1 at (7,6) stage=0 target=(10,1) pathlen=5
    BOT r200 n1 at (7,6) stage=0 target=(10,1) pathlen=3
    BOT r600 n1 at (7,6) stage=0 target=(10,1) pathlen=9

Three of four builders sit in `build_stage == 0` from round 100 to 600+, each
oscillating between two tiles, each holding a build order whose `go_to` it never
reaches. The map stops being scouted at round 100 and the game runs to the
round-1000 tiebreak. Base rate on that map: **median 1000 turns, 8 of 12 games
never end**. The ladder record on this family of maps is 0-13 (longhouse) and
1-6 (yulerune) — and `longhouse` is not even in the 15-map A/B pool.

The mechanism is the known path-step bug compounding: `_bot_pathfind` pops a step
off the cached route whether or not the move happened, so one blocked step
desyncs the whole route from where the builder actually is, and it walks a plan
for a position it never reached. Nothing detects this and nothing replans.

There are two ways to fix it — make the builder *reach* the order, or make it
*drop* the order. CLAUDE.md's own evidence says the second is the one that wins,
since the first converts a frozen builder into a miner and every measured variant
that spent builder turns on mining lost. `patch_giveup` drops an order that has
gone nowhere for 20 rounds; on yulerune it turns 1000-turn stalls into
core kills at turns 121 / 129 / 155.

Note the detector has to tolerate *oscillation*: the first version required an
identical position each round and caught almost nothing, because a desynced
builder does not stand still, it rattles between two tiles. Counting distinct
tiles over a window catches it.

**There are two different freezes, and they need different fixes.** Tracing
`longhouse` (ladder record 1-18) shows the other one:

    BOT r100 n1 at (4,7)  stage=-1 target=(19,8) pathlen=32 movecd=1
    BOT r200 n1 at (7,14) stage=-1 target=(19,9) pathlen=29 movecd=1
    BOT r300 n1 at (6,13) stage=-1 target=(19,9) pathlen=19 movecd=1

Symmetry is solved here and the enemy core is known at (25,9); the builders are
not wedged on two tiles, they *wander* the western third of the map for 900
rounds and the scouted count sticks at 250/504. Builders move on a cooldown, so
on roughly every other round `can_move` is False — and `_bot_pathfind` pops the
step anyway. On a 30-step march that discards about half the route, and what is
left is a plan for tiles the builder never stood on. So:

- **yulerune type** — builder wedged in two tiles holding an order it cannot
  reach. Fixed by dropping the order (`patch_giveup`) or the siege tile
  (`patch_siegepick`).
- **longhouse type** — route decays into noise because steps are spent on
  cooldown rounds. Only fixed by not spending a step that was not taken
  (`patch_pathstep`, included in `patch_blocked`).

A third variant of the same family: `_bot_without_orders` picks the *nearest*
tile from `tiles_to_attack_core_ct_mode()`, which is built from geometry alone
and happily returns a tile the builder has never seen and that is solid rock.
BFS finds no route to a WALL, the greedy fallback walks into it, and nothing
notices. That is `patch_siegepick`.

### What that is worth: 12 games per map against the do-nothing opponent

Median turns to kill, and how many of 12 games never ended at all:

| | longhouse | yulerune | string | yggdrasil | stalls |
| --- | --- | --- | --- | --- | --- |
| live bot | 960 (6/12) | 1000 (9/12) | 59 (5/12) | 108 (0/12) | **20/48** |
| + give up on a stuck order | 754 (3/12) | 122 | 59 | 93 | 3/48 |
| **+ blocked-tile pathfinding** | **104** | **78** | **51** | **67** | **0/48** |
| + guards + give-up | 544 | 138 | 58 | 112 | 0/48 |
| all of the above | 95 | 81 | 51 | 70 | 0/48 |

`patch_blocked` alone removes every stall on the board and takes longhouse — our
worst ladder map at 1-18 — from a 960-turn median to 104. The path-step half of
it is doing most of that work; `patch_giveup` fixes yulerune but barely touches
longhouse, exactly as the two-freeze diagnosis predicts.

### Against the adversarial opponents

Against `hunter` (6 games/map, 6 maps), which shoots builder bots:

| | games ending in a stall | median turns, worst map |
| --- | --- | --- |
| live bot | 4/36 | 99 (archipelago) |
| + replace dead builders | 1/36 | 92 |
| + **defend** with the damage-response builders | **8/36** | **609** |
| all robustness fixes | **0/36** | 82 |

Against `waller` (barrier ring), every variant still wins every game, but
`patch_blocked` gets there faster on all six maps (medians 76→61, 74→68, 76→65,
48→45, 54→49, 61→57).

## The economy cap: the first change that clearly wins

`patch_ecocap 4` stops the core planning new harvester orders once four have ever
been issued. It is six lines. Measured against the incumbent over **450 games in
three independent seed ranges: 60.7% / 65.3% / 69.3%, pooled 65.1%.** With the
robustness bundle on top: 68.0% / 67.3% / 65.3%, pooled **66.9%**.

Nothing in ~4,000 previous games came close, and unlike the readings this file
warns about (54.4% at 90 games, 58.0% then 50.0%), this one gets *stronger* on
each fresh seed range rather than decaying toward 50%.

**Why it works, and why it does not contradict the rest of this file.** The core
caps *concurrent* build orders at three but keeps minting new ones for as long as
it knows of unmined ore, so builder-turns drain into mining for the whole match.
Every earlier attempt to cap mining was made inside `bots/econ`, a rewrite whose
builders mine as a *behaviour*; capping a behaviour there just meant they found
different mining to do. Here the cap is on the *number of orders the core ever
issues*, which is the quantity CLAUDE.md already identified as the real currency:
builder-turns, not titanium. Past four harvesters, every builder is permanently on
the siege. This is the same conclusion as "any use of a builder's action other
than walking at the enemy core loses" — it is that finding applied to the one
place the incumbent had no limit at all.

Note the round-based form of the same idea is much weaker: no new orders after
round 40 scores 52.0%. It is the *count* that matters, not the clock.

### The cap has a real optimum, and the curve proves the effect

Sweeping the cap, 150 games each on seeds 1-5, with the promising values
replicated on seeds 11-15:

| Cap (total harvester orders) | seeds 1-5 | seeds 11-15 | pooled |
| --- | --- | --- | --- |
| 1 | 27.3% | — | 27.3% |
| 2 | 51.3% | 48.7% | 50.0% |
| 3 | 57.3% | 50.0% | 53.7% |
| 4 | 60.7% | 65.3% (+69.3% on 21-25) | **65.1%** (450 games) |
| **5** | **68.0%** | **70.7%** (+70.0% on 21-25) | **69.6%** (450 games) |
| 6 | 60.0% | — | 60.0% |
| 8 | 52.0% | — | 52.0% |

A clean inverted U peaking at 5. That shape is itself the strongest evidence the
effect is real: noise does not produce a monotone rise to a peak and a monotone
fall away from it, and the two ends are interpretable — at a cap of 1 the bot has
no economy at all and loses badly (27.3%), at 8 the cap barely binds and the
result returns to baseline (52.0%).

**Cap 5 is the recommended value.** It now has the same 450 games across three
independent seed ranges as cap 4, and it is the most stable reading in this file:
68.0 / 70.7 / 70.0, a spread of under three points where every other promising
result in this project decayed toward 50% on the second range.

### The bundle, audited on all 46 maps with the time limit ON

`vfinal` = `patch_mapguard` + `patch_oob` + `patch_blocked` + `patch_siegepick`
+ `patch_respawn`:

| | live bot | vfinal |
| --- | --- | --- |
| Tracebacks in 92 games | 2 (`bridge`) | **0** |
| Time-limit messages | 0 | 0 |
| Maps flagged | 7 | **4** |
| longhouse | 785 turns | **96** |
| string | 530 | **48** |
| yulerune | 1000 | **84** |
| yggdrasil | 108 | **67** |
| bridge | 83 + crash | **58** |

The four maps still flagged — drakkarfjord, glacierkeep, jotunheim, showdown —
are all "mines NOTHING", i.e. the conveyor-encoding bug, not a stall. That is a
different fix (`patch_conveyor`) and the two are complementary: measured alone,
the conveyor fix takes glacierkeep from 109 to 80 turns but leaves longhouse and
yulerune stalling 7/12 and 8/12, exactly as before.

### `scouter2-patched` re-audited the same way, 2026-08-23

Same instrument, all 46 maps, 2 seeds, **TLE ON**:

- **92/92 games won.** No map fails to end.
- **No tracebacks and no time-limit messages** — so the builder's BFS tail-routing
  (`_extend_conveyor_path`, capped at 1500 nodes) fits the 10 ms budget.
- **1 map flagged, down from 4**: only `showdown` still mines nothing, and it is
  won in 85 turns anyway. The three that mattered are repaired — drakkarfjord
  **600 Ti**, glacierkeep **330 Ti**, jotunheim **220 Ti**, all previously zero.
- longhouse 102 turns / 820 Ti, yulerune 74 / 580, string 42 / 310 — the stall
  family stays fixed.

This is the cleanest audit any bot in this project has produced.

CPU with the fixes in: median 0.3–1.4 ms, max 6.7 ms per builder turn against the
10 ms limit — the live bot's max is 6.9 ms, so this costs nothing measurable.

**Defending is the one idea here that measurably loses**, and it loses twice
over: 35.3% in the mirror (where the opponent *is* a rusher, so this is a fair
test of anti-rush play) and *more* stalls against the hunter than doing nothing,
because a builder holding station near our core is a builder not ending the game.
This is the same wall CLAUDE.md's turtle and garrison experiments hit; the narrow
version — defend only with builders that already exist because the core is being
hit, leaving the 4-builder siege untouched — does not escape it either.

## Three robustness defects in the live bot

All three are invisible to the mirror and all three match what a teammate
reported from real games.

- **Dead builders are never replaced.** `self.bots_made` only ever increments and
  the spawn gate is `if self.bots_made < 4`, so once four builders have *existed*
  the core will not make another however many are killed. An opponent that kills
  builders removes them permanently — siege, economy and scouting — while the bank
  climbs. Death detection is free: `read_stored_scout` already zeroes a builder's
  scout slot after reading it, so a live builder is exactly one that rewrites its
  slot. The one gap is that a builder which did not move writes a literal 0;
  `patch_respawn` writes a nonzero heartbeat that still decodes to `Position(0,0)`
  with no tiles, so it does **not** quietly fix the load-bearing `Position(0, 0)`
  bug.
- **The builders spawned because we are being attacked walk away.** The core does
  react to a rush (`if ct.get_hp() < ct.get_max_hp() and self.bots_made < 6`) but
  builders 5 and 6 get no store slots, fall through to `_bot_without_orders`, and
  march at the *enemy* core. The bot's entire answer to being rushed is to send
  two more attackers away from the fight. `patch_defend` gives only those builders
  a defensive job and leaves the 4-builder siege force untouched.
- **Three unguarded `get_tile_building_id()` calls.** All of the form
  `ct.get_tile_building_id(bot_position.add(self.build_direction))`, which reaches
  up to two tiles from `go_to` and lands off the grid for orders planned near an
  edge — a permanent unit death. Everything else in the bot iterates
  `get_nearby_tiles()`, which is always in bounds, so these three are the whole
  exposure. `patch_oob`.

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

## The economy rewrite (`bots/econ`) — 10.7%, and why

The architectural rewrite the plateau seemed to call for: the core plans no
economy at all, and each builder every turn either builds a harvester on
adjacent ore that touches our conveyor network, lays the one belt that extends
the network toward the cheapest unclaimed ore, or walks to where it could do
one of those. This removes the 3-order cap, the per-harvester private chain and
the store-slot pressure in one go. Builders share the network over the freed
build-order slots (each publishes the belt it laid that turn, 11 bits, and a
builder lays at most one belt per turn, so the bandwidth is exactly sufficient),
and the core broadcasts one known ore tile per turn in the spare bits of slot 0.

**The engine works.** Against the idle bot across the pool, harvesters by turn 80
went 4.6 → 7.6, titanium collected 962 → 1448/game, and `glacierkeep` and
`drakkarfjord` — which mine literally zero under the incumbent — mine normally.
On ore-dense `archipelago` it reaches 32 harvesters at 2.7 belts each.

**It loses anyway, and the sweep is monotone**: every unit of builder time moved
off the siege costs win rate (10.7% all-mining → 36.7% mining only to turn 50).
No split, no reach cap and no cutoff round beats the incumbent.

**The measurement that explains it.** Head-to-head against the incumbent on
midgard, at the turn-72 point where the game actually ends:

| | rewrite | incumbent |
| --- | --- | --- |
| Harvesters | 5 | 5 |
| Conveyors | 15 | 15 |
| Sentinels | **0** | **7** |
| Titanium unspent at death | 634 | 28 |

The economies are *identical*. The rewrite's advantage is real but only exists
in games long enough for it to compound, and a real opponent ends the game
before that. This is the "game length is the hidden variable" finding confirmed
from the other side: **fixing the economy does not lengthen the game, so the
economy never gets paid.** Do not re-derive this by building a better miner.

**The balance point does not exist, and it was looked for properly.** Six
independent axes, ~20 configurations: what fraction of builders mine, a phase
switch from mining to sieging at turn N, a cap on belt-run length, a cap on how
far a builder will *detour* for a job, extra builders on top of an untouched
4-builder siege force, and spending the proceeds on ammo instead of buildings.
The best of all of them is 36.7% (mine with everyone until turn 50, then commit
everything to the siege). Nothing reaches 50%.

The one that looked most promising on paper — keep the siege at its measured
optimum of 4 and add a 5th builder that only mines — scores 33.3%, barely above
the 30.7% CLAUDE.md already records for a 5th builder with no economy at all. A
builder costs +20% cost scale forever and its belts another +1% each, and the
siege is money-limited, so the extra harvesters mostly pay for the scale
inflation they themselves caused. A 6th builder is catastrophic (15.0%).

**Why builder-turns, not titanium, are the currency.** The incumbent's economy is
nearly free: three short build orders executed *en route* by builders that are
walking at the enemy anyway. Ours is not, because a builder that plans its own
mining will always find one more job worth doing. Capping the detour at 5-8 tiles
was the attempt to reproduce "mine only what is on the way", and it fails on
mechanism: fresh ore keeps coming into range as the builder marches, so it never
stops mining and still ends games with 0-2 sentinels. Any scheme where mining is
a *behaviour* rather than a fixed short *quota* runs to the same place.

**The incumbent's economy is not the weak part — it is well-sized.** Capping
belt runs at 0 (harvesters only on ore already touching the core) mines nothing
at all on most maps and scores 16.7%, while the incumbent collects 420-870 Ti
per game with builders that mostly siege. Its 3-order cap is not a bug to route
around; it is roughly the right amount of mining, bought at roughly the right
price in builder turns.

## The turtle experiment (drastic playstyle change) — 42.2%

Tried abandoning the rush entirely: builders keep mining, order-less builders come
home, fortify with barriers (10 HP/Ti vs healing's 4, +1% scale vs a turret's +20%)
and play for the round-1000 tiebreak, which we had never once contested.

It works mechanically — games reach round 1000 instead of dying at turn 85, and
mining goes from ~400 to 9,880 — but it does not win:

| Variant | Win rate |
| --- | --- |
| turtle alone | 36.7% |
| **turtle + all three economy fixes** | **42.2%** |
| turtle + endgame banking | worse (ragnarok 1-5 → 0-6) |
| turtle + proactive sentinel garrison | no better; still dies turn 53–98 |

The +5.5 points from adding the economy fixes is the **only direct evidence all
session that those fixes are worth anything** — they help once games last long
enough for economy to compound, exactly as the game-length theory predicts.

Results are strongly bimodal: drakkarfjord 6-0, glacierkeep 5-1, valkyrie 5-1
(all maps where the *opponent* mines zero because of the conveyor bug), against
auroraveil 0-6, archipelago 0-6, frostgate 1-5.

**Why it fails:** it dies. On auroraveil all six games ended core_destroyed between
turn 65 and 126. Neither reactive barriers nor a proactive sentinel garrison stopped
our own rusher. Pantheon survives long games because 38 gunners hold the line; a
turtle with 2-4 sentinels cannot, and it cannot afford more without an economy that
needs the time the defence was supposed to buy.

Also learned: on maps where both sides mine the same total (ragnarok, 4,980 each) the
match falls through to *titanium stored*, and the turtle structurally loses that —
it spends its bank on barriers. Endgame banking did not recover it; the margins are
~2% and the turtle simply spends more.

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
  Fixing that by stepping the request down (`want`, `want//2`, `want//4`, 10 until
  one is affordable) measured 41.7% at the current target of 20 and 45.3% over 150
  games at a target of 40 — so the all-or-nothing behaviour is load-bearing too,
  presumably because titanium not spent on ammo is titanium available for the next
  sentinel. Note the target-40 variant read **55.0% at 60 games** before settling
  at 45.3% over 150: the single clearest reminder this session that a 60-game read
  is worth nothing. A target of 80 lands at exactly 50.0% over 60 games, i.e. no
  detectable effect either way.
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

### v8 `robust-ecocap5` (2026-08-22) — the first candidate that holds up

Unrated scrimmages with v8 active. **The informative opponents are the ones in our own
rating band**, not the top five: against a bot rated 600-800 points above us we lose
whatever we change, which is most of why the v4/v5/v6 scrimmage tables above look flat.
Use `fcode ladder --around --json` to find them.

| Band | Record |
| --- | --- |
| Our band (#49-#58, ratings 1364-1452) | **29-13 = 69%** |
| Top tier (Pantheon #5, Pivot #4, Bean counters #2, Lorem Ipsum #10) | 4-16 |

Per-opponent in our band: potatis 5-0, Kings College 5-0, Hugging Farce 5-0, Askar City
4-1, 1337 3-2, Viktor5776 3-2, Team imeto 1-1, Orizon 2-3, Landers 1-4.

**No game stalled.** All 42 were decided by core destruction inside 208 turns, and we won
on `longhouse` — the map we are 1-18 on. Previous submissions lost that family on the
clock. For comparison v4 went 6-19 against the top-tier set and v6 went 1-24; v8 goes
2-3 against Pantheon, where v4 went 1-4 and v6 went 0-5.

**First rated evidence.** In the first 5 rated ladder matches after activating v8 the
rating went **1409 -> 1466 (+57)** and the rank **#54 -> #46**, last-10 8W-2L. Five matches
is not a result — but it is the right instrument, it is free, and it is the one number to
keep watching. Re-run `experiments/ladder_stats.py` once a few hundred games have
accumulated and compare against the v4 baseline of 113-187 (37.7%).

### Against the teammate's `bots/scouter3`

A second new bot landed the same day (economy-focused rewrite, `bots/scouter3`). Ours is
`bots/scouter2-robust` to avoid the collision. Head to head:

| | Games | Result |
| --- | --- | --- |
| `scouter2-robust` vs `scouter3` | 300 | **71.3% / 72.7%** |
| `scouter3` vs the v4 incumbent | 150 | 48.7% |
| `scouter3` vs idle, longhouse / yulerune | 12 ea | **12/12 stall on both** |

It mines more than we do (870 vs 770 Ti in a sample game, 45 structures vs 21) and still
loses, because it carries the same freeze — worse, since it never finishes either stall
map. The two efforts are complementary, not competing: its economy plus these robustness
patches is the obvious next bot.

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
- `_bot_pathfind` pops a step off its cached BFS route whether or not the move
  happened, and builders move on a cooldown, so every cooldown turn silently
  discards a step and the rest of the route points at tiles the builder never
  reached. Found while rewriting the economy (one builder sat on one tile from
  turn 20 to turn 83). Fixing alone → 40.0%; the resulting wander appears to be
  load-bearing too.

## Proven bugs worth fixing (written, not merged)

- **All-NORTH conveyor routes are silently dropped.** `CARDINALS.index(NORTH) == 0`, so a
  pure-north route encodes as all-zero bits and `if (number >> 15) > 0` reads it as "no
  path". The builder lays no belts, builds the harvester anyway, and marks the order
  done. Fix: bit 31 is free — use it as an explicit "path present" flag.
- **8-tile conveyor cap** rejected 609/609 plans on `drakkarfjord` (zero harvesters all
  game). It is an encoding limit, not a game rule.

**Which of the two actually causes the zero-mining maps: the cap, not the encoding.**
Measured 2026-08-23 by building v8 + the `PATH_PRESENT_BIT` flag *alone* and running it
against the idle bot: `glacierkeep` still mines **0 Ti in 109 turns** and `jotunheim`
still mines **0 Ti in 77 turns** — identical to v8. Both maps only start mining when the
chain cap is raised (`MAX_CONVEYOR_CHAIN = 20`) and the builder finishes the tail with its
own BFS. So the earlier attribution of `glacierkeep` to the all-NORTH bug in this file was
wrong; it is the same 8-tile cap that kills `drakkarfjord`. Apply `patch_conveyor` as a
unit — its two halves are not independently useful.

## Measurement discipline (learned the hard way)

- **150+ games minimum.** One variant read 54.4% at 90 games and 50.7% at 150; another
  read 58.0% then 50.0% on fresh seeds. Replicate on a **different seed range** before
  believing anything.
- Play every (map, seed) **twice with sides swapped**; side bias is large.
- Use `--tle 0` when comparing strategies, or results depend on machine load and
  penalise whichever variant computes more. **Then check the CPU budget separately
  with `get_cpu_time_elapsed()` — `--tle 0` hides a broken bot completely.** The
  economy rewrite first measured 6.9ms median / 13.2ms max per builder against a
  10ms limit (the live bot is 0.2ms / 4.3ms) and would have passed a full
  150-game A/B while having turns interrupted on the ladder. Building `Position`
  NamedTuples inside a per-turn BFS was almost all of it; raw `(x, y)` tuples plus
  a replan timer brought it to 0.4ms / 8.8ms.
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
- Module-level globals are **not shared between units** — a counter in a module
  dict reads back as zero from the core. Probes must print per event and be
  aggregated outside (see `experiments/patch_probe.py`).

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

### Engine facts measured here, not in the docs

- **Conveyors are passable; the core is not.** Builders walk over their own belts
  (that is how the belt-laying loop works), but the core's 2x2 footprint blocks
  movement. Being part of the resource network says nothing about passability —
  conflating the two made pathfinding route straight through our own core and
  froze two of four builders from turn 17 to the end of the game.
- **The core is not at the map origin.** On midgard it is at (3, 3). Anything that
  assumes (0, 0) is wrong, and `Position(0, 0)` is truthy, so the mistake is quiet.
- `Map.configure(width, height, core_pos)` records `core_pos` as the core. Builders
  call it with **their own** position, so `local_map.own_core` on a builder is its
  spawn tile, not the core. Find the core in vision instead.
- `can_build_*()` returns False while the action cooldown is running, which is not
  distinguishable from "too expensive" or "tile occupied" without checking each
  yourself. Treating a cooldown refusal as "impossible" makes a builder walk away
  from a site it was one turn from building.
- **Out of bounds, every `can_*()` returns False but `get_tile_env()` and
  `get_tile_building_id()` RAISE `GameError`** — and an uncaught exception destroys
  that unit permanently. So `can_fire(t) and get_tile_building_id(t)` is safe and
  `get_tile_building_id(t) and can_fire(t)` is a unit-killer. Probed directly
  (`scratchpad/oob`): `can_heal`, `can_build_*`, `can_destroy`, `can_fire` and
  `is_tile_passable` all return False; the two getters raise.
- **Each unit gets its own `Player` instance and it persists for the whole match.**
  Verified by printing `id(self)`: the core's instance is stable across rounds,
  which is why `self.bots_made` works — and why a counter that is never decremented
  stays wrong for the rest of the game.
