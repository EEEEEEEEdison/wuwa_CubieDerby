import contextlib
import io
import json
import random
import tempfile
import unittest
from pathlib import Path

from cubie_derby import (
    MonteCarloAccumulator,
    ProgressBar,
    RaceSkillState,
    RaceConfig,
    RaceMovementState,
    TraceLogger,
    apply_lynae_skill,
    apply_sigrika_debuff,
    build_config_from_args,
    check_chisa_skill,
    check_denia_skill,
    check_hiyuki_bonus,
    current_rank,
    display_position,
    display_width,
    format_summary,
    format_season_roster_scan_summary,
    format_tournament_result,
    format_simulation_overview_lines,
    champion_prediction_to_dict,
    format_champion_prediction_summary,
    summary_to_dict,
    main,
    make_start_grid,
    mark_sigrika_debuffs,
    maybe_trigger_aemeath_after_active_move,
    maybe_trigger_luno_after_action,
    maybe_trigger_player1_skill_after_action,
    initial_player_order,
    next_round_action_order,
    move_npc,
    move_group_due_to_cell_effect,
    move_runner_with_left_side,
    move_single_runner,
    normalize_cli_args,
    parallel_task_count,
    parse_runner,
    parse_runner_tokens,
    parse_start_layout,
    parse_start_spec,
    rank_scope,
    run_skill_ablation,
    run_monte_carlo,
    run_champion_prediction_monte_carlo,
    run_season_roster_scan,
    simulate_stage,
    simulate_tournament,
    season_rules,
    season_roster_combination_count,
    season_roster_scan_to_dict,
    season_runner_pool,
    settle_npc_end_of_round,
    simulate_race,
    skill_ablation_to_dict,
    split_iterations,
    roll_dice,
    roll_round_dice,
    with_elapsed,
)


