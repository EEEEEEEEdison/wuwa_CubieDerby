import random
import tempfile
import unittest
from pathlib import Path

from cubie_derby import (
    RaceSkillState,
    RaceConfig,
    TraceLogger,
    apply_sigrika_debuff,
    build_config_from_args,
    check_denia_skill,
    check_hiyuki_bonus,
    current_rank,
    display_position,
    display_width,
    format_summary,
    main,
    make_start_grid,
    mark_sigrika_debuffs,
    maybe_trigger_player1_skill_after_action,
    initial_player_order,
    move_npc,
    move_runner_with_left_side,
    move_single_runner,
    normalize_cli_args,
    parse_runner,
    parse_start_layout,
    parse_start_spec,
    preset_config,
    rank_scope,
    run_monte_carlo,
    season_rules,
    settle_npc_end_of_round,
    simulate_race,
)


def argparse_namespace(**kwargs):
    defaults = {
        "season": 1,
        "preset": 4,
        "runners": None,
        "track_length": None,
        "start": None,
        "initial_order": None,
    }
    defaults.update(kwargs)
    return type("Args", (), defaults)()


class CountingRandom(random.Random):
    def __init__(self, random_value: float = 0.1):
        super().__init__(1)
        self.random_value = random_value
        self.random_calls = 0

    def random(self) -> float:
        self.random_calls += 1
        return self.random_value


class FixedDiceRandom(CountingRandom):
    def __init__(self, random_value: float, dice_value: int):
        super().__init__(random_value)
        self.dice_value = dice_value

    def randint(self, a: int, b: int) -> int:
        if not a <= self.dice_value <= b:
            raise ValueError(f"fixed dice {self.dice_value} is outside {a}..{b}")
        return self.dice_value


class RecordingShuffleRandom(random.Random):
    def __init__(self):
        super().__init__(1)
        self.shuffle_inputs: list[list[int]] = []

    def shuffle(self, x) -> None:
        self.shuffle_inputs.append(list(x))
        x.reverse()


def first_trace_action(text: str, runner_name: str) -> str:
    start = text.index(f"--- {runner_name}行动 ---")
    next_start = text.find("\n--- ", start + 1)
    if next_start == -1:
        return text[start:]
    return text[start:next_start]


