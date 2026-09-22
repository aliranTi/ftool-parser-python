import unittest

import matplotlib
matplotlib.use("Agg")
import numpy as np
from matplotlib import pyplot as plt

from src.converter_anastruct import to_anastruct
from src.parser import FtlParser
from src.visualizer import plot_displacements


class DisplacementVisualizationTest(unittest.TestCase):
    def test_visual_scale_preserves_solution_and_fits_both_curves(self):
        analysis = to_anastruct(FtlParser("inputs/ponte_3.ftl").parse(), solve=True)
        before = analysis.system.get_node_displacements()
        small = plot_displacements(analysis, show=False, deformation_ratio=0.04)
        large = plot_displacements(analysis, show=False, deformation_ratio=0.08)
        self.addCleanup(plt.close, small)
        self.addCleanup(plt.close, large)
        self.assertEqual(before, analysis.system.get_node_displacements())
        axis = large.axes[0]
        self.assertEqual(axis.get_aspect(), 1.0)
        originals = axis.lines[::2]
        self.assertAlmostEqual(min(min(line.get_xdata()) for line in originals), 0)
        self.assertAlmostEqual(min(min(line.get_ydata()) for line in originals), 0)
        for i in range(0, len(axis.lines), 2):
            base = np.array(axis.lines[i].get_data())
            delta_small = np.array(small.axes[0].lines[i + 1].get_data()) - base
            delta_large = np.array(axis.lines[i + 1].get_data()) - base
            np.testing.assert_allclose(delta_large, delta_small * 2, atol=1e-10)
        for line in axis.lines:
            self.assertGreaterEqual(min(line.get_xdata()), axis.get_xlim()[0])
            self.assertLessEqual(max(line.get_xdata()), axis.get_xlim()[1])
            self.assertGreaterEqual(min(line.get_ydata()), axis.get_ylim()[0])
            self.assertLessEqual(max(line.get_ydata()), axis.get_ylim()[1])

    def test_zero_load_has_no_artificial_deformation(self):
        # Exercise an exact zero-displacement result without invoking the
        # solver, which rejects structures without any applied forces.
        from types import SimpleNamespace
        node = SimpleNamespace(ux=0.0, uy=0.0)
        element = SimpleNamespace(
            type="truss", node_1=node, node_2=node,
            vertex_1=SimpleNamespace(x=5.0, y=2.0),
            vertex_2=SimpleNamespace(x=6.0, y=2.0),
        )
        analysis = SimpleNamespace(solved=True, system=SimpleNamespace(element_map={1: element}))
        figure = plot_displacements(analysis, show=False)
        self.addCleanup(plt.close, figure)
        for original, deformed in zip(figure.axes[0].lines[::2], figure.axes[0].lines[1::2]):
            np.testing.assert_allclose(original.get_data(), deformed.get_data())


if __name__ == "__main__":
    unittest.main()
