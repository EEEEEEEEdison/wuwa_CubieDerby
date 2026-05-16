from __future__ import annotations

from typing import Any, Callable

from cubie_derby_core.effects import EffectHooks
from cubie_derby_core.npc import NPCHelpers
from cubie_derby_core.runner_actions import RunnerActionHelpers
from cubie_derby_core.skill_hooks import SkillHookHelpers


def build_effect_hooks(
    *,
    record_movement: Callable[..., Any],
    record_hiyuki_npc_path_contact: Callable[..., Any],
    maybe_arm_aemeath_pending: Callable[..., Any],
    format_position: Callable[[int], str],
    format_cell: Callable[[Any], str],
    format_runner: Callable[[int], str],
    log_block: Callable[..., Any],
    log_timing: Callable[..., Any],
) -> EffectHooks:
    return EffectHooks(
        record_movement=record_movement,
        record_hiyuki_npc_path_contact=record_hiyuki_npc_path_contact,
        maybe_arm_aemeath_pending=maybe_arm_aemeath_pending,
        format_position=format_position,
        format_cell=format_cell,
        format_runner=format_runner,
        log_block=log_block,
        log_timing=log_timing,
    )


def build_npc_helpers(
    *,
    apply_cell_effects: Callable[..., Any],
    current_rank: Callable[..., Any],
    format_cell: Callable[[Any], str],
    format_position: Callable[[int], str],
    format_runner: Callable[[int], str],
    log_block: Callable[..., Any],
    record_hiyuki_npc_path_contact: Callable[..., Any],
) -> NPCHelpers:
    return NPCHelpers(
        apply_cell_effects=apply_cell_effects,
        current_rank=current_rank,
        format_cell=format_cell,
        format_position=format_position,
        format_runner=format_runner,
        log_block=log_block,
        record_hiyuki_npc_path_contact=record_hiyuki_npc_path_contact,
    )


def build_runner_action_helpers(
    *,
    add_group_to_position: Callable[..., Any],
    format_runner: Callable[[int], str],
    log_block: Callable[..., Any],
    log_grid: Callable[..., Any],
    maybe_arm_aemeath_pending: Callable[..., Any],
    record_hiyuki_npc_path_contact: Callable[..., Any],
) -> RunnerActionHelpers:
    return RunnerActionHelpers(
        add_group_to_position=add_group_to_position,
        format_runner=format_runner,
        log_block=log_block,
        log_grid=log_grid,
        maybe_arm_aemeath_pending=maybe_arm_aemeath_pending,
        record_hiyuki_npc_path_contact=record_hiyuki_npc_path_contact,
    )


def build_skill_hook_helpers(
    *,
    add_group_to_position: Callable[..., Any],
    current_rank: Callable[..., Any],
    format_cell: Callable[[Any], str],
    format_position: Callable[[int], str],
    format_runner: Callable[[int], str],
    log_block: Callable[..., Any],
    log_timing: Callable[..., Any],
) -> SkillHookHelpers:
    return SkillHookHelpers(
        add_group_to_position=add_group_to_position,
        current_rank=current_rank,
        format_cell=format_cell,
        format_position=format_position,
        format_runner=format_runner,
        log_block=log_block,
        log_timing=log_timing,
    )
