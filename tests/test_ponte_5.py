import unittest

from src.parser import FtlParser
from src.converter_anastruct import to_anastruct
from src.stick_sizing import size_axial_members


class Ponte5Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = FtlParser('inputs/ponte_5.ftl').parse()
        cls.analysis = to_anastruct(cls.model, solve=True)
        cls.report = size_axial_members(cls.model, cls.analysis)

    def test_geometry_and_connectivity(self):
        model = self.model
        height = max(n.y for n in model.nodes) - min(n.y for n in model.nodes)
        span = max(n.x for n in model.nodes) - min(n.x for n in model.nodes)
        self.assertGreaterEqual(height, .25)
        self.assertLessEqual(height, .40)
        self.assertGreater(span, 1.05)
        self.assertLess(span, 1.1)
        self.assertEqual((len(model.nodes), len(model.members)), (13, 23))
        reference = FtlParser('inputs/ponte_4.ftl').parse()
        self.assertEqual(
            [(b.id, b.start_node_id, b.end_node_id, b.hinge_start, b.hinge_end) for b in model.members],
            [(b.id, b.start_node_id, b.end_node_id, b.hinge_start, b.hinge_end) for b in reference.members],
        )

    def test_material_and_section_match_ponte_3(self):
        reference = FtlParser('inputs/ponte_3.ftl').parse()
        self.assertEqual(self.model.materials, reference.materials)
        self.assertEqual(self.model.sections[0], next(s for s in reference.sections if s.name == 'palito'))

    def test_load_and_equilibrium(self):
        model, analysis = self.model, self.analysis
        self.assertEqual(sum(n.load.fy for n in model.nodes if n.load), -2000)
        reactions = [(n, analysis.get_reaction_results(n.id)) for n in model.nodes if not n.support.is_free]
        for axis, load_attr in [('Fx', 'fx'), ('Fy', 'fy')]:
            residual = sum(r[axis] for _, r in reactions)
            residual += sum(getattr(n.load, load_attr) for n in model.nodes if n.load)
            self.assertAlmostEqual(residual, 0, delta=1e-6)
        moment = sum(n.x * r['Fy'] - n.y * r['Fx'] + r['Tz'] for n, r in reactions)
        moment += sum(n.x * n.load.fy - n.y * n.load.fx + n.load.moment for n in model.nodes if n.load)
        self.assertAlmostEqual(moment, 0, delta=1e-6)

    def test_all_members_pass_current_sizing_rules(self):
        self.assertEqual(self.report.total_physical_sticks, 418)
        self.assertEqual(self.report.total_required_layers, 155)
        for member in self.report.members:
            self.assertGreaterEqual(member.required_layers, 3)
            for check in (member.compression_check, member.tension_check):
                if check:
                    self.assertTrue(check.passes, member.ftool_id)
            if member.compression_check:
                self.assertLessEqual(member.compression_check.slenderness_x, 140)
                self.assertLessEqual(member.compression_check.slenderness_y, 140)
