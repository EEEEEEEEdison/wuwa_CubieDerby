"""Match types and RaceConfig building tests.

Split from the original monolithic tests/test_cubie_derby.py to
make selective runs and code review tractable. The shared
imports and helpers (fake RNGs, argparse_namespace fixture, etc.)
live in tests/_shared.py.
"""
from __future__ import annotations

import unittest

from tests._shared import *  # noqa: F401,F403  (test fixtures)


class MatchTypesAndConfigTests(unittest.TestCase):
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
        self.assertEqual(config.map_label, "小组赛阶段地图")
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


if __name__ == "__main__":
    unittest.main()
