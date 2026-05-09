import random
import unittest

from cubie_derby import (
    RaceConfig,
    build_config_from_args,
    current_rank,
    empty_grid,
    make_start_grid,
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

    def test_same_position_ranking_uses_cell_order(self):
        grid = list(empty_grid(5))
        grid[3] = (4, 3, 8)
        positions = {4: 3, 3: 3, 8: 3}

        self.assertEqual(current_rank((3, 4, 8), positions, grid), [4, 3, 8])

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
