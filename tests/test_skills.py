"""Per-runner skills tests.

Split from the original monolithic tests/test_cubie_derby.py to
make selective runs and code review tractable. The shared
imports and helpers (fake RNGs, argparse_namespace fixture, etc.)
live in tests/_shared.py.
"""
from __future__ import annotations

import unittest

from tests._shared import *  # noqa: F401,F403  (test fixtures)


class SkillsTests(unittest.TestCase):
    def test_sigrika_marks_two_immediately_higher_ranked_runners(self):
        grid = {2: [16], 3: [13], 4: [15], 5: [14], 31: [-1]}
        progress = {13: 3, 14: 5, 15: 4, 16: 2, -1: 31}

        debuffed = mark_sigrika_debuffs(
            runners=(13, 14, 15, 16),
            progress=progress,
            grid=grid,
        )

        self.assertEqual(debuffed, {14, 15})

    def test_sigrika_marks_on_first_round_for_fixed_start(self):
        grid = {2: [16], 3: [13], 4: [15], 5: [14]}
        progress = {13: 3, 14: 5, 15: 4, 16: 2}

        debuffed = mark_sigrika_debuffs(
            runners=(13, 14, 15, 16),
            progress=progress,
            grid=grid,
            round_number=1,
        )

        self.assertEqual(debuffed, {14, 15})

    def test_sigrika_does_not_mark_on_first_round_for_random_stack_start(self):
        grid = {2: [16], 3: [13], 4: [15], 5: [14]}
        progress = {13: 3, 14: 5, 15: 4, 16: 2}

        debuffed = mark_sigrika_debuffs(
            runners=(13, 14, 15, 16),
            progress=progress,
            grid=grid,
            round_number=1,
            skip_first_round=True,
        )

        self.assertEqual(debuffed, set())

    def test_sigrika_debuff_reduces_steps_but_not_below_one(self):
        debuffed = {14, 15}

        self.assertEqual(apply_sigrika_debuff(player=14, total_steps=5, debuffed=debuffed), 4)
        self.assertEqual(apply_sigrika_debuff(player=15, total_steps=1, debuffed=debuffed), 1)
        self.assertEqual(apply_sigrika_debuff(player=16, total_steps=5, debuffed=debuffed), 5)

    def test_denia_gets_bonus_when_current_dice_matches_previous_round(self):
        state = RaceSkillState()

        self.assertEqual(check_denia_skill(state, 2), 0)
        self.assertEqual(state.denia_last_dice, 2)
        self.assertEqual(check_denia_skill(state, 2), 2)
        self.assertEqual(check_denia_skill(state, 3), 0)
        self.assertEqual(state.denia_last_dice, 3)

    def test_hiyuki_bonus_is_capped_after_first_contact(self):
        state = RaceSkillState()

        self.assertEqual(check_hiyuki_bonus(state), 0)
        state.hiyuki_bonus_steps = 2
        self.assertEqual(check_hiyuki_bonus(state), 1)

    def test_player1_skill_checks_actor_left_after_action(self):
        grid = {5: [2, 1]}
        progress = {1: 5, 2: 5}

        maybe_trigger_player1_skill_after_action(
            grid=grid,
            progress=progress,
            actor=2,
            track_length=24,
            rng=CountingRandom(0.1),
        )

        self.assertEqual(grid[5], [1, 2])

    def test_player1_skill_requires_actor_left_of_player1(self):
        grid = {5: [3, 1, 2]}
        progress = {1: 5, 2: 5, 3: 5}
        rng = CountingRandom(0.1)

        maybe_trigger_player1_skill_after_action(
            grid=grid,
            progress=progress,
            actor=2,
            track_length=24,
            rng=rng,
        )

        self.assertEqual(grid[5], [3, 1, 2])
        self.assertEqual(rng.random_calls, 0)

    def test_player1_skill_checks_actor_left_even_with_multiple_left_runners(self):
        grid = {5: [2, 3, 1]}
        progress = {1: 5, 2: 5, 3: 5}
        rng = CountingRandom(0.1)

        maybe_trigger_player1_skill_after_action(
            grid=grid,
            progress=progress,
            actor=3,
            track_length=24,
            rng=rng,
        )

        self.assertEqual(grid[5], [1, 2, 3])
        self.assertEqual(rng.random_calls, 1)

    def test_player1_skill_requires_actor_to_be_immediately_left(self):
        grid = {5: [2, 3, 1]}
        progress = {1: 5, 2: 5, 3: 5}
        rng = CountingRandom(0.1)

        maybe_trigger_player1_skill_after_action(
            grid=grid,
            progress=progress,
            actor=2,
            track_length=24,
            rng=rng,
        )

        self.assertEqual(grid[5], [2, 3, 1])
        self.assertEqual(rng.random_calls, 0)

    def test_player1_skill_does_not_check_left_side_when_actor_elsewhere(self):
        grid = {5: [3, 1], 7: [2]}
        progress = {1: 5, 2: 7, 3: 5}
        rng = CountingRandom(0.1)

        maybe_trigger_player1_skill_after_action(
            grid=grid,
            progress=progress,
            actor=2,
            track_length=24,
            rng=rng,
        )

        self.assertEqual(grid[5], [3, 1])
        self.assertEqual(grid[7], [2])
        self.assertEqual(rng.random_calls, 0)

    def test_player1_skill_can_retry_after_previous_failure(self):
        grid = {5: [2, 1]}
        progress = {1: 5, 2: 5}
        first_rng = CountingRandom(0.9)

        maybe_trigger_player1_skill_after_action(
            grid=grid,
            progress=progress,
            actor=2,
            track_length=24,
            rng=first_rng,
        )

        self.assertEqual(grid[5], [2, 1])
        self.assertEqual(first_rng.random_calls, 1)

        grid[5] = [2, 3, 1]
        progress[3] = 5
        second_rng = CountingRandom(0.1)
        maybe_trigger_player1_skill_after_action(
            grid=grid,
            progress=progress,
            actor=3,
            track_length=24,
            rng=second_rng,
        )

        self.assertEqual(grid[5], [1, 2, 3])
        self.assertEqual(second_rng.random_calls, 1)

    def test_player1_skill_can_retry_after_previous_success(self):
        grid = {5: [2, 1]}
        progress = {1: 5, 2: 5}
        first_rng = CountingRandom(0.1)

        maybe_trigger_player1_skill_after_action(
            grid=grid,
            progress=progress,
            actor=2,
            track_length=24,
            rng=first_rng,
        )

        self.assertEqual(grid[5], [1, 2])
        self.assertEqual(first_rng.random_calls, 1)

        grid[5] = [3, 1, 2]
        progress[3] = 5
        second_rng = CountingRandom(0.1)
        maybe_trigger_player1_skill_after_action(
            grid=grid,
            progress=progress,
            actor=3,
            track_length=24,
            rng=second_rng,
        )

        self.assertEqual(grid[5], [1, 3, 2])
        self.assertEqual(second_rng.random_calls, 1)

    def test_player1_skill_waits_for_final_position_after_cell_effects(self):
        config = RaceConfig(
            runners=(1, 2),
            track_length=32,
            start_grid={2: (2,), 3: (1,)},
            season=2,
            forward_cells=frozenset({3}),
        )
        grid = {2: [2], 3: [1]}
        progress = {1: 3, 2: 2}
        rng = CountingRandom(0.1)

        move_single_runner(
            grid=grid,
            progress=progress,
            config=config,
            player=2,
            total_steps=1,
            rng=rng,
        )
        maybe_trigger_player1_skill_after_action(
            grid=grid,
            progress=progress,
            actor=2,
            track_length=32,
            rng=rng,
        )

        self.assertEqual(grid[3], [1])
        self.assertEqual(grid[4], [2])
        self.assertEqual(rng.random_calls, 0)

    def test_player1_skill_can_trigger_when_actor_cannot_move(self):
        config = RaceConfig(
            runners=(19, 1),
            track_length=32,
            start_grid={5: (19, 1)},
            initial_order_mode="fixed",
            fixed_initial_order=(19, 1),
        )
        trace = TraceLogger()

        simulate_race(config, QueuedFloatDiceShuffleRandom(random_values=[0.7, 0.1], dice_value=1), trace=trace)
        first_action = first_trace_action(trace.text(), "琳奈")

        self.assertIn("琳奈本回合无法移动：", first_action)
        self.assertIn("视为主动移动0格，原地停留", first_action)
        self.assertIn("今汐技能进入概率判定：", first_action)
        self.assertIn("今汐技能触发：", first_action)

    def test_player1_skill_can_trigger_when_no_move_actor_keeps_left_carry_queue(self):
        config = RaceConfig(
            runners=(2, 19, 1),
            track_length=32,
            start_grid={5: (2, 19, 1)},
            initial_order_mode="fixed",
            fixed_initial_order=(19, 2, 1),
        )
        trace = TraceLogger()

        simulate_race(config, QueuedFloatDiceShuffleRandom(random_values=[0.7, 0.1], dice_value=1), trace=trace)
        first_action = first_trace_action(trace.text(), "琳奈")

        self.assertIn("琳奈本回合无法移动：", first_action)
        self.assertIn("视为主动移动0格，原地停留", first_action)
        self.assertIn("格内顺序：[长离, 琳奈, 今汐]", first_action)
        self.assertIn("今汐技能进入概率判定：", first_action)
        self.assertIn("左侧角色：[琳奈]", first_action)
        self.assertIn("今汐技能触发：", first_action)

    def test_player1_skill_no_move_still_requires_actor_to_be_immediately_left(self):
        config = RaceConfig(
            runners=(2, 19, 3, 1),
            track_length=32,
            start_grid={5: (2, 19, 3, 1)},
            initial_order_mode="fixed",
            fixed_initial_order=(19, 2, 3, 1),
        )
        trace = TraceLogger()

        simulate_race(config, QueuedFloatDiceShuffleRandom(random_values=[0.7, 0.1], dice_value=1), trace=trace)
        first_action = first_trace_action(trace.text(), "琳奈")

        self.assertIn("琳奈本回合无法移动：", first_action)
        self.assertIn("视为主动移动0格，原地停留", first_action)
        self.assertIn("今汐技能不判定：", first_action)
        self.assertIn("原因：行动角色不紧邻今汐左侧", first_action)
        self.assertNotIn("今汐技能进入概率判定：", first_action)

    def test_player1_skill_can_trigger_after_shuffle_moves_actor_to_left(self):
        config = RaceConfig(
            runners=(1, 2),
            track_length=32,
            start_grid={5: (1, 2)},
            shuffle_cells=frozenset({6}),
            initial_order_mode="fixed",
            fixed_initial_order=(2, 1),
        )
        trace = TraceLogger()

        simulate_race(config, FixedDiceShuffleRandom(random_value=0.1, dice_value=1), trace=trace)
        first_action = first_trace_action(trace.text(), "长离")

        self.assertIn("效果：随机打乱格内顺序", first_action)
        self.assertIn("格内顺序：[长离, 今汐]", first_action)
        self.assertIn("今汐技能触发：", first_action)
        self.assertIn("原左侧角色：[长离]", first_action)

    def test_player1_skill_can_trigger_after_no_move_shuffle_reorders_left_side(self):
        config = RaceConfig(
            runners=(19, 1),
            track_length=32,
            start_grid={6: (1, 19)},
            shuffle_cells=frozenset({6}),
            initial_order_mode="fixed",
            fixed_initial_order=(19, 1),
        )
        trace = TraceLogger()

        simulate_race(config, QueuedFloatDiceShuffleRandom(random_values=[0.7, 0.1], dice_value=1), trace=trace)
        first_action = first_trace_action(trace.text(), "琳奈")

        self.assertIn("琳奈本回合无法移动：", first_action)
        self.assertIn("效果：随机打乱格内顺序", first_action)
        self.assertIn("今汐技能进入概率判定：", first_action)
        self.assertIn("今汐技能触发：", first_action)
        self.assertIn("原左侧角色：[琳奈]", first_action)

    def test_player1_skill_does_not_trigger_after_npc_moves_group_to_jinhsi_left_side(self):
        grid = {18: [3, 1, -1]}
        progress = {1: 18, 3: 18, -1: 18}
        rng = CountingRandom(0.1)

        maybe_trigger_player1_skill_after_action(
            grid=grid,
            progress=progress,
            actor=-1,
            track_length=32,
            rng=rng,
        )

        self.assertEqual(grid[18], [3, 1, -1])
        self.assertEqual(rng.random_calls, 0)

    def test_camellya_skill_triggers_at_fifty_percent_and_moves_alone(self):
        config = RaceConfig(
            runners=(4, 5),
            track_length=8,
            start_grid=make_start_grid(8, {0: (4, 5)}),
            initial_order_mode="fixed",
            fixed_initial_order=(5, 4),
        )
        trace = TraceLogger()

        simulate_race(config, FixedDiceRandom(random_value=0.1, dice_value=2), trace=trace)
        first_action = first_trace_action(trace.text(), "椿")

        self.assertIn("椿技能触发：", first_action)
        self.assertIn("移动队列：[椿]", first_action)
        self.assertIn("到达位置：第3格", first_action)

    def test_camellya_skill_failure_moves_with_left_side(self):
        config = RaceConfig(
            runners=(4, 5),
            track_length=8,
            start_grid=make_start_grid(8, {0: (4, 5)}),
            initial_order_mode="fixed",
            fixed_initial_order=(5, 4),
        )
        trace = TraceLogger()

        simulate_race(config, FixedDiceRandom(random_value=0.9, dice_value=2), trace=trace)
        first_action = first_trace_action(trace.text(), "椿")

        self.assertIn("椿技能未触发：", first_action)
        self.assertIn("移动队列：[守岸人, 椿]", first_action)
        self.assertIn("到达位置：第2格", first_action)

    def test_hiyuki_gains_bonus_when_landing_on_npc(self):
        config = RaceConfig(
            runners=(16,),
            track_length=32,
            start_grid={0: (16,)},
        )
        grid = {0: [16], 2: [-1]}
        progress = {16: 0, -1: 2}
        state = RaceSkillState()

        move_single_runner(
            grid=grid,
            progress=progress,
            config=config,
            player=16,
            total_steps=2,
            rng=random.Random(1),
            skill_state=state,
        )

        self.assertEqual(state.hiyuki_bonus_steps, 1)
        self.assertEqual(grid[2], [16, -1])

    def test_hiyuki_does_not_trigger_on_waiting_npc_before_round_three(self):
        config = RaceConfig(
            runners=(16,),
            track_length=32,
            start_grid={-1: (16,)},
            season=2,
            npc_enabled=True,
        )
        grid = {-1: [16], 0: [-1]}
        progress = {16: -1}
        state = RaceSkillState()

        move_single_runner(
            grid=grid,
            progress=progress,
            config=config,
            player=16,
            total_steps=1,
            rng=random.Random(1),
            skill_state=state,
        )

        self.assertEqual(state.hiyuki_bonus_steps, 0)
        self.assertEqual(grid[0], [16, -1])

    def test_hiyuki_gains_bonus_when_passing_through_npc(self):
        config = RaceConfig(
            runners=(16,),
            track_length=32,
            start_grid={0: (16,)},
        )
        grid = {0: [16], 2: [-1]}
        progress = {16: 0, -1: 2}
        state = RaceSkillState()

        move_single_runner(
            grid=grid,
            progress=progress,
            config=config,
            player=16,
            total_steps=3,
            rng=random.Random(1),
            skill_state=state,
        )

        self.assertEqual(state.hiyuki_bonus_steps, 1)
        self.assertEqual(grid[2], [-1])
        self.assertEqual(grid[3], [16])

    def test_hiyuki_contact_only_triggers_once(self):
        config = RaceConfig(
            runners=(16,),
            track_length=32,
            start_grid={0: (16,)},
        )
        grid = {0: [16], 2: [-1]}
        progress = {16: 0, -1: 2}
        state = RaceSkillState()

        move_single_runner(
            grid=grid,
            progress=progress,
            config=config,
            player=16,
            total_steps=2,
            rng=random.Random(1),
            skill_state=state,
        )
        grid = {2: [16], 4: [-1]}
        progress = {16: 2, -1: 4}
        move_single_runner(
            grid=grid,
            progress=progress,
            config=config,
            player=16,
            total_steps=2,
            rng=random.Random(1),
            skill_state=state,
        )

        self.assertEqual(state.hiyuki_bonus_steps, 1)
        self.assertEqual(state.success_counts[16], 1)

    def test_hiyuki_gains_bonus_when_npc_lands_on_hiyuki_before_cell_effect(self):
        config = RaceConfig(
            runners=(16,),
            track_length=32,
            start_grid={28: (16,)},
            season=2,
            backward_cells=frozenset({28}),
        )
        grid = {28: [16]}
        progress = {16: 28, -1: 0}
        state = RaceSkillState()

        npc_progress = move_npc(
            grid=grid,
            progress=progress,
            config=config,
            npc_progress=0,
            rng=FixedDiceRandom(random_value=0.1, dice_value=4),
            skill_state=state,
            trace=False,
        )

        self.assertEqual(state.hiyuki_bonus_steps, 1)
        self.assertEqual(npc_progress, 27)
        self.assertEqual(grid[28], [16])
        self.assertEqual(grid[27], [-1])

    def test_hiyuki_gains_bonus_when_npc_passes_through_hiyuki(self):
        config = RaceConfig(
            runners=(16,),
            track_length=32,
            start_grid={29: (16,)},
        )
        grid = {29: [16]}
        progress = {16: 29, -1: 0}
        state = RaceSkillState()

        npc_progress = move_npc(
            grid=grid,
            progress=progress,
            config=config,
            npc_progress=0,
            rng=FixedDiceRandom(random_value=0.1, dice_value=4),
            skill_state=state,
            trace=False,
        )

        self.assertEqual(state.hiyuki_bonus_steps, 1)
        self.assertEqual(npc_progress, 28)
        self.assertNotIn(29, grid)
        self.assertEqual(grid[28], [16, -1])

    def test_shorekeeper_skill_dice_can_be_disabled(self):
        enabled_config = RaceConfig(runners=(4,), track_length=8, start_grid={0: (4,)})
        disabled_config = RaceConfig(
            runners=(4,),
            track_length=8,
            start_grid={0: (4,)},
            disabled_skills=frozenset({4}),
        )
        enabled_state = RaceSkillState()
        disabled_state = RaceSkillState()

        enabled_dice = roll_dice(4, FixedDiceRandom(random_value=0.1, dice_value=2), config=enabled_config, skill_state=enabled_state)
        disabled_dice = roll_dice(4, FixedDiceRandom(random_value=0.1, dice_value=1), config=disabled_config, skill_state=disabled_state)

        self.assertEqual(enabled_dice, 2)
        self.assertEqual(disabled_dice, 1)
        self.assertEqual(enabled_state.success_counts[4], 1)
        self.assertNotIn(4, disabled_state.success_counts)

    def test_chisa_gets_bonus_when_tied_for_lowest_dice(self):
        state = RaceSkillState()

        bonus = check_chisa_skill(state, 1, {17: 1, 18: 1, -1: 2})

        self.assertEqual(bonus, 2)
        self.assertEqual(state.success_counts[17], 1)

    def test_mornye_dice_cycles_three_two_one(self):
        config = RaceConfig(runners=(18,), track_length=8, start_grid={0: (18,)})
        state = RaceSkillState()
        rng = FixedDiceRandom(random_value=0.9, dice_value=1)

        rolls = [roll_dice(18, rng, config=config, skill_state=state) for _ in range(4)]

        self.assertEqual(rolls, [3, 2, 1, 3])
        self.assertEqual(state.success_counts[18], 4)

    def test_lynae_can_double_or_fail_to_move(self):
        doubled_state = RaceSkillState()
        stopped_state = RaceSkillState()

        doubled_steps, doubled_adjustment = apply_lynae_skill(
            doubled_state,
            CountingRandom(0.5),
            dice=3,
            total_steps=3,
        )
        stopped_steps, stopped_adjustment = apply_lynae_skill(
            stopped_state,
            CountingRandom(0.7),
            dice=3,
            total_steps=3,
        )

        self.assertEqual((doubled_steps, doubled_adjustment), (6, 3))
        self.assertEqual(doubled_state.success_counts[19], 1)
        self.assertEqual((stopped_steps, stopped_adjustment), (0, -3))
        self.assertNotIn(19, stopped_state.success_counts)

    def test_lynae_cannot_move_on_shuffle_cell_still_triggers_shuffle(self):
        config = RaceConfig(
            runners=(19, 3),
            track_length=32,
            start_grid={6: (19,), 1: (3,)},
            season=2,
            shuffle_cells=frozenset({6}),
            initial_order_mode="fixed",
            fixed_initial_order=(19, 3),
        )
        trace = TraceLogger()

        simulate_race(config, FixedDiceRandom(random_value=0.7, dice_value=1), trace=trace)
        first_action = first_trace_action(trace.text(), "琳奈")

        self.assertIn("琳奈本回合无法移动：", first_action)
        self.assertIn("视为主动移动0格，原地停留", first_action)
        self.assertIn("检查第6格是否为打乱顺序格", first_action)
        self.assertIn("效果：随机打乱格内顺序", first_action)
        self.assertEqual(apply_sigrika_debuff(player=19, total_steps=0, debuffed={19}), 0)

    def test_augusta_does_not_trigger_in_round_one_for_random_start_stack(self):
        config = RaceConfig(
            runners=(21, 12),
            track_length=8,
            start_grid={},
            random_start_stack=True,
            random_start_position=1,
            initial_order_mode="start",
            fixed_initial_order=(21, 12),
        )
        trace = TraceLogger()

        simulate_race(config, FixedDiceRandom(random_value=0.9, dice_value=1), trace=trace)
        text = trace.text()
        first_action = first_trace_action(text, "奥古斯塔")

        self.assertIn("奥古斯塔技能本回合不判定：", first_action)
        self.assertIn("原因：随机同格开局时，第一回合不发动技能", first_action)
        self.assertNotIn("奥古斯塔技能触发：", first_action)

    def test_augusta_can_trigger_in_round_one_for_custom_start_layout(self):
        config = RaceConfig(
            runners=(21, 12),
            track_length=8,
            start_grid={0: (21, 12)},
            initial_order_mode="fixed",
            fixed_initial_order=(21, 12),
        )
        trace = TraceLogger()

        simulate_race(config, FixedDiceRandom(random_value=0.9, dice_value=1), trace=trace)
        first_action = first_trace_action(trace.text(), "奥古斯塔")

        self.assertIn("奥古斯塔技能触发：", first_action)
        self.assertNotIn("奥古斯塔技能本回合不判定：", first_action)

    def test_augusta_and_changli_forced_last_follow_trigger_order(self):
        order = next_round_action_order(
            runners=(21, 2, 12),
            rng=random.Random(1),
            include_npc=False,
            forced_last_runners=(21, 2),
        )

        self.assertEqual(order[-2:], [21, 2])

    def test_phrolova_does_not_trigger_in_round_one_for_random_start_stack(self):
        config = RaceConfig(
            runners=(12, 23),
            track_length=8,
            start_grid={},
            random_start_stack=True,
            random_start_position=1,
            initial_order_mode="start",
            fixed_initial_order=(23, 12),
        )
        trace = TraceLogger()

        simulate_race(config, FixedDiceRandom(random_value=0.9, dice_value=1), trace=trace)
        first_action = first_trace_action(trace.text(), "弗洛洛")
        self.assertIn("弗洛洛技能本回合不判定：", first_action)
        self.assertIn("原因：随机同格开局时，第一回合不发动技能", first_action)
        self.assertNotIn("弗洛洛技能触发：", first_action)

    def test_phrolova_can_trigger_in_round_one_for_custom_start_layout(self):
        config = RaceConfig(
            runners=(12, 23),
            track_length=8,
            start_grid={0: (12, 23)},
            initial_order_mode="fixed",
            fixed_initial_order=(23, 12),
        )
        trace = TraceLogger()

        simulate_race(config, FixedDiceRandom(random_value=0.9, dice_value=1), trace=trace)
        first_action = first_trace_action(trace.text(), "弗洛洛")
        self.assertIn("弗洛洛技能触发：", first_action)
        self.assertNotIn("弗洛洛技能本回合不判定：", first_action)

    def test_luno_gathers_all_non_npc_runners_to_own_cell_in_rank_order(self):
        config = RaceConfig(
            runners=(22, 1, 3, 5, 7),
            track_length=32,
            start_grid={17: (22,), 25: (1,), 21: (3,), 14: (5,), 9: (7,)},
        )
        grid = {17: [22], 25: [1], 21: [3], 14: [5], 9: [7]}
        progress = {22: 17, 1: 25, 3: 21, 5: 14, 7: 9}
        state = RaceSkillState()
        rng = random.Random(1)

        move_single_runner(
            grid=grid,
            progress=progress,
            config=config,
            player=22,
            total_steps=1,
            rng=rng,
            skill_state=state,
        )
        maybe_trigger_luno_after_action(
            grid=grid,
            progress=progress,
            config=config,
            skill_state=state,
        )

        self.assertEqual(grid[18], [1, 3, 22, 5, 7])
        self.assertEqual(progress[22], 18)
        self.assertEqual(progress[1], 18)
        self.assertEqual(progress[3], 18)
        self.assertEqual(progress[5], 18)
        self.assertEqual(progress[7], 18)
        self.assertFalse(state.luno_available)
        self.assertEqual(state.success_counts[22], 1)

    def test_luno_requires_runners_on_both_sides_and_keeps_skill_until_later_trigger(self):
        config = RaceConfig(
            runners=(22, 1, 3),
            track_length=32,
            start_grid={25: (22,), 20: (1,), 18: (3,)},
        )
        state = RaceSkillState()

        grid = {25: [22], 20: [1], 18: [3]}
        progress = {22: 25, 1: 20, 3: 18}
        maybe_trigger_luno_after_action(
            grid=grid,
            progress=progress,
            config=config,
            skill_state=state,
        )

        self.assertEqual(grid[25], [22])
        self.assertEqual(grid[20], [1])
        self.assertEqual(grid[18], [3])
        self.assertTrue(state.luno_available)
        self.assertNotIn(22, state.success_counts)

        grid = {26: [22], 29: [1], 21: [3]}
        progress = {22: 26, 1: 29, 3: 21}
        maybe_trigger_luno_after_action(
            grid=grid,
            progress=progress,
            config=config,
            skill_state=state,
        )

        self.assertEqual(grid[26], [1, 22, 3])
        self.assertEqual(progress[22], 26)
        self.assertEqual(progress[1], 26)
        self.assertEqual(progress[3], 26)
        self.assertFalse(state.luno_available)
        self.assertEqual(state.success_counts[22], 1)

    def test_luno_can_trigger_when_not_first_or_last_even_if_all_runners_share_one_cell(self):
        config = RaceConfig(
            runners=(22, 1, 3),
            track_length=32,
            start_grid={25: (1, 22, 3)},
        )
        state = RaceSkillState()
        grid = {25: [1, 22, 3]}
        progress = {22: 25, 1: 25, 3: 25}

        maybe_trigger_luno_after_action(
            grid=grid,
            progress=progress,
            config=config,
            skill_state=state,
        )

        self.assertEqual(grid[25], [1, 22, 3])
        self.assertFalse(state.luno_available)
        self.assertEqual(state.success_counts[22], 1)

    def test_luno_skill_does_not_trigger_player1_skill(self):
        config = RaceConfig(
            runners=(22, 1, 3, 5),
            track_length=32,
            start_grid={17: (22,), 15: (1,), 23: (3,), 10: (5,)},
            initial_order_mode="fixed",
            fixed_initial_order=(22, 1, 3, 5),
        )
        trace = TraceLogger()

        simulate_race(config, FixedDiceRandom(random_value=0.1, dice_value=1), trace=trace)
        first_action = first_trace_action(trace.text(), "尤诺")

        self.assertIn("今汐技能不判定：", first_action)
        self.assertIn("原因：行动角色终点未与自己同格", first_action)
        self.assertIn("尤诺技能触发：", first_action)
        self.assertNotIn("今汐技能触发：", first_action)

    def test_aemeath_triggers_only_after_active_move_ends(self):
        config = RaceConfig(runners=(20, 2, 3), track_length=32, start_grid={15: (20,), 22: (2,), 25: (3,)})
        grid = {15: [20], 22: [2], 25: [3]}
        progress = {20: 15, 2: 22, 3: 25}
        state = RaceSkillState()
        rng = random.Random(1)

        new_progress = move_single_runner(
            grid=grid,
            progress=progress,
            config=config,
            player=20,
            total_steps=3,
            rng=rng,
            skill_state=state,
        )

        self.assertEqual(new_progress, 18)
        self.assertEqual(progress[20], 18)
        self.assertEqual(grid[18], [20])
        self.assertTrue(state.aemeath_available)
        self.assertTrue(state.aemeath_ready)
        self.assertNotIn(20, state.success_counts)

        maybe_trigger_aemeath_after_active_move(
            grid=grid,
            progress=progress,
            config=config,
            start_progress=15,
            action_had_forward_movement=True,
            rng=rng,
            skill_state=state,
        )

        self.assertEqual(progress[20], 22)
        self.assertNotIn(18, grid)
        self.assertEqual(grid[22], [20, 2])
        self.assertFalse(state.aemeath_available)
        self.assertFalse(state.aemeath_ready)
        self.assertEqual(state.success_counts[20], 1)

    def test_aemeath_keeps_pending_state_until_later_active_move(self):
        config = RaceConfig(runners=(20, 2, 3), track_length=32, start_grid={16: (20,), 10: (2,), 24: (3,)})
        grid = {16: [20], 10: [2], 24: [3]}
        progress = {20: 16, 2: 10, 3: 24}
        state = RaceSkillState()
        rng = random.Random(1)

        move_single_runner(
            grid=grid,
            progress=progress,
            config=config,
            player=20,
            total_steps=2,
            rng=rng,
            skill_state=state,
        )
        self.assertEqual(progress[20], 18)
        self.assertTrue(state.aemeath_ready)
        self.assertTrue(state.aemeath_available)

        progress.pop(3)
        grid.pop(24)
        maybe_trigger_aemeath_after_active_move(
            grid=grid,
            progress=progress,
            config=config,
            start_progress=16,
            action_had_forward_movement=True,
            rng=rng,
            skill_state=state,
        )
        self.assertEqual(progress[20], 18)
        self.assertIn(18, grid)
        self.assertTrue(state.aemeath_ready)
        self.assertTrue(state.aemeath_available)
        self.assertNotIn(20, state.success_counts)

        progress[3] = 24
        grid[24] = [3]
        move_single_runner(
            grid=grid,
            progress=progress,
            config=config,
            player=20,
            total_steps=1,
            rng=rng,
            skill_state=state,
        )
        maybe_trigger_aemeath_after_active_move(
            grid=grid,
            progress=progress,
            config=config,
            start_progress=18,
            action_had_forward_movement=True,
            rng=rng,
            skill_state=state,
        )

        self.assertEqual(progress[20], 24)
        self.assertNotIn(19, grid)
        self.assertEqual(grid[24], [20, 3])
        self.assertFalse(state.aemeath_available)
        self.assertFalse(state.aemeath_ready)
        self.assertEqual(state.success_counts[20], 1)

    def test_aemeath_carried_past_midpoint_arms_but_waits_for_own_action(self):
        config = RaceConfig(runners=(20, 2, 3), track_length=32, start_grid={16: (20, 2), 22: (3,)})
        grid = {16: [20, 2], 22: [3]}
        progress = {20: 16, 2: 16, 3: 22}
        state = RaceSkillState()
        rng = random.Random(1)

        new_progress = move_runner_with_left_side(
            grid=grid,
            progress=progress,
            config=config,
            player=2,
            idx_in_cell=1,
            total_steps=3,
            rng=rng,
            skill_state=state,
        )

        self.assertEqual(new_progress, 19)
        self.assertEqual(progress[20], 19)
        self.assertEqual(progress[2], 19)
        self.assertEqual(grid[19], [20, 2])
        self.assertTrue(state.aemeath_available)
        self.assertTrue(state.aemeath_ready)
        self.assertNotIn(20, state.success_counts)

        move_single_runner(
            grid=grid,
            progress=progress,
            config=config,
            player=20,
            total_steps=1,
            rng=rng,
            skill_state=state,
        )
        maybe_trigger_aemeath_after_active_move(
            grid=grid,
            progress=progress,
            config=config,
            start_progress=19,
            action_had_forward_movement=True,
            rng=rng,
            skill_state=state,
        )

        self.assertEqual(progress[2], 19)
        self.assertEqual(progress[20], 22)
        self.assertEqual(grid[19], [2])
        self.assertEqual(grid[22], [20, 3])
        self.assertFalse(state.aemeath_available)
        self.assertFalse(state.aemeath_ready)
        self.assertEqual(state.success_counts[20], 1)

    def test_aemeath_teleport_leaves_carried_runners_on_action_endpoint(self):
        config = RaceConfig(runners=(2, 3, 20), track_length=32, start_grid={15: (2, 20), 24: (3,)})
        grid = {15: [2, 20], 24: [3]}
        progress = {2: 15, 20: 15, 3: 24}
        state = RaceSkillState()
        rng = random.Random(1)

        new_progress = move_runner_with_left_side(
            grid=grid,
            progress=progress,
            config=config,
            player=20,
            idx_in_cell=1,
            total_steps=3,
            rng=rng,
            skill_state=state,
        )

        self.assertEqual(new_progress, 18)
        self.assertEqual(progress[2], 18)
        self.assertEqual(progress[20], 18)
        self.assertEqual(grid[18], [2, 20])

        maybe_trigger_aemeath_after_active_move(
            grid=grid,
            progress=progress,
            config=config,
            start_progress=15,
            action_had_forward_movement=True,
            rng=rng,
            skill_state=state,
        )

        self.assertEqual(progress[2], 18)
        self.assertEqual(progress[20], 24)
        self.assertEqual(grid[18], [2])
        self.assertEqual(grid[24], [20, 3])
        self.assertFalse(state.aemeath_available)
        self.assertFalse(state.aemeath_ready)

    def test_aemeath_backward_movement_does_not_enter_pending_state(self):
        config = RaceConfig(runners=(20, 2), track_length=32, start_grid={18: (20,), 22: (2,)})
        grid = {18: [20], 22: [2]}
        progress = {20: 18, 2: 22}
        state = RaceSkillState()

        move_group_due_to_cell_effect(
            grid,
            progress,
            [20],
            18,
            -1,
            random.Random(1),
            config,
            active_player=20,
            skill_state=state,
        )

        self.assertEqual(progress[20], 17)
        self.assertEqual(grid[17], [20])
        self.assertTrue(state.aemeath_available)
        self.assertFalse(state.aemeath_ready)
        self.assertNotIn(20, state.success_counts)

    def test_aemeath_carried_backward_by_npc_does_not_enter_pending_state(self):
        config = RaceConfig(runners=(20, 2), track_length=32, start_grid={18: (20,), 22: (2,)}, npc_enabled=True)
        grid = {18: [20, -1], 22: [2]}
        progress = {20: 18, -1: 18, 2: 22}
        state = RaceSkillState()

        npc_progress = move_npc(
            grid=grid,
            progress=progress,
            config=config,
            npc_progress=18,
            rng=random.Random(1),
            steps=1,
            skill_state=state,
            trace=False,
        )

        self.assertEqual(npc_progress, 17)
        self.assertEqual(progress[20], 17)
        self.assertEqual(progress[-1], 17)
        self.assertEqual(grid[17], [20, -1])
        self.assertTrue(state.aemeath_available)
        self.assertFalse(state.aemeath_ready)
        self.assertNotIn(20, state.success_counts)

    def test_skill_ablation_includes_shorekeeper(self):
        config = RaceConfig(
            runners=(4, 12),
            track_length=8,
            start_grid={0: (4, 12)},
        )

        ablation = run_skill_ablation(config, 10, seed=3)

        self.assertIn(4, {row.runner for row in ablation.rows})

    def test_disabled_phoebe_skill_does_not_record_success(self):
        config = RaceConfig(
            runners=(12,),
            track_length=3,
            start_grid={0: (12,)},
            disabled_skills=frozenset({12}),
        )

        result = simulate_race(config, FixedDiceRandom(random_value=0.1, dice_value=2))

        self.assertNotIn((12, 1), result.skill_success_counts)
        self.assertEqual(dict(result.skill_success_counts).get(12, 0), 0)

    def test_enabled_phoebe_skill_records_success(self):
        config = RaceConfig(
            runners=(12,),
            track_length=3,
            start_grid={0: (12,)},
        )

        result = simulate_race(config, FixedDiceRandom(random_value=0.1, dice_value=2))

        self.assertEqual(dict(result.skill_success_counts).get(12), 1)

    def test_skill_ablation_runs_base_plus_one_disabled_scenario(self):
        config = RaceConfig(
            runners=(12,),
            track_length=8,
            start_grid={0: (12,)},
        )

        ablation = run_skill_ablation(config, 20, targets=(12,), seed=3)
        row = ablation.rows[0]

        self.assertEqual(ablation.iterations, 20)
        self.assertEqual(ablation.total_simulated_races, 40)
        self.assertEqual(row.enabled_win_rate, ablation.base_summary.rows[0].win_rate)
        self.assertEqual(row.disabled_win_rate, 1.0)
        self.assertGreater(row.skill_average_success_count, 0)

    def test_skill_ablation_json_omits_detail_unless_requested(self):
        config = RaceConfig(
            runners=(12,),
            track_length=8,
            start_grid={0: (12,)},
        )
        ablation = run_skill_ablation(config, 5, targets=(12,), seed=3)

        compact = skill_ablation_to_dict(ablation)
        detailed = skill_ablation_to_dict(ablation, include_detail=True)

        self.assertNotIn("success_distribution", compact["rows"][0])
        self.assertIn("success_distribution", detailed["rows"][0])


if __name__ == "__main__":
    unittest.main()
