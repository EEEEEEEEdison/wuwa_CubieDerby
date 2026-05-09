import random
import tempfile
import unittest
from pathlib import Path

from cubie_derby import (
    RaceConfig,
    build_config_from_args,
    current_rank,
    display_position,
    main,
    make_start_grid,
    maybe_trigger_player1_skill_after_action,
    initial_player_order,
    move_npc,
    move_runner_with_left_side,
    move_single_runner,
    normalize_cli_args,
    parse_start_layout,
    parse_start_spec,
    preset_config,
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

    def test_player1_skill_uses_actor_position_not_any_left_runner(self):
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

        npc_progress = move_npc(
            grid=grid,
            npc_progress=0,
            track_length=32,
            rng=random.Random(1),
            trace=False,
        )

        self.assertEqual(npc_progress, 30)
        self.assertEqual(grid[30], [3, -1])

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
            self.assertIn("npc moves backward", text)
            self.assertIn("=== result ===", text)


if __name__ == "__main__":
    unittest.main()
