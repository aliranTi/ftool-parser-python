import unittest
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt

from src.converter_anastruct import to_anastruct
from src.parser import FtlParser
from src.visualizer import plot_axial_forces


class AxialForceVisualizationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.model = FtlParser(Path("inputs/ponte_3.ftl")).parse()
        cls.analysis = to_anastruct(cls.model, solve=True)

    def test_shows_only_member_axial_forces(self) -> None:
        figure = plot_axial_forces(
            self.model,
            self.analysis,
            show=False,
            force_unit="kN",
            length_unit="cm",
            decimals=3,
        )
        self.addCleanup(plt.close, figure)
        axis = figure.axes[0]
        member_labels = [
            text.get_text()
            for text in axis.texts
            if text.get_text().startswith("m")
        ]

        self.assertEqual(len(axis.lines), len(self.model.members))
        self.assertEqual(len(member_labels), len(self.model.members))
        self.assertTrue(all(" kN" in label for label in member_labels))
        self.assertEqual(
            {label.splitlines()[0] for label in member_labels},
            {f"m{member.id}" for member in self.model.members},
        )
        self.assertTrue(any("\n+" in label for label in member_labels))
        self.assertTrue(any("\n-" in label for label in member_labels))
        self.assertEqual(axis.get_xlabel(), "Comprimento (cm)")
        self.assertEqual(axis.get_ylabel(), "Altura (cm)")
        self.assertEqual(len(axis.patches), 0)

    def test_requires_a_solved_analysis(self) -> None:
        unsolved = to_anastruct(self.model)

        with self.assertRaisesRegex(RuntimeError, "analysis.solve"):
            plot_axial_forces(self.model, unsolved, show=False)


if __name__ == "__main__":
    unittest.main()