def argparse_namespace(**kwargs):
    defaults = {
        "season": 1,
        "match_type": None,
        "champion_prediction": None,
        "runners": None,
        "track_length": None,
        "start": None,
        "initial_order": None,
        "seed": None,
        "iterations": 100,
        "field_size": None,
        "workers": 1,
        "json": False,
        "trace": False,
        "trace_log": None,
        "season_roster_scan": False,
        "skill_ablation": False,
        "skill_ablation_runners": None,
        "skill_ablation_detail": False,
        "qualify_cutoff": 4,
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


class FixedDiceShuffleRandom(FixedDiceRandom):
    def shuffle(self, x) -> None:
        x.reverse()


class QueuedFloatDiceShuffleRandom(random.Random):
    def __init__(self, random_values: list[float], dice_value: int, fallback_random: float = 0.9):
        super().__init__(1)
        self.random_values = list(random_values)
        self.dice_value = dice_value
        self.fallback_random = fallback_random

    def random(self) -> float:
        if not self.random_values:
            return self.fallback_random
        return self.random_values.pop(0)

    def randint(self, a: int, b: int) -> int:
        if not a <= self.dice_value <= b:
            raise ValueError(f"fixed dice {self.dice_value} is outside {a}..{b}")
        return self.dice_value

    def shuffle(self, x) -> None:
        x.reverse()


class QueuedRandom(CountingRandom):
    def __init__(self, randint_values: list[int], random_value: float = 0.9):
        super().__init__(random_value)
        self.randint_values = list(randint_values)

    def randint(self, a: int, b: int) -> int:
        if not self.randint_values:
            raise AssertionError("no queued randint value left")
        value = self.randint_values.pop(0)
        if not a <= value <= b:
            raise ValueError(f"queued dice {value} is outside {a}..{b}")
        return value


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
        self.assertEqual(summary.rows[0].qualify_count, 20)
        self.assertEqual(summary.rows[0].qualify_rate, 1.0)

    def test_winner_lazy_win_rate_counts_carried_steps(self):
        config = RaceConfig(
            runners=(1, 2),
            track_length=3,
            start_grid={0: (1, 2)},
            initial_order_mode="fixed",
            fixed_initial_order=(2, 1),
        )

        result = simulate_race(config, FixedDiceRandom(random_value=0.9, dice_value=3))

        self.assertEqual(result.winner, 1)
        self.assertEqual(result.winner_carried_steps, 3)
        self.assertEqual(result.winner_total_steps, 3)

        accumulator = MonteCarloAccumulator(config.runners)
        accumulator.add(result)
        summary = accumulator.to_summary(config)
        row = next(row for row in summary.rows if row.runner == 1)

        self.assertEqual(row.lazy_win_rate, 1.0)
        self.assertEqual(row.winner_carried_steps, 3)
        self.assertEqual(row.winner_total_steps, 3)
        self.assertIn("躺赢率", format_summary(summary))
        self.assertEqual(summary_to_dict(summary)["rows"][0]["lazy_win_rate"], 1.0)

    def test_lazy_win_movement_ignores_backward_steps(self):
        config = RaceConfig(
            runners=(1, 2),
            track_length=8,
            start_grid={3: (1, 2)},
            backward_cells=frozenset({4}),
        )
        grid = {3: [1, 2]}
        progress = {1: 3, 2: 3}
        movement_state = RaceMovementState()

        move_runner_with_left_side(
            grid=grid,
            progress=progress,
            config=config,
            player=2,
            idx_in_cell=1,
            total_steps=1,
            rng=random.Random(1),
            movement_state=movement_state,
        )

        self.assertEqual(progress[1], 3)
        self.assertEqual(progress[2], 3)
        self.assertEqual(movement_state.total_steps[1], 1)
        self.assertEqual(movement_state.carried_steps[1], 1)
        self.assertEqual(movement_state.total_steps[2], 1)
        self.assertNotIn(2, movement_state.carried_steps)

    def test_custom_config_runs_and_counts_all_races(self):
        config = RaceConfig(
            runners=(3, 4, 8, 10),
            track_length=24,
            start_grid=make_start_grid(24, {1: (10,), 2: (4, 3), 3: (8,)}),
        )

        summary = run_monte_carlo(config, 100, seed=42)

        self.assertEqual(sum(row.wins for row in summary.rows), 100)
        self.assertEqual({row.runner for row in summary.rows}, {3, 4, 8, 10})
        self.assertEqual(sum(row.qualify_count for row in summary.rows), 400)

    def test_qualify_cutoff_controls_top_n_counting(self):
        config = RaceConfig(
            runners=(3, 4, 8, 10),
            track_length=24,
            start_grid=make_start_grid(24, {1: (10,), 2: (4, 3), 3: (8,)}),
            qualify_cutoff=2,
        )

        summary = run_monte_carlo(config, 100, seed=42)

        self.assertEqual(sum(row.qualify_count for row in summary.rows), 200)
        self.assertEqual(summary.config.qualify_cutoff, 2)
        self.assertEqual(summary_to_dict(summary)["config"]["qualify_cutoff"], 2)

    def test_format_summary_uses_chinese_aligned_table(self):
        config = RaceConfig(
            runners=(13, 14, 15, 16),
            track_length=8,
            start_grid=make_start_grid(8, {0: (13, 14, 15, 16)}),
            name="自定义",
        )
        summary = run_monte_carlo(config, 12, seed=3)

        text = format_summary(summary)

        self.assertIn("赛制：自定义", text)
        self.assertIn("角色", text)
        self.assertIn("晋级率", text)
        self.assertIn("晋级统计：前4名", text)
        self.assertIn("用时：未统计", text)
        self.assertIn("速度：未统计", text)
        self.assertIn("推荐选择：", text)
        self.assertNotIn("夺冠次数", text)
        self.assertNotIn("Scenario:", text)
        self.assertNotIn("win_rate", text)

        lines = text.splitlines()
        header_index = next(i for i, line in enumerate(lines) if line.startswith("角色"))
        table_lines = lines[header_index : header_index + 2 + len(config.runners)]
        expected_width = display_width(table_lines[0])
        self.assertTrue(all(display_width(line) == expected_width for line in table_lines))

    def test_format_summary_shows_elapsed_time_when_recorded(self):
        config = RaceConfig(
            runners=(3, 4, 8, 10),
            track_length=24,
            start_grid=make_start_grid(24, {1: (10,), 2: (4, 3), 3: (8,)}),
        )
        summary = with_elapsed(run_monte_carlo(config, 10, seed=1), 0.5)

        text = format_summary(summary)
        data = summary_to_dict(summary)

        self.assertIn("用时：500 ms", text)
        self.assertIn("速度：20 局/秒", text)
        self.assertEqual(data["elapsed_seconds"], 0.5)
        self.assertEqual(data["races_per_second"], 20.0)

    def test_format_summary_uses_custom_config_name(self):
        config = RaceConfig(
            runners=(3, 4, 8, 10),
            track_length=24,
            start_grid=make_start_grid(24, {1: (10,), 2: (4, 3), 3: (8,)}),
            name="自定义",
        )
        summary = run_monte_carlo(config, 10, seed=1)

        text = format_summary(summary)

        self.assertIn("赛制：自定义", text)

    def test_format_summary_includes_custom_start_layout(self):
        config = RaceConfig(
            runners=(3, 4, 8, 10),
            track_length=24,
            start_grid=make_start_grid(24, {1: (10,), 2: (4, 3), 3: (8,)}),
            name="自定义",
        )
        summary = run_monte_carlo(config, 10, seed=1)

        text = format_summary(summary)
        data = summary_to_dict(summary)

        self.assertIn("登场角色：卡卡罗, 守岸人, 布兰特, 赞妮", text)
        self.assertIn("自定义站位：第1格：[赞妮]；第2格：[守岸人, 卡卡罗]；第3格：[布兰特]", text)
        self.assertEqual(data["config"]["start_layout"], "第1格：[赞妮]；第2格：[守岸人, 卡卡罗]；第3格：[布兰特]")
        self.assertEqual(data["config"]["start_grid"], {"1": [10], "2": [4, 3], "3": [8]})

    def test_format_summary_includes_random_stack_start_and_entrants(self):
        config = RaceConfig(
            runners=(11, 12, 13, 14, 15, 16),
            track_length=32,
            start_grid={},
            season=2,
            random_start_stack=True,
            random_start_position=1,
            name="自定义",
        )

        summary = run_monte_carlo(config, 10, seed=1)
        text = format_summary(summary)
        data = summary_to_dict(summary)

        self.assertIn("登场角色：卡提希娅, 菲比, 西格莉卡, 陆赫斯, 达尼娅, 绯雪", text)
        self.assertIn("起跑配置：第1格（全部登场角色同格，每局随机堆叠顺序）", text)
        self.assertEqual(
            data["config"]["start_layout"],
            "第1格（全部登场角色同格，每局随机堆叠顺序）",
        )

    def test_format_simulation_overview_lines_supports_pending_status(self):
        config = RaceConfig(
            runners=(3, 4, 8, 10),
            track_length=24,
            start_grid=make_start_grid(24, {1: (10,), 2: (4, 3), 3: (8,)}),
            season=2,
            name="自定义",
        )

        lines = format_simulation_overview_lines(config, 1_000_000, pending=True)

        self.assertEqual(
            lines,
            [
                "赛制：自定义",
                "赛季：第2季",
                "登场角色：卡卡罗, 守岸人, 布兰特, 赞妮",
                "模拟次数：1,000,000",
                "赛道长度：24格",
                "晋级统计：前4名",
                "用时：进行中",
                "速度：计算中",
                "自定义站位：第1格：[赞妮]；第2格：[守岸人, 卡卡罗]；第3格：[布兰特]",
            ],
        )

    def test_grand_final_summary_hides_qualify_stats(self):
        config = RaceConfig(
            runners=(11, 12, 13, 14, 15, 16),
            track_length=32,
            start_grid={1: (11, 12, 13, 14, 15, 16)},
            qualify_cutoff=1,
            season=2,
            match_type="grand-final",
            show_qualify_stats=False,
            name="总决赛",
        )

        summary = run_monte_carlo(config, 10, seed=1)
        text = format_summary(summary)
        data = summary_to_dict(summary)

        self.assertNotIn("晋级率", text)
        self.assertNotIn("晋级统计", text)
        self.assertFalse(data["config"]["show_qualify_stats"])
        self.assertNotIn("qualify_cutoff", data["config"])
        self.assertNotIn("qualify_rate", data["rows"][0])

    def test_progress_bar_renders_zero_percent_immediately(self):
        stream = io.StringIO()

        progress = ProgressBar(100, "模拟进度", stream=stream)

        output = stream.getvalue()
        self.assertIn("模拟进度", output)
        self.assertIn("0/100", output)
        self.assertIn("0.00%", output)
        progress.close()

    def test_run_monte_carlo_seed_is_worker_independent(self):
        config = RaceConfig(
            runners=(3, 4, 8, 10),
            track_length=24,
            start_grid=make_start_grid(24, {1: (10,), 2: (4, 3), 3: (8,)}),
        )

        single_worker = run_monte_carlo(config, 120, seed=42, workers=1)
        multi_worker = run_monte_carlo(config, 120, seed=42, workers=2)

        self.assertEqual(single_worker.best, multi_worker.best)
        self.assertEqual(single_worker.rows, multi_worker.rows)

    def test_parallel_task_count_uses_more_tasks_than_workers(self):
        self.assertEqual(parallel_task_count(1_000_000, 8), 64)
        self.assertEqual(parallel_task_count(10, 8), 10)
        self.assertEqual(parallel_task_count(100, 1), 8)

    def test_split_iterations_evenly_distributes_chunk_sizes(self):
        chunk_sizes = split_iterations(100, 12)

        self.assertEqual(len(chunk_sizes), 12)
        self.assertEqual(sum(chunk_sizes), 100)
        self.assertLessEqual(max(chunk_sizes) - min(chunk_sizes), 1)
        self.assertTrue(all(size > 0 for size in chunk_sizes))

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

    def test_build_config_requires_custom_start(self):
        args = argparse_namespace(
            runners=["3", "4", "8", "10"],
            track_length=24,
            start=None,
            initial_order=None,
        )

        with self.assertRaisesRegex(ValueError, "--start is required"):
            build_config_from_args(args)

    def test_random_stack_start_requires_selected_runners(self):
        args = argparse_namespace(
            runners=None,
            track_length=24,
            start="0:*",
            initial_order=None,
        )

        with self.assertRaisesRegex(ValueError, "--runners is required"):
            build_config_from_args(args)

    def test_random_stack_at_nonzero_position_defaults_to_left_to_right_order(self):
        args = argparse_namespace(
            season=2,
            runners=["11", "12", "13", "14", "15", "16"],
            track_length=None,
            start="1:*",
            initial_order=None,
        )

        config = build_config_from_args(args)

        self.assertTrue(config.random_start_stack)
        self.assertEqual(config.random_start_position, 1)
        self.assertEqual(config.initial_order_mode, "start")
        self.assertEqual(initial_player_order(config, {1: [14, 12, 13, 15, 11, 16]}, random.Random(1)), [14, 12, 13, 15, 11, 16])

    def test_initial_start_order_ignores_waiting_npc(self):
        config = RaceConfig(runners=(11, 12), track_length=32, start_grid={1: (11, 12)}, initial_order_mode="start")

        self.assertEqual(initial_player_order(config, {0: [-1], 1: [11, 12]}, random.Random(1)), [11, 12])

    def test_parse_new_runner_aliases_and_names(self):
        self.assertEqual(parse_runner("sigrika"), 13)
        self.assertEqual(parse_runner("luuk_herssen"), 14)
        self.assertEqual(parse_runner("Luuk Herssen"), 14)
        self.assertEqual(parse_runner("denia"), 15)
        self.assertEqual(parse_runner("hiyuki"), 16)
        self.assertEqual(parse_runner("chisa"), 17)
        self.assertEqual(parse_runner("mornye"), 18)
        self.assertEqual(parse_runner("lynae"), 19)
        self.assertEqual(parse_runner("aemeath"), 20)
        self.assertEqual(parse_runner("augusta"), 21)
        self.assertEqual(parse_runner("luno"), 22)
        self.assertEqual(parse_runner("phrolova"), 23)
        self.assertEqual(parse_runner("西格莉卡"), 13)
        self.assertEqual(parse_runner("陆赫斯"), 14)
        self.assertEqual(parse_runner("达尼娅"), 15)
        self.assertEqual(parse_runner("绯雪"), 16)
        self.assertEqual(parse_runner("千咲"), 17)
        self.assertEqual(parse_runner("莫宁"), 18)
        self.assertEqual(parse_runner("琳奈"), 19)
        self.assertEqual(parse_runner("爱弥斯"), 20)
        self.assertEqual(parse_runner("奥古斯塔"), 21)
        self.assertEqual(parse_runner("尤诺"), 22)
        self.assertEqual(parse_runner("弗洛洛"), 23)

    def test_parse_random_runners_defaults_to_six_unique_ids(self):
        runners = parse_runner_tokens(["random"], rng=random.Random(42))

        self.assertEqual(len(runners), 6)
        self.assertEqual(len(set(runners)), 6)
        self.assertTrue(all(1 <= runner <= 23 for runner in runners))
        self.assertEqual(runners, parse_runner_tokens(["random"], rng=random.Random(42)))

    def test_parse_random_runners_supports_custom_count(self):
        runners = parse_runner_tokens(["random:4"], rng=random.Random(42))

        self.assertEqual(len(runners), 4)
        self.assertEqual(len(set(runners)), 4)

    def test_parse_random_runners_respects_runner_pool(self):
        runner_pool = season_runner_pool(2)
        runners = parse_runner_tokens(["random"], rng=random.Random(42), runner_pool=runner_pool)

        self.assertEqual(len(runners), 6)
        self.assertTrue(set(runners).issubset(set(runner_pool)))

    def test_parse_random_runners_rejects_count_above_runner_pool(self):
        with self.assertRaisesRegex(ValueError, r"1\.\.12"):
            parse_runner_tokens(["random:13"], rng=random.Random(42), runner_pool=season_runner_pool(1))

    def test_parse_random_runners_cannot_mix_explicit_ids(self):
        with self.assertRaisesRegex(ValueError, "cannot be mixed"):
            parse_runner_tokens(["random", "1"], rng=random.Random(42))

    def test_build_config_random_runners_uses_seed(self):
        args = argparse_namespace(
            season=2,
            runners=["random"],
            track_length=None,
            start="0:*",
            initial_order=None,
            seed=42,
        )

        first = build_config_from_args(args)
        second = build_config_from_args(args)

        self.assertEqual(first.runners, second.runners)
        self.assertEqual(len(first.runners), 6)
        self.assertTrue(set(first.runners).issubset(set(season_runner_pool(2))))
        self.assertEqual(first.track_length, 32)

    def test_match_type_group_round_one_applies_default_start_and_hides_qualify_stats(self):
        args = argparse_namespace(
            season=2,
            match_type="group-round-1",
            runners=["11", "12", "13", "14", "15", "16"],
            start=None,
        )

        config = build_config_from_args(args)

        self.assertEqual(config.match_type, "group-round-1")
        self.assertTrue(config.random_start_stack)
        self.assertEqual(config.random_start_position, 1)
        self.assertEqual(config.qualify_cutoff, 6)
        self.assertFalse(config.show_qualify_stats)
        self.assertEqual(config.name, "小组赛第一轮")

    def test_match_type_group_round_two_builds_seeded_start_from_runner_order(self):
        args = argparse_namespace(
            season=2,
            match_type="group-round-2",
            runners=["11", "12", "13", "14", "15", "16"],
            start=None,
        )

        config = build_config_from_args(args)

        self.assertEqual(config.match_type, "group-round-2")
        self.assertEqual(
            config.start_grid,
            {
                -3: (16,),
                -2: (14, 15),
                -1: (12, 13),
                0: (11,),
            },
        )
        self.assertEqual(config.qualify_cutoff, 4)
        self.assertTrue(config.show_qualify_stats)

    def test_season_runner_pool_matches_expected_rosters(self):
        self.assertEqual(season_runner_pool(1), tuple(range(1, 13)))
        self.assertEqual(season_runner_pool(2), (1, 2, 3, 4, 6, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23))

    def test_season_roster_combination_count_matches_expected_value(self):
        self.assertEqual(season_roster_combination_count(2, 6), 18564)

    def test_season_roster_scan_aggregates_all_combinations(self):
        args = argparse_namespace(
            season=1,
            start="1:*",
            field_size=2,
            iterations=3,
            workers=1,
        )

        summary = run_season_roster_scan(args)
        text = format_season_roster_scan_summary(summary)
        data = season_roster_scan_to_dict(summary)

        self.assertEqual(summary.combination_count, 66)
        self.assertEqual(summary.total_simulated_races, 198)
        self.assertEqual({row.runner for row in summary.rows}, set(range(1, 13)))
        self.assertTrue(all(row.combination_count == 11 for row in summary.rows))
        self.assertEqual(sum(row.wins for row in summary.rows), summary.total_simulated_races)
        self.assertIn("赛季角色池遍历统计：", text)
        self.assertIn("参赛组合", text)
        self.assertIn("综合推荐：", text)
        self.assertEqual(data["combination_count"], 66)
        self.assertEqual(data["total_simulated_races"], 198)
        self.assertEqual(len(data["rows"]), 12)

    def test_season_roster_scan_requires_reusable_star_start(self):
        args = argparse_namespace(
            season=2,
            start="-3:11;-2:16,14;-1:12,13;1:15",
            field_size=6,
        )

        with self.assertRaisesRegex(ValueError, "requires a reusable '\\*' start"):
            run_season_roster_scan(args)

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

    def test_custom_start_infers_or_validates_selected_runners(self):
        args = argparse_namespace(
            runners=["1", "2", "3", "4", "5", "6"],
            track_length=24,
            start="-3:2;-2:1,4;-1:3,6;0:5",
            initial_order=None,
        )

        config = build_config_from_args(args)

        self.assertEqual(config.runners, (1, 2, 3, 4, 5, 6))
        self.assertEqual(config.start_grid, {-3: (2,), -2: (1, 4), -1: (3, 6), 0: (5,)})
        self.assertEqual(config.initial_order_mode, "random")

    def test_simulate_stage_group_round_one_emits_round_two_layout(self):
        stage = simulate_stage(
            season=2,
            match_type="group-round-1",
            runners=(11, 12, 13, 14, 15, 16),
            rng=random.Random(1),
        )

        self.assertEqual(stage.match_type, "group-round-1")
        self.assertEqual(len(stage.ranking), 6)
        self.assertEqual(stage.qualified_runners, stage.ranking)
        self.assertIsNotNone(stage.next_stage_start_spec)
        self.assertIn("0:", stage.next_stage_start_spec)
        self.assertIn("-1:", stage.next_stage_start_spec)

    def test_simulate_tournament_returns_complete_season_two_flow(self):
        result = simulate_tournament(2, random.Random(1))
        text = format_tournament_result(result)

        self.assertEqual(result.season, 2)
        self.assertEqual(len(result.stages), 12)
        self.assertEqual(result.stages[0].title, "小组赛第一轮 A组")
        self.assertEqual(result.stages[-1].title, "总决赛")
        self.assertIn(result.champion, season_runner_pool(2))
        self.assertIn("总决赛", text)
        self.assertIn("冠军", text)

    def test_champion_prediction_monte_carlo_outputs_only_champion_rates(self):
        summary = run_champion_prediction_monte_carlo(2, 8, seed=3, workers=1)
        data = champion_prediction_to_dict(summary)
        text = format_champion_prediction_summary(summary)

        self.assertEqual(summary.iterations, 8)
        self.assertEqual(len(summary.rows), len(season_runner_pool(2)))
        self.assertAlmostEqual(sum(row.championships for row in summary.rows), 8)
        self.assertEqual(data["iterations"], 8)
        self.assertIn("冠军次数", text)
        self.assertIn("夺冠率", text)

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

    def test_finish_line_stops_after_action_skill_checks(self):
        config = RaceConfig(
            runners=(22, 1),
            track_length=32,
            start_grid={31: (22,), 19: (1,)},
            initial_order_mode="fixed",
            fixed_initial_order=(22, 1),
        )
        trace = TraceLogger()

        simulate_race(config, FixedDiceRandom(random_value=0.1, dice_value=1), trace=trace)
        first_action = first_trace_action(trace.text(), "尤诺")

        self.assertIn("到达位置：第0格", first_action)
        self.assertIn("到达或经过终点，立即进行冠军判定", first_action)
        self.assertNotIn("今汐检查行动角色尤诺", first_action)
        self.assertNotIn("尤诺技能触发：", first_action)

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

    def test_luuk_herssen_does_not_enhance_special_cell_when_carried(self):
        config = RaceConfig(
            runners=(12, 14, 16),
            track_length=32,
            start_grid={21: (12, 14, 16)},
            season=2,
            forward_cells=frozenset({23}),
        )
        grid = {21: [12, 14, 16]}
        progress = {12: 21, 14: 21, 16: 21}

        new_progress = move_runner_with_left_side(
            grid=grid,
            progress=progress,
            config=config,
            player=16,
            idx_in_cell=2,
            total_steps=2,
            rng=random.Random(1),
        )

        self.assertEqual(new_progress, 24)
        self.assertEqual(progress[14], 24)
        self.assertEqual(grid[24], [12, 14, 16])
        self.assertNotIn(27, grid)

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

    def test_npc_carries_runners_it_passes_with_remaining_steps(self):
        grid = {0: [-1], 31: [3]}
        progress = {-1: 0, 3: 31}
        config = RaceConfig(runners=(3,), track_length=32, start_grid={31: (3,)})

        npc_progress = move_npc(
            grid=grid,
            progress=progress,
            config=config,
            npc_progress=0,
            rng=FixedDiceRandom(random_value=0.1, dice_value=2),
            trace=False,
        )

        self.assertEqual(npc_progress, 30)
        self.assertEqual(progress[-1], 30)
        self.assertEqual(progress[3], 30)
        self.assertEqual(grid[30], [3, -1])
        self.assertNotIn(31, grid)

    def test_npc_carrying_group_enters_next_cell_from_left(self):
        grid = {
            19: [16, -1],
            18: [15, 13],
            17: [11],
        }
        progress = {-1: 19, 16: 19, 15: 18, 13: 18, 11: 17}
        config = RaceConfig(runners=(11, 13, 15, 16), track_length=32, start_grid={})

        npc_progress = move_npc(
            grid=grid,
            progress=progress,
            config=config,
            npc_progress=19,
            rng=FixedDiceRandom(random_value=0.1, dice_value=3),
            trace=False,
        )

        self.assertEqual(npc_progress, 16)
        self.assertNotIn(19, grid)
        self.assertNotIn(18, grid)
        self.assertNotIn(17, grid)
        self.assertEqual(grid[16], [16, 15, 13, 11, -1])
        self.assertEqual(progress[16], 16)
        self.assertEqual(progress[15], 16)
        self.assertEqual(progress[13], 16)
        self.assertEqual(progress[11], 16)

    def test_npc_does_not_carry_runners_already_stacked_before_first_action_round(self):
        grid = {0: [3, -1], 31: [4]}
        progress = {3: 0, 4: 31, -1: 0}
        config = RaceConfig(runners=(3, 4), track_length=32, start_grid={})

        npc_progress = move_npc(
            grid=grid,
            progress=progress,
            config=config,
            npc_progress=0,
            rng=FixedDiceRandom(random_value=0.1, dice_value=2),
            trace=False,
            ignore_waiting_stack=True,
        )

        self.assertEqual(npc_progress, 30)
        self.assertEqual(progress[-1], 30)
        self.assertEqual(progress[3], 0)
        self.assertEqual(progress[4], 30)
        self.assertEqual(grid[0], [3])
        self.assertEqual(grid[30], [4, -1])

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

    def test_round_dice_are_rolled_for_every_round_participant_including_npc(self):
        config = RaceConfig(runners=(17,), track_length=32, start_grid={0: (17,)}, season=2, npc_enabled=True)
        state = RaceSkillState()

        dice = roll_round_dice((17, -1), QueuedRandom([2, 1]), config=config, skill_state=state)

        self.assertEqual(dice, {17: 2, -1: 1})
        self.assertEqual(check_chisa_skill(state, dice[17], dice), 0)

    def test_core_skill_trace_logger_uses_buffer_instead_of_stdout(self):
        state = RaceSkillState()
        trace = TraceLogger()
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            self.assertEqual(check_hiyuki_bonus(state, trace), 0)

        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("绯雪技能未生效：", trace.text())

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

    def test_npc_stays_when_position_is_not_less_than_last_runner(self):
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

        self.assertEqual(npc_progress, -2)
        self.assertEqual(grid[30], [-1])
        self.assertNotIn(-1, grid.get(0, []))

    def test_npc_returns_to_start_when_position_is_less_than_last_runner(self):
        grid = {21: [-1], 22: [3], 25: [4]}
        progress = {3: 22, 4: 25}

        npc_progress = settle_npc_end_of_round(
            grid=grid,
            progress=progress,
            runners=(3, 4),
            npc_progress=21,
            track_length=32,
            trace=False,
        )

        self.assertEqual(npc_progress, 0)
        self.assertEqual(grid[0], [-1])
        self.assertNotIn(-1, grid.get(21, []))

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
            self.assertIn("今汐检查行动角色", text)
            self.assertIn("行动结算后是否位于自己紧邻左侧", text)
            self.assertIn("【判定时机：回合结束】", text)
            self.assertIn("长离检查", text)
            self.assertIn("NPC参与排名：否", text)
            self.assertIn("NPC参与排名：是", text)

            round_three_start = text.index("=== 第3轮 ===")
            first_npc_action = text.index("NPC行动：", round_three_start)
            round_three_intro = text[round_three_start:first_npc_action]
            self.assertRegex(round_three_intro, r"第0格（左→右）：\[[^\]]*NPC[^\]]*\]")

            lines = round_three_intro.splitlines()
            order_index = next(i for i, line in enumerate(lines) if line.startswith("本轮行动顺序："))
            order_text = lines[order_index + 1].strip()
            self.assertIn("NPC", order_text)
            self.assertEqual(order_text.count("->") + 1, 7)

    def test_main_champion_prediction_random_json(self):
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            exit_code = main(
                [
                    "--season",
                    "2",
                    "--champion-prediction",
                    "random",
                    "--json",
                    "--seed",
                    "7",
                ]
            )

        data = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(data["season"], 2)
        self.assertIn("champion", data)
        self.assertEqual(data["stages"][-1]["match_type"], "grand-final")


if __name__ == "__main__":
    unittest.main()
