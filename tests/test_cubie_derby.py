import random
import unittest

from cubie_derby import (
    RaceConfig,
    build_config_from_args,
    current_rank,
    display_position,
    make_start_grid,
    move_runner_with_left_side,
    move_single_runner,
    normalize_cli_args,
    parse_start_layout,
    parse_start_spec,
    preset_config,
    run_monte_carlo,
    simulate_race,
)


def argparse_namespace(**kwargs):
    defaults = {
        "preset": 4,
        "runners": None,
        "track_length": None,
        "start": None,
        "initial_order": None,
    }
    defaults.update(kwargs)
    return type("Args", (), defaults)()


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

    def test_same_position_ranking_uses_cell_order(self):
        grid = {3: (4, 3, 8)}
        progress = {4: 3, 3: 3, 8: 3}

        self.assertEqual(current_rank((3, 4, 8), progress, grid), [4, 3, 8])

    def test_negative_start_first_reaches_zero_without_winning(self):
        grid = {-3: [3]}
        progress = {3: -3}

        new_progress = move_single_runner(
            grid=grid,
            progress=progress,
            player=3,
            total_steps=3,
            track_length=24,
            rng=random.Random(1),
        )

        self.assertEqual(new_progress, 0)
        self.assertEqual(display_position(new_progress, 24), 0)
        self.assertLess(new_progress, 24)
        self.assertEqual(grid[0], [3])

    def test_zero_start_requires_full_lap(self):
        grid = {0: [3]}
        progress = {3: 0}

        new_progress = move_single_runner(
            grid=grid,
            progress=progress,
            player=3,
            total_steps=3,
            track_length=24,
            rng=random.Random(1),
        )

        self.assertEqual(new_progress, 3)
        self.assertEqual(grid[3], [3])
        self.assertLess(new_progress, 24)

    def test_crossing_zero_finishes_lap_immediately(self):
        grid = {22: [3]}
        progress = {3: 22}

        new_progress = move_single_runner(
            grid=grid,
            progress=progress,
            player=3,
            total_steps=3,
            track_length=24,
            rng=random.Random(1),
        )

        self.assertEqual(new_progress, 24)
        self.assertEqual(grid[0], [3])
        self.assertNotIn(1, [pos for pos, cell in grid.items() if cell])

    def test_carried_finish_winner_uses_zero_cell_order(self):
        grid = {22: [4, 3], 0: [8]}
        progress = {4: 22, 3: 22, 8: 0}

        new_progress = move_runner_with_left_side(
            grid=grid,
            progress=progress,
            player=3,
            idx_in_cell=1,
            total_steps=3,
            track_length=24,
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


if __name__ == "__main__":
    unittest.main()
