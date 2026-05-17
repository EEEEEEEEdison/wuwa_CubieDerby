"""Single source of truth for simulation constants.

These values define the rules of the simulator: lap lengths, special-cell
positions, per-skill probabilities, and a defensive guard for the main
loop. Changing any of them here changes simulator behaviour everywhere
they're used.

Anything that the README documents as a balance number lives here and
nowhere else. Tests under tests/test_monte_carlo_pinned.py will fail
loudly if any of these values is altered without intent.
"""
from __future__ import annotations


# ---- Track lengths --------------------------------------------------------

DEFAULT_LAP_LENGTH = 24
SEASON2_LAP_LENGTH = 32


# ---- Season 2 special-cell sets ------------------------------------------
#
# `frozenset` rather than `set` so the values are hashable and safe to
# share across multiprocessing workers.

SEASON2_GROUP_FORWARD_CELLS = frozenset({3, 11, 16, 23})
SEASON2_GROUP_BACKWARD_CELLS = frozenset({10, 28})
SEASON2_GROUP_SHUFFLE_CELLS = frozenset({6, 20})

SEASON2_KNOCKOUT_FORWARD_CELLS = frozenset({4, 10, 20})
SEASON2_KNOCKOUT_BACKWARD_CELLS = frozenset({16, 26, 30})
SEASON2_KNOCKOUT_SHUFFLE_CELLS = frozenset({6, 14, 23})


# ---- Skill triggers / probabilities --------------------------------------
#
# README documents these as plain percentages; they're encoded as floats
# in [0, 1] for `rng.random() <= chance` checks.

AEMEATH_TRIGGER_CELL = 17

CAMELLYA_SOLO_ACTION_CHANCE = 0.5
ZANI_EXTRA_STEPS_CHANCE = 0.4
CARTETHYIA_EXTRA_STEPS_CHANCE = 0.6
PHOEBE_EXTRA_STEP_CHANCE = 0.5
POTATO_REPEAT_DICE_CHANCE = 0.28
JINHSI_REORDER_CHANCE = 0.4
CHANGLI_EXTRA_STEP_CHANCE = 0.65


# ---- RNG seed mixing ------------------------------------------------------

RNG_SEED_MASK = (1 << 64) - 1


# ---- Defensive bounds -----------------------------------------------------
#
# Real races terminate in <= 20 rounds. This guard exists only to convert
# pathological configs (all skills disabled + impossible start grid) into
# a clear RuntimeError rather than an infinite loop. Set generously.

MAX_RACE_ROUNDS = 10_000


__all__ = [
    "AEMEATH_TRIGGER_CELL",
    "CAMELLYA_SOLO_ACTION_CHANCE",
    "CARTETHYIA_EXTRA_STEPS_CHANCE",
    "CHANGLI_EXTRA_STEP_CHANCE",
    "DEFAULT_LAP_LENGTH",
    "JINHSI_REORDER_CHANCE",
    "MAX_RACE_ROUNDS",
    "PHOEBE_EXTRA_STEP_CHANCE",
    "POTATO_REPEAT_DICE_CHANCE",
    "RNG_SEED_MASK",
    "SEASON2_GROUP_BACKWARD_CELLS",
    "SEASON2_GROUP_FORWARD_CELLS",
    "SEASON2_GROUP_SHUFFLE_CELLS",
    "SEASON2_KNOCKOUT_BACKWARD_CELLS",
    "SEASON2_KNOCKOUT_FORWARD_CELLS",
    "SEASON2_KNOCKOUT_SHUFFLE_CELLS",
    "SEASON2_LAP_LENGTH",
    "ZANI_EXTRA_STEPS_CHANCE",
]
