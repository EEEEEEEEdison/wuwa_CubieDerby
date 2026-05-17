"""Pinned (a.k.a. golden-sample) regression tests for Monte Carlo output.

These tests lock the *exact* statistical output of the simulator for
specific (seed, config) combinations. They guarantee that any future
refactor cannot silently drift win-rates / qualify-rates / champion-rates,
which is the single biggest hidden-failure mode in a Monte Carlo project:
unit tests can pass while distributions shift by 1-2 percent.

If a change deliberately alters statistical behaviour, the new expected
values must be recomputed AND clearly justified in the commit message.

Captured on commit 8b29ffc (review/opus-cleanup) on 2026-05-17.
"""
from __future__ import annotations

import types
import unittest

from cubie_derby import (
    RaceConfig,
    SEASON2_GROUP_BACKWARD_CELLS,
    SEASON2_GROUP_FORWARD_CELLS,
    SEASON2_GROUP_SHUFFLE_CELLS,
    SEASON2_LAP_LENGTH,
    run_champion_prediction_monte_carlo,
    run_monte_carlo,
    run_season_roster_scan,
)


def _argparse_namespace(**kwargs: object) -> object:
    defaults = {
        "season": 1,
        "match_type": None,
        "champion_prediction": None,
        "champion_analysis": "fast",
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
        "tournament_context_in": None,
        "tournament_context_out": None,
        "qualify_cutoff": 4,
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


class MonteCarloPinnedRegressionTests(unittest.TestCase):
    """Each test pins the exact output of one simulator pathway."""

    def assertRowFloat(self, actual: float, expected: float) -> None:
        # Place delta a hair below the captured precision (1e-10) so that
        # genuinely identical results pass while real drift fails loudly.
        self.assertAlmostEqual(actual, expected, places=10)

    # ---- single-stage Monte Carlo, Season 1 ------------------------------

    def test_single_stage_season1_2000_races_seed42(self):
        runners = (1, 2, 3, 4, 5, 6)
        config = RaceConfig(
            runners=runners,
            track_length=24,
            start_grid={1: runners},
            season=1,
            random_start_stack=True,
            random_start_position=1,
            initial_order_mode="random",
        )
        summary = run_monte_carlo(config, iterations=2000, seed=42, workers=1)

        self.assertEqual(summary.iterations, 2000)
        rows = {row.runner: row for row in summary.rows}

        expected = {
            1: dict(wins=269, qualify_count=1130, win_rate=0.1345,
                    qualify_rate=0.5650, average_rank=3.8700,
                    rank_variance=3.1086543272),
            2: dict(wins=267, qualify_count=1185, win_rate=0.1335,
                    qualify_rate=0.5925, average_rank=3.7900,
                    rank_variance=3.1114557279),
            3: dict(wins=246, qualify_count=1417, win_rate=0.1230,
                    qualify_rate=0.7085, average_rank=3.4635,
                    rank_variance=2.1627491246),
            4: dict(wins=315, qualify_count=1447, win_rate=0.1575,
                    qualify_rate=0.7235, average_rank=3.3160,
                    rank_variance=2.6504692346),
            5: dict(wins=537, qualify_count=1421, win_rate=0.2685,
                    qualify_rate=0.7105, average_rank=3.2010,
                    rank_variance=3.2232106053),
            6: dict(wins=366, qualify_count=1400, win_rate=0.1830,
                    qualify_rate=0.7000, average_rank=3.3595,
                    rank_variance=2.8867031016),
        }

        for runner_id, exp in expected.items():
            row = rows[runner_id]
            with self.subTest(runner=runner_id):
                self.assertEqual(row.wins, exp["wins"])
                self.assertEqual(row.qualify_count, exp["qualify_count"])
                self.assertRowFloat(row.win_rate, exp["win_rate"])
                self.assertRowFloat(row.qualify_rate, exp["qualify_rate"])
                self.assertRowFloat(row.average_rank, exp["average_rank"])
                self.assertRowFloat(row.rank_variance, exp["rank_variance"])

        # Statistical invariants (cheap & catch a different class of bug).
        self.assertEqual(sum(row.wins for row in summary.rows), 2000)
        self.assertAlmostEqual(
            sum(row.win_rate for row in summary.rows), 1.0, places=10
        )

    # ---- single-stage Monte Carlo, Season 2 group map --------------------

    def test_single_stage_season2_group_2000_races_seed42(self):
        runners = (11, 12, 13, 14, 15, 16)
        config = RaceConfig(
            runners=runners,
            track_length=SEASON2_LAP_LENGTH,
            start_grid={1: runners},
            season=2,
            forward_cells=SEASON2_GROUP_FORWARD_CELLS,
            backward_cells=SEASON2_GROUP_BACKWARD_CELLS,
            shuffle_cells=SEASON2_GROUP_SHUFFLE_CELLS,
            npc_enabled=True,
            random_start_stack=True,
            random_start_position=1,
            initial_order_mode="random",
        )
        summary = run_monte_carlo(config, iterations=2000, seed=42, workers=1)

        self.assertEqual(summary.iterations, 2000)
        rows = {row.runner: row for row in summary.rows}

        expected = {
            11: dict(wins=279, qualify_count=1317, win_rate=0.1395,
                     qualify_rate=0.6585, average_rank=3.5900,
                     rank_variance=2.6902451226),
            12: dict(wins=302, qualify_count=1395, win_rate=0.1510,
                     qualify_rate=0.6975, average_rank=3.4100,
                     rank_variance=2.6722361181),
            13: dict(wins=328, qualify_count=1254, win_rate=0.1640,
                     qualify_rate=0.6270, average_rank=3.6300,
                     rank_variance=2.9705852926),
            14: dict(wins=302, qualify_count=1253, win_rate=0.1510,
                     qualify_rate=0.6265, average_rank=3.6855,
                     rank_variance=3.0711253127),
            15: dict(wins=428, qualify_count=1502, win_rate=0.2140,
                     qualify_rate=0.7510, average_rank=3.1555,
                     rank_variance=2.7196795898),
            16: dict(wins=361, qualify_count=1279, win_rate=0.1805,
                     qualify_rate=0.6395, average_rank=3.5290,
                     rank_variance=3.1977578789),
        }

        for runner_id, exp in expected.items():
            row = rows[runner_id]
            with self.subTest(runner=runner_id):
                self.assertEqual(row.wins, exp["wins"])
                self.assertEqual(row.qualify_count, exp["qualify_count"])
                self.assertRowFloat(row.win_rate, exp["win_rate"])
                self.assertRowFloat(row.qualify_rate, exp["qualify_rate"])
                self.assertRowFloat(row.average_rank, exp["average_rank"])
                self.assertRowFloat(row.rank_variance, exp["rank_variance"])

        self.assertEqual(sum(row.wins for row in summary.rows), 2000)
        self.assertAlmostEqual(
            sum(row.win_rate for row in summary.rows), 1.0, places=10
        )

    # ---- whole-tournament champion prediction ----------------------------

    def test_champion_prediction_season2_fast_300_seed42(self):
        summary = run_champion_prediction_monte_carlo(
            season=2, iterations=300, seed=42, workers=1, analysis_depth="fast"
        )

        self.assertEqual(summary.iterations, 300)
        rows = {row.runner: row for row in summary.rows}

        expected = {
            1:  (16, 0.05333333333333334),
            2:  (14, 0.04666666666666667),
            3:  (16, 0.05333333333333334),
            4:  (18, 0.06),
            6:  (17, 0.05666666666666667),
            11: (12, 0.04),
            12: (24, 0.08),
            13: (4,  0.013333333333333334),
            14: (7,  0.023333333333333334),
            15: (21, 0.07),
            16: (11, 0.03666666666666667),
            17: (35, 0.11666666666666667),
            18: (9,  0.03),
            19: (37, 0.12333333333333334),
            20: (36, 0.12),
            21: (7,  0.023333333333333334),
            22: (4,  0.013333333333333334),
            23: (12, 0.04),
        }

        for runner_id, (champ_count, champ_rate) in expected.items():
            row = rows[runner_id]
            with self.subTest(runner=runner_id):
                self.assertEqual(row.championships, champ_count)
                self.assertRowFloat(row.champion_rate, champ_rate)

        self.assertEqual(sum(row.championships for row in summary.rows), 300)
        self.assertAlmostEqual(
            sum(row.champion_rate for row in summary.rows), 1.0, places=10
        )

    # ---- season-roster scan ---------------------------------------------

    def test_season1_roster_scan_field2_iterations10_seed42(self):
        args = _argparse_namespace(
            season=1,
            start="1:*",
            field_size=2,
            iterations=10,
            seed=42,
            workers=1,
        )
        summary = run_season_roster_scan(args)

        self.assertEqual(summary.combination_count, 66)
        self.assertEqual(summary.total_simulated_races, 660)

        rows = {row.runner: row for row in summary.rows}
        expected_wins = {
            1: 42, 2: 29, 3: 72, 4: 54, 5: 48, 6: 58,
            7: 78, 8: 75, 9: 26, 10: 40, 11: 71, 12: 67,
        }
        for runner_id, exp_wins in expected_wins.items():
            row = rows[runner_id]
            with self.subTest(runner=runner_id):
                self.assertEqual(row.combination_count, 11)
                self.assertEqual(row.race_count, 110)
                self.assertEqual(row.wins, exp_wins)

        # 660 races × 2 runners per race = 1320 row participation events.
        self.assertEqual(
            sum(row.race_count for row in summary.rows),
            summary.total_simulated_races * 2,
        )
        # Every race has exactly one winner.
        self.assertEqual(
            sum(row.wins for row in summary.rows),
            summary.total_simulated_races,
        )


if __name__ == "__main__":
    unittest.main()
