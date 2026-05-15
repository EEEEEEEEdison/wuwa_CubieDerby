from __future__ import annotations

from typing import Any, Callable

from cubie_derby_core.action_flow import PostActionHelpers
from cubie_derby_core.effects import EffectHooks
from cubie_derby_core.npc import NPCHelpers
from cubie_derby_core.pre_action import PreActionHelpers
from cubie_derby_core.round_flow import RoundFlowHelpers
from cubie_derby_core.runner_actions import RunnerActionHelpers
from cubie_derby_core.skill_hooks import SkillHookHelpers
from cubie_derby_core.turn_flow import TurnFlowHelpers


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


def build_pre_action_helpers(
    *,
    current_rank: Callable[..., Any],
    format_cell: Callable[[Any], str],
    format_runner: Callable[[int], str],
    log_block: Callable[..., Any],
    log_rank_decision: Callable[..., Any],
    log_timing: Callable[..., Any],
    rank_scope: Callable[..., Any],
) -> PreActionHelpers:
    return PreActionHelpers(
        current_rank=current_rank,
        format_cell=format_cell,
        format_runner=format_runner,
        log_block=log_block,
        log_rank_decision=log_rank_decision,
        log_timing=log_timing,
        rank_scope=rank_scope,
    )


def build_post_action_helpers(
    *,
    current_rank: Callable[..., Any],
    format_runner: Callable[[int], str],
    log_block: Callable[..., Any],
    log_rank_decision: Callable[..., Any],
    log_timing: Callable[..., Any],
    maybe_trigger_aemeath_after_active_move: Callable[..., Any],
    maybe_trigger_luno_after_action: Callable[..., Any],
    maybe_trigger_player1_skill_after_action: Callable[..., Any],
    rank_scope: Callable[..., Any],
) -> PostActionHelpers:
    return PostActionHelpers(
        current_rank=current_rank,
        format_runner=format_runner,
        log_block=log_block,
        log_rank_decision=log_rank_decision,
        log_timing=log_timing,
        maybe_trigger_aemeath_after_active_move=maybe_trigger_aemeath_after_active_move,
        maybe_trigger_luno_after_action=maybe_trigger_luno_after_action,
        maybe_trigger_player1_skill_after_action=maybe_trigger_player1_skill_after_action,
        rank_scope=rank_scope,
    )


def build_round_flow_helpers(
    *,
    add_npc_to_start: Callable[..., Any],
    check_player2_skill: Callable[..., Any],
    chisa_has_lowest_dice: Callable[..., Any],
    format_position: Callable[[int], str],
    format_round_dice: Callable[..., Any],
    format_runner: Callable[[int], str],
    format_runner_arrow_list: Callable[..., Any],
    log: Callable[..., Any],
    log_block: Callable[..., Any],
    log_chisa_round_check: Callable[..., Any],
    log_grid: Callable[..., Any],
    log_timing: Callable[..., Any],
    mark_sigrika_debuffs: Callable[..., Any],
    next_round_action_order: Callable[..., Any],
    roll_round_dice: Callable[..., Any],
    settle_npc_end_of_round: Callable[..., Any],
    skill_enabled: Callable[..., Any],
) -> RoundFlowHelpers:
    return RoundFlowHelpers(
        add_npc_to_start=add_npc_to_start,
        check_player2_skill=check_player2_skill,
        chisa_has_lowest_dice=chisa_has_lowest_dice,
        format_position=format_position,
        format_round_dice=format_round_dice,
        format_runner=format_runner,
        format_runner_arrow_list=format_runner_arrow_list,
        log=log,
        log_block=log_block,
        log_chisa_round_check=log_chisa_round_check,
        log_grid=log_grid,
        log_timing=log_timing,
        mark_sigrika_debuffs=mark_sigrika_debuffs,
        next_round_action_order=next_round_action_order,
        roll_round_dice=roll_round_dice,
        settle_npc_end_of_round=settle_npc_end_of_round,
        skill_enabled=skill_enabled,
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


def build_turn_flow_helpers(
    *,
    apply_shuffle_cell_effect: Callable[..., Any],
    format_cell: Callable[[Any], str],
    format_position: Callable[[int], str],
    format_runner: Callable[[int], str],
    log: Callable[..., Any],
    log_block: Callable[..., Any],
    log_grid: Callable[..., Any],
    log_timing: Callable[..., Any],
    move_cantarella: Callable[..., Any],
    move_runner_with_left_side: Callable[..., Any],
    move_single_runner: Callable[..., Any],
    resolve_pre_action_state_core_fn: Callable[..., Any],
    resolve_post_action_effects_core_fn: Callable[..., Any],
    pre_action_helpers_fn: Callable[[], PreActionHelpers],
    post_action_helpers_fn: Callable[[], PostActionHelpers],
    camellya_solo_action_chance: float,
    zani_extra_steps_chance: float,
    cartethyia_extra_steps_chance: float,
    phoebe_extra_step_chance: float,
    potato_repeat_dice_chance: float,
) -> TurnFlowHelpers:
    def resolve_pre_action_state_for_turn(**kwargs: object) -> object:
        return resolve_pre_action_state_core_fn(
            helpers=pre_action_helpers_fn(),
            camellya_solo_action_chance=camellya_solo_action_chance,
            zani_extra_steps_chance=zani_extra_steps_chance,
            cartethyia_extra_steps_chance=cartethyia_extra_steps_chance,
            phoebe_extra_step_chance=phoebe_extra_step_chance,
            potato_repeat_dice_chance=potato_repeat_dice_chance,
            **kwargs,
        )

    def resolve_post_action_effects_for_turn(**kwargs: object) -> object:
        return resolve_post_action_effects_core_fn(
            helpers=post_action_helpers_fn(),
            **kwargs,
        )

    return TurnFlowHelpers(
        apply_shuffle_cell_effect=apply_shuffle_cell_effect,
        format_cell=format_cell,
        format_position=format_position,
        format_runner=format_runner,
        log=log,
        log_block=log_block,
        log_grid=log_grid,
        log_timing=log_timing,
        move_cantarella=move_cantarella,
        move_runner_with_left_side=move_runner_with_left_side,
        move_single_runner=move_single_runner,
        resolve_post_action_effects=resolve_post_action_effects_for_turn,
        resolve_pre_action_state=resolve_pre_action_state_for_turn,
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
