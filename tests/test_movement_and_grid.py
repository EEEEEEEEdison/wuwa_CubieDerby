"""Movement, grid, ranking, finish line tests.

Split from the original monolithic tests/test_cubie_derby.py to
make selective runs and code review tractable. The shared
imports and helpers (fake RNGs, argparse_namespace fixture, etc.)
live in tests/_shared.py.
"""
from __future__ import annotations

import unittest

from tests._shared import *  # noqa: F401,F403  (test fixtures)


class MovementAndGridTests(unittest.TestCase):
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

    def test_same_position_ranking_uses_cell_order(self):
        grid = {3: (4, 3, 8)}
        progress = {4: 3, 3: 3, 8: 3}

        self.assertEqual(current_rank((3, 4, 8), progress, grid), [4, 3, 8])

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

    def test_round_dice_are_rolled_for_every_round_participant_including_npc(self):
        config = RaceConfig(runners=(17,), track_length=32, start_grid={0: (17,)}, season=2, npc_enabled=True)
        state = RaceSkillState()

        dice = roll_round_dice((17, -1), QueuedRandom([2, 1]), config=config, skill_state=state)

        self.assertEqual(dice, {17: 2, -1: 1})
        self.assertEqual(check_chisa_skill(state, dice[17], dice), 0)


if __name__ == "__main__":
    unittest.main()
