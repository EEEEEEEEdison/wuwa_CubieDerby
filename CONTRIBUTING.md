# Contributing

## Setup

```powershell
# Python 3.10+ required (PEP 604 / PEP 585 used at runtime in some modules).
python --version
```

The project has zero runtime dependencies; `pip install -e .` is enough
to expose the `cubie-derby` console script.

## Run the tests

```powershell
python -m unittest discover -s tests
```

195 tests, ~3.5s. Selective runs:

```powershell
python -m unittest tests.test_skills
python -m unittest tests.test_tournament -v
python -m unittest tests.test_monte_carlo_pinned
```

## Commit policy

- Each commit should leave the test suite green: `python -m unittest discover -s tests`.
- Behavioural changes (bug fixes, new mechanics, balance tweaks) MUST update
  the affected tests in the same commit. If the pinned regression tests
  in `tests/test_monte_carlo_pinned.py` change, the commit message MUST
  explain *why* the statistical output legitimately drifted — that's the
  single biggest invisible-failure mode in this project.
- Internal refactors must NOT change the pinned values.

## Performance changes

The simulator hot loop runs ~2,500 races/second/core. We treat this as
load-bearing.

When changing anything inside `simulate_race` or its callees:

1. Bench against `main` with two scenarios — single-stage Monte Carlo (5000
   races, 5 trials, median) and champion prediction (300 tournaments, 3
   trials, median).
2. A regression > 1% needs a justification. Outright rejection is the
   default unless there's a concrete reason (e.g. a real correctness fix
   that requires the slowdown).
3. The pinned tests must still pass without modification.

## Adding a runner / skill

1. Add the id constant + name + alias in `cubie_derby_core/runners.py`.
2. Add the skill helper in `cubie_derby_core/skills.py` (stateless dice /
   probability checks) or `cubie_derby_core/skill_hooks.py` (post-action
   hooks that touch grid / progress).
3. Wire it into `simulate_race` in `cubie_derby.py`. Look for the per-skill
   `if player == X_ID and skill_enabled(config, X_ID):` block as the
   precedent.
4. Add a test in `tests/test_skills.py` using one of the fake RNGs from
   `tests/_shared.py` (`FixedDiceRandom`, `QueuedRandom`, etc.).
5. Document the skill in `README.md` and `README.en.md`.

## Adding a stage / match type

1. Add the rule in `cubie_derby_core/match_types.py:SEASON2_MATCH_TYPES`
   using `AdvancementMode` and `MapVariant` enum members.
2. Add the alias in `MATCH_TYPE_ALIASES` if there's a Chinese name.
3. If it changes the tournament flow, update
   `cubie_derby_core/tournament.py:SEASON2_TOURNAMENT_PHASES` and
   `SEASON2_TOURNAMENT_FLOW`.
4. Add a test in `tests/test_tournament.py`.

## File-naming conventions

- `core_run_*` (in `cli_dispatch.py`) — top-level command handlers.
- `core_<name>` (re-exported in `cubie_derby.py`) — pure core function;
  the entry script wraps it after binding the right `*Helpers` singleton.
- `_<name>` (inside `cubie_derby.py`) — module-private helper. The
  `_EFFECT_HOOKS` / `_NPC_HELPERS` / `_RUNNER_ACTION_HELPERS` /
  `_SKILL_HOOK_HELPERS` lazy singletons live here.
- `*Helpers` frozen dataclass — a bag of injected callbacks. Wide use in
  `core/*.py`; see `ARCHITECTURE.md` for why.

## Don't do

- Don't change the pinned regression values without a justified reason.
- Don't add a runtime dependency unless absolutely necessary.
- Don't import `cubie_derby` (the entry script) from inside
  `cubie_derby_core/`. The dependency direction is one-way.
- Don't add `from cubie_derby_core.X import *` — be explicit.
- Don't remove `_MAX_RACE_ROUNDS` or its check. It's free insurance.
- Don't replace `frozenset` cell sets with `set` — they're shared between
  workers via multiprocessing and `frozenset` matters for hashability.