class CubieDerbyTests(unittest.TestCase):
    def test_single_runner_always_wins(self):
        config = RaceConfig(
            runners=(3,),
            track_length=5,
            start_grid=make_start_grid(5, {0: (3,)}),
            name="single",
        )

        summary = run_monte_carlo(config, 20, seed=7)

        self.assertEqual(summary.best.runner, 3)
        self.assertEqual(summary.rows[0].wins, 20)
        self.assertEqual(summary.rows[0].win_rate, 1.0)

    def test_preset_four_runs_and_counts_all_races(self):
        config = preset_config(4)

        summary = run_monte_carlo(config, 100, seed=42)

        self.assertEqual(sum(row.wins for row in summary.rows), 100)
        self.assertEqual({row.runner for row in summary.rows}, {3, 4, 8, 10})

    def test_format_summary_uses_chinese_aligned_table(self):
        config = RaceConfig(
            runners=(13, 14, 15, 16),
            track_length=8,
            start_grid=make_start_grid(8, {0: (13, 14, 15, 16)}),
            name="custom",
        )
        summary = run_monte_carlo(config, 12, seed=3)

        text = format_summary(summary)

        self.assertIn("赛制：自定义", text)
        self.assertIn("角色", text)
        self.assertIn("夺冠次数", text)
        self.assertIn("推荐选择：", text)
        self.assertNotIn("Scenario:", text)
        self.assertNotIn("win_rate", text)

        lines = text.splitlines()
        header_index = next(i for i, line in enumerate(lines) if line.startswith("角色"))
        table_lines = lines[header_index : header_index + 2 + len(config.runners)]
        expected_width = display_width(table_lines[0])
        self.assertTrue(all(display_width(line) == expected_width for line in table_lines))

    def test_format_summary_localizes_builtin_config_names(self):
        summary = run_monte_carlo(preset_config(4), 10, seed=1)

        text = format_summary(summary)

        self.assertIn("赛制：预设4：决赛下半区固定起点", text)

    def test_parse_custom_start_spec(self):
        self.assertEqual(parse_start_spec("1:10;2:4,3;3:8"), {1: (10,), 2: (4, 3), 3: (8,)})

    def test_parse_custom_start_spec_supports_negative_cells(self):
        self.assertEqual(parse_start_spec("-3:10;-2:4,3;0:8"), {-3: (10,), -2: (4, 3), 0: (8,)})

    def test_normalize_cli_args_preserves_negative_start_value(self):
        self.assertEqual(
            normalize_cli_args(["--start", "-3:10;-2:4,3;0:8", "--runners", "3", "4", "8", "10"]),
            ["--start=-3:10;-2:4,3;0:8", "--runners", "3", "4", "8", "10"],
        )

    def test_parse_random_stack_start_layout(self):
        self.assertEqual(parse_start_layout("0:*"), ({}, 0))

    def test_build_config_supports_random_stack_start(self):
        args = argparse_namespace(
            preset=4,
            runners=["3", "4", "8", "10"],
            track_length=25,
            start="0:*",
            initial_order=None,
        )

        config = build_config_from_args(args)

        self.assertTrue(config.random_start_stack)
        self.assertEqual(config.random_start_position, 0)
        self.assertEqual(config.runners, (3, 4, 8, 10))
        self.assertEqual(config.initial_order_mode, "start")

    def test_parse_new_runner_aliases_and_names(self):
        self.assertEqual(parse_runner("sigrika"), 13)
        self.assertEqual(parse_runner("luuk_herssen"), 14)
        self.assertEqual(parse_runner("Luuk Herssen"), 14)
        self.assertEqual(parse_runner("denia"), 15)
        self.assertEqual(parse_runner("hiyuki"), 16)
        self.assertEqual(parse_runner("西格莉卡"), 13)
        self.assertEqual(parse_runner("陆赫斯"), 14)
        self.assertEqual(parse_runner("达尼娅"), 15)
        self.assertEqual(parse_runner("绯雪"), 16)

    def test_fixed_start_at_zero_defaults_to_left_to_right_order(self):
        args = argparse_namespace(
            runners=["3", "4", "8", "10"],
            track_length=24,
            start="0:3,4,8,10",
            initial_order=None,
        )

        config = build_config_from_args(args)

        self.assertEqual(config.initial_order_mode, "start")
        self.assertEqual(initial_player_order(config, {0: [3, 4, 8, 10]}, random.Random(1)), [3, 4, 8, 10])

    def test_mixed_start_defaults_to_random_order(self):
        args = argparse_namespace(
            runners=["3", "4", "8", "10"],
            track_length=24,
            start="-1:3;0:4,8,10",
            initial_order=None,
        )

        config = build_config_from_args(args)

        self.assertEqual(config.initial_order_mode, "random")

    def test_custom_start_does_not_validate_against_default_preset(self):
        args = argparse_namespace(
            preset=4,
            runners=["1", "2", "3", "4", "5", "6"],
            track_length=24,
            start="-3:2;-2:1,4;-1:3,6;0:5",
            initial_order=None,
        )

        config = build_config_from_args(args)

        self.assertEqual(config.runners, (1, 2, 3, 4, 5, 6))
        self.assertEqual(config.start_grid, {-3: (2,), -2: (1, 4), -1: (3, 6), 0: (5,)})
        self.assertEqual(config.initial_order_mode, "random")

    def test_same_position_ranking_uses_cell_order(self):
        grid = {3: (4, 3, 8)}
        progress = {4: 3, 3: 3, 8: 3}

        self.assertEqual(current_rank((3, 4, 8), progress, grid), [4, 3, 8])

    def test_sigrika_marks_two_immediately_higher_ranked_runners(self):
        grid = {2: [16], 3: [13], 4: [15], 5: [14], 31: [-1]}
        progress = {13: 3, 14: 5, 15: 4, 16: 2, -1: 31}

        debuffed = mark_sigrika_debuffs(
            runners=(13, 14, 15, 16),
            progress=progress,
            grid=grid,
        )

        self.assertEqual(debuffed, {14, 15})

    def test_sigrika_does_not_mark_anyone_on_first_round(self):
        grid = {2: [16], 3: [13], 4: [15], 5: [14]}
        progress = {13: 3, 14: 5, 15: 4, 16: 2}

        debuffed = mark_sigrika_debuffs(
            runners=(13, 14, 15, 16),
            progress=progress,
            grid=grid,
            round_number=1,
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

    def test_hiyuki_bonus_depends_on_contact_stacks(self):
        state = RaceSkillState()

        self.assertEqual(check_hiyuki_bonus(state), 0)
        state.hiyuki_bonus_steps = 2
        self.assertEqual(check_hiyuki_bonus(state), 2)

    def test_npc_only_participates_in_ranking_after_action(self):
        grid = {13: [3], 14: [6], 31: [-1]}
        progress = {3: 13, 6: 14, -1: 31}

        self.assertEqual(rank_scope((3, 6), progress, include_npc=False), (3, 6))
        self.assertEqual(current_rank(rank_scope((3, 6), progress, False), progress, grid), [6, 3])
        self.assertEqual(rank_scope((3, 6), progress, include_npc=True), (3, 6, -1))
        self.assertEqual(current_rank(rank_scope((3, 6), progress, True), progress, grid), [-1, 6, 3])

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

    def test_player1_skill_checks_any_runner_left_of_player1(self):
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

        self.assertEqual(grid[5], [1, 3, 2])
        self.assertEqual(rng.random_calls, 1)

    def test_player1_skill_checks_player1_cell_even_when_actor_elsewhere(self):
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

        self.assertEqual(grid[5], [1, 3])
        self.assertEqual(grid[7], [2])
        self.assertEqual(rng.random_calls, 1)

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

        grid[5] = [3, 2, 1]
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

    def test_negative_start_first_reaches_zero_without_winning(self):
        grid = {-3: [3]}
        progress = {3: -3}
        config = RaceConfig(runners=(3,), track_length=24, start_grid={-3: (3,)})

        new_progress = move_single_runner(
            grid=grid,
            progress=progress,
            config=config,
            player=3,
            total_steps=3,
            rng=random.Random(1),
        )

        self.assertEqual(new_progress, 0)
        self.assertEqual(display_position(new_progress, 24), 0)
        self.assertLess(new_progress, 24)
        self.assertEqual(grid[0], [3])

    def test_zero_start_requires_full_lap(self):
        grid = {0: [3]}
        progress = {3: 0}
        config = RaceConfig(runners=(3,), track_length=24, start_grid={0: (3,)})

        new_progress = move_single_runner(
            grid=grid,
            progress=progress,
            config=config,
            player=3,
            total_steps=3,
            rng=random.Random(1),
        )

        self.assertEqual(new_progress, 3)
        self.assertEqual(grid[3], [3])
        self.assertLess(new_progress, 24)

    def test_crossing_zero_finishes_lap_immediately(self):
        grid = {22: [3]}
        progress = {3: 22}
        config = RaceConfig(runners=(3,), track_length=24, start_grid={22: (3,)})

        new_progress = move_single_runner(
            grid=grid,
            progress=progress,
            config=config,
            player=3,
            total_steps=3,
            rng=random.Random(1),
        )

        self.assertEqual(new_progress, 24)
        self.assertEqual(grid[0], [3])
        self.assertNotIn(1, [pos for pos, cell in grid.items() if cell])

    def test_carried_finish_winner_uses_zero_cell_order(self):
        grid = {22: [4, 3], 0: [8]}
        progress = {4: 22, 3: 22, 8: 0}
        config = RaceConfig(runners=(3, 4, 8), track_length=24, start_grid={22: (4, 3), 0: (8,)})

        new_progress = move_runner_with_left_side(
            grid=grid,
            progress=progress,
            config=config,
            player=3,
            idx_in_cell=1,
            total_steps=3,
            rng=random.Random(1),
        )

        self.assertEqual(new_progress, 24)
        self.assertEqual(grid[0], [4, 3, 8])
        self.assertEqual(current_rank((3, 4, 8), progress, grid)[0], 4)

    def test_simulate_race_returns_full_ranking(self):
        config = RaceConfig(
            runners=(3, 4),
            track_length=8,
            start_grid=make_start_grid(8, {0: (3, 4)}),
            name="two_runner",
        )

        result = simulate_race(config, random.Random(3))

        self.assertEqual(set(result.ranking), {3, 4})
        self.assertIn(result.winner, {3, 4})

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


    def test_season_two_default_rules(self):
        args = argparse_namespace(
            season=2,
            preset=4,
            runners=["3", "4", "8", "10"],
            track_length=None,
            start="0:*",
            initial_order=None,
        )

        config = build_config_from_args(args)

        self.assertEqual(config.track_length, 32)
        self.assertTrue(config.npc_enabled)
        self.assertEqual(config.forward_cells, season_rules(2)["forward_cells"])

    def test_season_two_forward_cell_moves_group_one_more(self):
        config = RaceConfig(
            runners=(3,),
            track_length=32,
            start_grid={0: (3,)},
            season=2,
            forward_cells=frozenset({3}),
        )
        grid = {0: [3]}
        progress = {3: 0}

        new_progress = move_single_runner(
            grid=grid,
            progress=progress,
            config=config,
            player=3,
            total_steps=3,
            rng=random.Random(1),
        )

        self.assertEqual(new_progress, 4)
        self.assertEqual(progress[3], 4)
        self.assertEqual(grid[4], [3])

    def test_season_two_backward_cell_moves_group_back_one(self):
        config = RaceConfig(
            runners=(3,),
            track_length=32,
            start_grid={8: (3,)},
            season=2,
            backward_cells=frozenset({10}),
        )
        grid = {8: [3]}
        progress = {3: 8}

        move_single_runner(
            grid=grid,
            progress=progress,
            config=config,
            player=3,
            total_steps=2,
            rng=random.Random(1),
        )

        self.assertEqual(progress[3], 9)
        self.assertEqual(grid[9], [3])

    def test_luuk_herssen_turns_forward_cell_into_four_forward_steps(self):
        config = RaceConfig(
            runners=(14,),
            track_length=32,
            start_grid={0: (14,)},
            season=2,
            forward_cells=frozenset({3}),
        )
        grid = {0: [14]}
        progress = {14: 0}

        new_progress = move_single_runner(
            grid=grid,
            progress=progress,
            config=config,
            player=14,
            total_steps=3,
            rng=random.Random(1),
        )

        self.assertEqual(new_progress, 7)
        self.assertEqual(progress[14], 7)
        self.assertEqual(grid[7], [14])

    def test_luuk_herssen_turns_backward_cell_into_two_backward_steps(self):
        config = RaceConfig(
            runners=(14,),
            track_length=32,
            start_grid={8: (14,)},
            season=2,
            backward_cells=frozenset({10}),
        )
        grid = {8: [14]}
        progress = {14: 8}

        move_single_runner(
            grid=grid,
            progress=progress,
            config=config,
            player=14,
            total_steps=2,
            rng=random.Random(1),
        )

        self.assertEqual(progress[14], 8)
        self.assertEqual(grid[8], [14])

    def test_season_two_shuffle_cell_randomizes_arriving_group(self):
        config = RaceConfig(
            runners=(1, 2, 3, 4),
            track_length=32,
            start_grid={5: (1, 2, 3, 4)},
            season=2,
            shuffle_cells=frozenset({6}),
        )
        grid = {5: [1, 2, 3, 4]}
        progress = {1: 5, 2: 5, 3: 5, 4: 5}

        move_runner_with_left_side(
            grid=grid,
            progress=progress,
            config=config,
            player=4,
            idx_in_cell=3,
            total_steps=1,
            rng=random.Random(1),
        )

        self.assertCountEqual(grid[6], [1, 2, 3, 4])
        self.assertNotEqual(grid[6], [1, 2, 3, 4])

    def test_npc_moves_backward_and_stays_rightmost(self):
        grid = {30: [3]}
        progress = {3: 30}
        config = RaceConfig(runners=(3,), track_length=32, start_grid={30: (3,)})

        npc_progress = move_npc(
            grid=grid,
            progress=progress,
            config=config,
            npc_progress=0,
            rng=random.Random(1),
            trace=False,
        )

        self.assertEqual(npc_progress, 30)
        self.assertEqual(grid[30], [3, -1])
        self.assertEqual(progress[-1], 30)

    def test_npc_triggers_fixed_backward_cell_after_landing(self):
        config = RaceConfig(
            runners=(3,),
            track_length=32,
            start_grid={0: (3,)},
            season=2,
            backward_cells=frozenset({28}),
        )
        grid: dict[int, list[int]] = {}
        progress = {-1: 0}

        npc_progress = move_npc(
            grid=grid,
            progress=progress,
            config=config,
            npc_progress=0,
            rng=FixedDiceRandom(random_value=0.1, dice_value=4),
            trace=False,
        )

        self.assertEqual(npc_progress, 27)
        self.assertEqual(progress[-1], 27)
        self.assertNotIn(28, grid)
        self.assertEqual(grid[27], [-1])

    def test_hiyuki_gains_stack_when_landing_on_npc(self):
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

    def test_hiyuki_gains_stack_when_passing_through_npc(self):
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

    def test_hiyuki_gains_stack_when_npc_lands_on_hiyuki_before_cell_effect(self):
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

    def test_hiyuki_gains_stack_when_npc_passes_through_hiyuki(self):
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
        self.assertEqual(grid[29], [16])
        self.assertEqual(grid[28], [-1])

    def test_npc_stays_rightmost_after_shuffle_cell(self):
        config = RaceConfig(
            runners=(1, 2, 3),
            track_length=32,
            start_grid={5: (1, 2, 3), 6: (-1,)},
            season=2,
            shuffle_cells=frozenset({6}),
        )
        grid = {5: [1, 2, 3], 6: [-1]}
        progress = {1: 5, 2: 5, 3: 5}

        move_runner_with_left_side(
            grid=grid,
            progress=progress,
            config=config,
            player=3,
            idx_in_cell=2,
            total_steps=1,
            rng=random.Random(1),
        )

        self.assertEqual(grid[6][-1], -1)
        self.assertCountEqual(grid[6], [1, 2, 3, -1])

    def test_shuffle_cell_excludes_npc_from_shuffle_pool(self):
        config = RaceConfig(
            runners=(1, 2, 3),
            track_length=32,
            start_grid={5: (1, 2, 3), 6: (-1,)},
            season=2,
            shuffle_cells=frozenset({6}),
        )
        grid = {5: [1, 2, 3], 6: [-1]}
        progress = {1: 5, 2: 5, 3: 5, -1: 6}
        rng = RecordingShuffleRandom()

        move_runner_with_left_side(
            grid=grid,
            progress=progress,
            config=config,
            player=3,
            idx_in_cell=2,
            total_steps=1,
            rng=rng,
        )

        self.assertEqual(rng.shuffle_inputs, [[1, 2, 3]])
        self.assertEqual(grid[6], [3, 2, 1, -1])

    def test_npc_returns_to_start_unless_with_last_runner(self):
        grid = {5: [3], 12: [4], 30: [-1]}
        progress = {3: 5, 4: 12}

        npc_progress = settle_npc_end_of_round(
            grid=grid,
            progress=progress,
            runners=(3, 4),
            npc_progress=-2,
            track_length=32,
            trace=False,
        )

        self.assertEqual(npc_progress, 0)
        self.assertEqual(grid[0], [-1])
        self.assertNotIn(-1, grid.get(30, []))

    def test_trace_log_writes_one_race_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_path = Path(tmp_dir) / "trace.log"

            exit_code = main(
                [
                    "--season",
                    "2",
                    "--trace-log",
                    str(log_path),
                    "--start",
                    "-3:2;-2:1,4;-1:3,6;0:5",
                    "--runners",
                    "1",
                    "2",
                    "3",
                    "4",
                    "5",
                    "6",
                    "--seed",
                    "42",
                ]
            )

            text = log_path.read_text(encoding="utf-8")
            self.assertEqual(exit_code, 0)
            self.assertIn("NPC行动：", text)
            self.assertIn("后退步数：", text)
            self.assertIn("=== 结果 ===", text)
            self.assertIn("长离", text)
            self.assertIn("本轮开始时位置分布：", text)
            self.assertIn("\n--- ", text)
            self.assertIn("行动后位置分布：", text)
            self.assertIn("【判定时机：行动结束】", text)
            self.assertIn("今汐检查自己所在格左侧", text)
            self.assertIn("【判定时机：回合结束】", text)
            self.assertIn("长离检查", text)
            self.assertIn("NPC参与排名：否", text)
            self.assertIn("NPC参与排名：是", text)

            round_three_start = text.index("=== 第3轮 ===")
            first_npc_action = text.index("NPC行动：", round_three_start)
            round_three_intro = text[round_three_start:first_npc_action]
            self.assertIn("第0格（左→右）：[NPC]", round_three_intro)

            lines = round_three_intro.splitlines()
            order_index = next(i for i, line in enumerate(lines) if line.startswith("本轮行动顺序："))
            order_text = lines[order_index + 1].strip()
            self.assertIn("NPC", order_text)
            self.assertEqual(order_text.count("->") + 1, 7)


if __name__ == "__main__":
    unittest.main()
