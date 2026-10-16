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
    def test_member_sizing_keeps_three_layers_for_construction(self):
        from src.models import FtoolModel, Material, Member, Node, PointLoad, Section, Support
        from src.converter_anastruct import to_anastruct
        from src.stick_sizing import size_axial_members

        for force in (0.0, 1.0, -1.0):
            with self.subTest(force=force):
                model = FtoolModel(
                    materials=[Material('wood', 13e9, 0.3, 0, 0)],
                    sections=[Section('stick', 1.66452e-5, 1e-10,
                                      width=0.00858, thickness=0.00194)],
                    nodes=[Node(1, 0, 0, Support(1, 1, 1)),
                           Node(2, 0.1, 0, load=PointLoad('load', force, 1 if force == 0 else 0, 0))],
                    members=[Member(1, 0, 0, 0.1, 0, 'wood', 'stick', 1, 2)],
                )
                report = size_axial_members(model, to_anastruct(model, solve=True))
                self.assertEqual(report.members[0].required_layers, 3)
                self.assertEqual(report.total_physical_sticks, 3)

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
