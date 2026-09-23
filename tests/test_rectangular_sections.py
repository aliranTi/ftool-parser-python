import unittest
from pathlib import Path

from src.parser import FtlParser
from src.converter_anastruct import to_anastruct
from src.models import FtoolModel, Material, Member, Node, PointLoad, Section, Support
from src.stick_sizing import (
    StickSizingConfig, check_compression_section, size_axial_members,
)


class RectangularSectionsTest(unittest.TestCase):
    def test_rectangle_properties_in_si(self):
        model = FtlParser('inputs/ponte_4.ftl').parse()
        section = model.sections[0]
        self.assertAlmostEqual(section.area, 1.66452e-5, delta=1e-15)
        self.assertAlmostEqual(section.inertia, 1.0211330844e-10, delta=1e-20)
        self.assertEqual((section.width, section.thickness), (0.00194, 0.00858))
        self.assertEqual(section.height, 0.00858)

    def test_generic_section_preserves_explicit_properties(self):
        text = Path('inputs/ponte_4.ftl').read_text(encoding='latin-1')
        text = text.replace("'palito' 1 0\n 0.00194 0.00858",
                            "'palito' 0 0\n 0.002 0.000003")
        section = FtlParser.from_text(text).parse().sections[0]
        self.assertEqual((section.area, section.inertia), (0.002, 0.000003))
        self.assertEqual((section.width, section.thickness), (0, 0))

    def test_small_positive_inertia_retains_bending(self):
        # Cantilever: tip displacement = P L^3 / (3 EI).
        model = FtoolModel(
            materials=[Material('wood', 13e9, 0.3, 0, 0)],
            sections=[Section('thin', 1e-5, 5e-13)],
            nodes=[Node(1, 0, 0, Support(1, 1, 1)),
                   Node(2, 0.1, 0, load=PointLoad('tip', 0, -0.01, 0))],
            members=[Member(1, 0, 0, 0.1, 0, 'wood', 'thin', 1, 2)],
        )
        analysis = to_anastruct(model, solve=True)
        self.assertEqual(analysis.system.element_map[1].type, 'general')
        self.assertAlmostEqual(abs(analysis.get_node_results(2)['uy']),
                               0.01 * 0.1**3 / (3 * 13e9 * 5e-13), delta=1e-10)

    def test_legacy_incomplete_section_uses_valid_equivalent(self):
        model = FtlParser('inputs/ponte_2.ftl').parse()
        self.assertEqual(model.sections[0].area, 0)
        analysis = to_anastruct(model, solve=True)
        expected_ea = 7.35e9 * 0.00784 * 0.00185
        for element in analysis.system.element_map.values():
            self.assertAlmostEqual(element.EA, expected_ea)

    def test_ponte_4_equilibrium_and_axial_forces(self):
        model = FtlParser('inputs/ponte_4.ftl').parse()
        analysis = to_anastruct(model, solve=True)
        report = size_axial_members(model, analysis)
        for axis, load_attr in [('Fx', 'fx'), ('Fy', 'fy')]:
            reactions = sum(analysis.get_reaction_results(n.id)[axis]
                            for n in model.nodes if not n.support.is_free)
            applied = sum(getattr(n.load, load_attr) for n in model.nodes if n.load)
            self.assertAlmostEqual(reactions + applied, 0, delta=1e-6)
        # Central top chord: moment 700 * 1.08 / 4, divided by height 0.24.
        self.assertAlmostEqual(min(b.axial_min_n for b in report.members),
                               -700 * 1.08 / (4 * 0.24), delta=1e-3)
        self.assertEqual(report.total_physical_sticks, 114)
        self.assertEqual(report.total_required_layers, 38)
        self.assertTrue(all(b.check.passes for b in report.members if b.check))

    def test_layers_follow_wide_faces_in_both_section_orientations(self):
        model = FtlParser('inputs/ponte_4.ftl').parse()
        analysis = to_anastruct(model, solve=True)
        before = size_axial_members(model, analysis)
        section = model.sections[0]
        section.width, section.thickness = section.thickness, section.width
        after = size_axial_members(model, analysis)
        self.assertEqual(before.counts_to_dict(), after.counts_to_dict())
        for member in before.members:
            self.assertAlmostEqual(member.section_width_mm, 8.58)
            self.assertAlmostEqual(member.section_thickness_mm, 1.94)

    def test_four_layers_do_not_pass_central_chord_at_700_n(self):
        model = FtlParser('inputs/ponte_4.ftl').parse()
        analysis = to_anastruct(model, solve=True)
        report = size_axial_members(model, analysis)
        central = next(b for b in report.members if b.ftool_id == 17)
        self.assertEqual(central.required_layers, 6)
        check = check_compression_section(
            central.compression_demand_n, central.member_length_m, 4,
            StickSizingConfig(),
        )
        self.assertAlmostEqual(check.area_mm2, 8.58 * 4 * 1.94)
        self.assertFalse(check.passes)
        self.assertGreater(check.governing_utilization, 1.7)
