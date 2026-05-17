# Architecture

This document is for **contributors**. The `README.md` files cover how to use
the simulator from the command line; this file covers what's actually inside
and why it's structured the way it is.

## High-level shape

```
cubie_derby.py                  ← entry script + public-API facade
├── main()                      ← CLI dispatch (5 paths)
└── re-exports ~50 names        ← imported by tests/_shared.py

cubie_derby_core/               ← implementation modules (24 files)
├── runners.py                  pure data: id constants, name / alias tables, season pools
├── constants.py                shared simulation constants (lap lengths, special-cell sets, skill probabilities)
├── tracing.py                  TraceContext = bool | TraceSink protocol
├── movement.py                 ring-track math (display_position, move_progress, ...)
├── setup_validation.py         track-length / start-grid / qualify-cutoff guards
├── skills.py                   stateless per-runner skill helpers + dice rollers
├── skill_hooks.py              post-action skill triggers (Aemeath, Luno, Jinhsi, Hiyuki contact)
├── runner_actions.py           the three movement variants (single, with-left-side, Cantarella)
├── npc.py                      NPC backward movement, carry, end-of-round settlement
├── effects.py                  cell-effect engine (forward / backward / shuffle)
├── ordering.py                 initial_player_order, current_rank, next_round_action_order
├── match_types.py              MatchTypeRule + AdvancementMode / MapVariant enums
├── stage_config.py             RaceConfig builders (parse_start_layout, build_config_from_args)
├── accumulators.py             MonteCarloAccumulator, SeasonRosterScanAccumulator
├── parallel_jobs.py            generic Monte Carlo / champion-prediction orchestrator
├── analysis_jobs.py            run_skill_ablation, run_season_roster_scan
├── tournament.py               TournamentPlan / EntryRequest / simulate_tournament / advanced analytics
├── tournament_context.py       JSON load/save for TournamentEntryRequest
├── champion_interactive.py     interactive wizard (zh/en, terminal rendering)
├── interactive_i18n.py         translation lookup
├── cli_parser.py / cli_dispatch.py    argparse + the five run_*_command functions
├── helper_factories.py         builders for the four *Helpers frozen dataclasses
├── reporting.py                format_summary / *_to_dict
└── trace_logs.py               default_trace_log_path
```

## Data flow

```
sys.argv  →  make_parser  →  argparse.Namespace  →  main()
                                                      ↓
                                          (5-way switch on flags)
              ┌──────────────────┬──────────────────┬──────────────────┬──────────────────┐
              ↓                  ↓                  ↓                  ↓                  ↓
   core_run_interactive  core_run_champion_  core_run_season_  core_run_trace_   core_run_simulation_
   _command              prediction_command  roster_scan_      command           command
                                              command
              │                  │                  │                  │                  │
              └──────────┬───────┴──────────────────┴──────────────────┴──────────────────┘
                         ↓
                    simulate_race / simulate_tournament / run_monte_carlo
                         ↓
                    text reporting (format_*) or JSON (*_to_dict)
```

## The hot loop

`simulate_race` (in `cubie_derby.py`) is the inner-most function. Everything
else exists to feed it inputs and aggregate its outputs. It runs once per
simulated race, ~2,500 times/second/core on a typical machine.

Key state per race:
- `grid: dict[int, list[int]]` — cell → ordered list of runner ids
- `progress: dict[int, int]` — runner id → integer position
- `RaceSkillState` — per-skill flags (Hiyuki bonus, Aemeath pending, Luno used, ...)
- `RaceMovementState` — per-runner totals for `lazy_win_rate`

Cached views (invalidated on every grid mutation):
- `cached_cell_index` — runner id → in-cell offset
- `cached_rankings` — `bool` → ranking with/without NPC

## The dependency-injection pattern

Many `core/*.py` functions take a frozen `*Helpers` dataclass full of
callbacks. The actual callbacks are wired up by lazy module-level singletons
in `cubie_derby.py` (`_EFFECT_HOOKS`, `_NPC_HELPERS`, `_RUNNER_ACTION_HELPERS`,
`_SKILL_HOOK_HELPERS`).

The original reason was to break import cycles. The cycles no longer exist,
so this DI is heavier than it needs to be — but unwinding it is on the
"future work" list because the pattern is widespread.

## Determinism & seeding

Monte Carlo correctness depends on per-race RNG state being a function of
`(master_seed, race_index)` only — not of worker count. `derive_race_seed`
implements a SplitMix64-style mix to achieve this. Workers are launched
with `multiprocessing.Pool.imap_unordered`, but the per-race seed is
derived inside the worker, so adding workers cannot change the output.
This is locked by `test_run_monte_carlo_seed_is_worker_independent` and
the pinned regression tests in `tests/test_monte_carlo_pinned.py`.

## Test layout

```
tests/
├── _shared.py                     fake-RNG helpers + argparse_namespace fixture
├── test_skills.py                 53 tests: every per-runner skill
├── test_interactive_wizard.py     37 tests: prompts, i18n, end-to-end main()
├── test_tournament.py             33 tests: plans, entry points, prediction
├── test_npc.py                    19 tests: NPC + Season 2 special cells
├── test_movement_and_grid.py      16 tests: ring math, ranking, finish line
├── test_reporting_and_progress.py 13 tests: format_summary, JSON, ProgressBar
├── test_cli.py                    11 tests: parser, --start, --runners
├── test_match_types_and_config.py  9 tests: build_config_from_args, --match-type
└── test_monte_carlo_pinned.py      4 tests: golden-sample regression
```

Each per-domain file imports `from tests._shared import *` and runs
standalone. Total: 195 tests, ~3.5s.

## Hot-path ground rules

When changing anything inside `simulate_race` or its callees:

1. Never weaken the closure-based `cached_cell_index` / `cached_rankings`
   pattern. The two-keyed cache is intentional and load-bearing.
2. Run the pinned regression tests (`tests/test_monte_carlo_pinned.py`).
   They lock per-runner statistics for fixed seeds; any drift means a
   real behavioural change, not just a refactor.
3. Run a benchmark (single-stage 5000 races + champion prediction 300
   tournaments) on `main` and your branch; compare medians of 5 / 3 trials.
   Reject changes that regress > 1% without strong cause.
4. The `_MAX_RACE_ROUNDS = 10_000` guard catches infinite-loop bugs in
   pathological configs. Don't remove it.

## What lives where

| Question                                               | File                                              |
|--------------------------------------------------------|---------------------------------------------------|
| What's runner 17's name and skill?                     | `runners.py`, `skills.py`, `skill_hooks.py`       |
| How does cell 6 (shuffle) work?                        | `effects.py:apply_shuffle_cell_effect`            |
| What are the Season 2 forward / shuffle / backward cells? | `constants.py`                                 |
| How is the round action order chosen?                  | `ordering.py:next_round_action_order`             |
| When does Aemeath teleport?                            | `skill_hooks.py:maybe_trigger_aemeath_after_active_move` |
| How do qualifications work for "elimination"?          | `match_types.py` (AdvancementMode.TOP_N)          |
| How does the wizard prompt for a stage?                | `champion_interactive.py`                         |
| How is per-race seed stable across worker counts?      | `cubie_derby.py:derive_race_seed`                 |
| What does `--season-roster-scan` enumerate?            | `analysis_jobs.py:core_run_season_roster_scan`    |
| Which columns does the JSON output have?               | `reporting.py:summary_to_dict`                    |
