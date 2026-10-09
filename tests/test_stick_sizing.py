import math
import unittest

from src.stick_sizing import (
    StickGeometry,
    StickSizingConfig,
    StickSizingError,
    check_compression_section,
    required_layers_for_compression,
)


class CompressionSlendernessTests(unittest.TestCase):
    def test_rejects_excess_slenderness_even_when_strength_passes(self):
        for width, thickness, failing_axes in (
            (12.0, 2.0, (True, False)),
            (2.0, 12.0, (False, True)),
            (2.0, 2.0, (True, True)),
        ):
            with self.subTest(width=width, thickness=thickness):
                config = StickSizingConfig(
                    stick=StickGeometry(width_mm=width, thickness_mm=thickness)
                )
                check = check_compression_section(0.01, 0.1, 1, config)
                self.assertLess(check.governing_utilization, 1.0)
                self.assertEqual(
                    (check.slenderness_x > 140, check.slenderness_y > 140),
                    failing_axes,
                )
                self.assertFalse(check.passes)

    def test_slenderness_limit_is_inclusive(self):
        config = StickSizingConfig(
            stick=StickGeometry(width_mm=12.0, thickness_mm=12.0)
        )
        for slenderness in (139.999, 140.0, 140.001):
            with self.subTest(slenderness=slenderness):
                length = slenderness * math.sqrt(12.0) / 1000.0
                check = check_compression_section(0.01, length, 1, config)
                self.assertAlmostEqual(check.slenderness_x, slenderness)
                self.assertAlmostEqual(check.slenderness_y, slenderness)
                self.assertEqual(check.passes, slenderness <= 140.0)

    def test_search_adds_layers_to_satisfy_slenderness(self):
        check = required_layers_for_compression(0.01, 0.1)
        self.assertEqual(check.layer_count, 2)
        self.assertTrue(check.passes)
        self.assertLessEqual(check.slenderness_x, 140.0)
        self.assertLessEqual(check.slenderness_y, 140.0)

    def test_search_fails_when_fixed_width_exceeds_slenderness_limit(self):
        config = StickSizingConfig(max_layers=10)
        check = check_compression_section(0.01, 0.4, config.max_layers, config)
        self.assertLess(check.governing_utilization, 1.0)
        self.assertLessEqual(check.slenderness_x, 140.0)
        self.assertGreater(check.slenderness_y, 140.0)
        with self.assertRaises(StickSizingError):
            required_layers_for_compression(0.01, 0.4, config)


if __name__ == "__main__":
    unittest.main()
