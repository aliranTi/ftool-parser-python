import unittest

from src.parser import FtlParser
from src.converter_anastruct import to_anastruct
from src.stick_sizing import size_axial_members


class OptimizedPonte5Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = FtlParser('inputs/ponte_5.ftl').parse()
        cls.model = FtlParser('inputs/otimizadas/ponte_5_otimizada.ftl').parse()
        cls.analysis = to_anastruct(cls.model, solve=True)
        cls.report = size_axial_members(cls.model, cls.analysis)

    def test_preserves_material_load_supports_and_connectivity(self):
        self.assertEqual(self.model.materials, self.base.materials)
        self.assertEqual(self.model.sections, self.base.sections)
        self.assertEqual(self.model.point_loads, self.base.point_loads)
        self.assertEqual([(n.x, n.support, n.load) for n in self.model.nodes],
                         [(n.x, n.support, n.load) for n in self.base.nodes])
        def edges(model):
            return {b.id: (frozenset((b.start_node_id, b.end_node_id)),
                           b.hinge_start, b.hinge_end) for b in model.members}
        self.assertEqual(edges(self.model), edges(self.base))
        self.assertEqual(sum(n.load.fy for n in self.model.nodes if n.load), -2000)
        span = max(n.x for n in self.model.nodes) - min(n.x for n in self.model.nodes)
        height = max(n.y for n in self.model.nodes) - min(n.y for n in self.model.nodes)
        self.assertGreater(span, 1.05)
        self.assertLess(span, 1.1)
        self.assertGreaterEqual(height, .25)
        self.assertLessEqual(height, .40)

    def test_equilibrium_in_forces_and_moments(self):
        fx = fy = moment = 0.0
        for node in self.model.nodes:
            if not node.support.is_free:
                reaction = self.analysis.get_reaction_results(node.id)
                fx += reaction['Fx']
                fy += reaction['Fy']
                moment += node.x * reaction['Fy'] - node.y * reaction['Fx'] + reaction['Tz']
            if node.load:
                fx += node.load.fx
                fy += node.load.fy
                moment += node.x * node.load.fy - node.y * node.load.fx + node.load.moment
        for residual in (fx, fy, moment):
            self.assertAlmostEqual(residual, 0, delta=1e-6)

    def test_below_600_sticks_with_all_existing_checks(self):
        self.assertEqual(self.report.total_physical_sticks, 240)
        self.assertEqual(self.report.total_required_layers, 112)
        self.assertLess(2 * self.report.total_physical_sticks, 600)
        for member in self.report.members:
            self.assertGreaterEqual(member.required_layers, 3)
            for check in (member.compression_check, member.tension_check):
                if check:
                    self.assertTrue(check.passes, member.ftool_id)
            if member.compression_check:
                self.assertLessEqual(member.compression_check.slenderness_x, 140)
                self.assertLessEqual(member.compression_check.slenderness_y, 140)
