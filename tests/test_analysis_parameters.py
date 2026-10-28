import json
import subprocess
import sys
import unittest
from pathlib import Path

from src.analysis_parameters import apply_parameters, parameter_fields
from src.parser import FtlParser
from src.pyodide_api import handle_request, size_ftl_sticks


class AnalysisParametersTest(unittest.TestCase):
    def setUp(self):
        self.text = Path('inputs/ponte_3.ftl').read_text(encoding='latin-1')
        self.model = FtlParser.from_text(self.text).parse()

    def test_parse_keeps_scientific_imports_lazy(self):
        code = """
import sys
from src.pyodide_api import handle_request
from pathlib import Path
r = handle_request({'operation': 'parse', 'ftl_text': Path('inputs/ponte_3.ftl').read_text(encoding='latin-1')})
assert r['ok'] and r['result']['parameters']
assert not any(x in sys.modules for x in ('numpy', 'anastruct', 'matplotlib'))
"""
        subprocess.run([sys.executable, '-c', code], check=True)

    def test_dimensions_recompute_properties_and_area_override_wins(self):
        apply_parameters(self.model, {'sections.1.width_mm': 10, 'sections.1.thickness_mm': 2})
        section = self.model.sections[1]
        self.assertAlmostEqual(section.area, 20e-6)
        self.assertAlmostEqual(section.inertia, 0.01 * 0.002**3 / 12)
        apply_parameters(self.model, {'sections.1.width_mm': 12, 'sections.1.area_mm2': 30})
        self.assertAlmostEqual(section.area, 30e-6)
        self.assertAlmostEqual(section.width, .012)
        self.assertEqual(FtlParser.from_text(self.text).parse().sections[1].width, .00784)

    def test_overrides_reach_sizing_and_report(self):
        baseline = size_ftl_sticks(self.text)
        response = handle_request({'operation': 'render_report', 'ftl_text': self.text,
                                   'options': {'parameters': {'minimum_member_layers': 4,
                                                             'wood.kmod1': 1.2}}})
        self.assertTrue(response['ok'], response)
        result = response['result']
        self.assertTrue(all(b['required_layers'] >= 4 for b in result['stick_counts']['members']))
        fields = {f['key']: f['value'] for f in result['parameters']}
        self.assertEqual(fields['wood.kmod1'], 1.2)
        self.assertNotEqual(result['stick_counts']['total_physical_sticks'],
                            baseline['stick_counts']['total_physical_sticks'])

    def test_invalid_values_rejected_by_boundary(self):
        for overrides in ({'wood.kmod1': -1}, {'wood.kmod1': True},
                          {'wood.kmod1': float('nan')}, {'sections.999.area_mm2': 1},
                          {'minimum_member_layers': 3.5}, {'minimum_member_layers': 1001},
                          {'splice_overlap_mm': 115}, {'sections.0.width_mm': 9}):
            with self.subTest(overrides=overrides):
                response = handle_request({'operation': 'size_sticks', 'ftl_text': self.text,
                                           'options': {'parameters': overrides}})
                self.assertFalse(response['ok'])
                self.assertEqual(response['error']['code'], 'invalid_request')

    def test_empty_overrides_preserve_defaults(self):
        self.assertEqual(size_ftl_sticks(self.text), size_ftl_sticks(self.text, parameters={}))
        json.dumps(parameter_fields(self.model), allow_nan=False)

    def test_elasticity_override_changes_displacement(self):
        from src.converter_anastruct import to_anastruct
        before = to_anastruct(self.model, solve=True)
        loaded = next(n for n in self.model.nodes if n.load)
        displacement = before.get_node_results(loaded.id)['uy']
        apply_parameters(self.model, {'materials.0.elasticity_mpa': 14700})
        after = to_anastruct(self.model, solve=True)
        self.assertAlmostEqual(after.get_node_results(loaded.id)['uy'], displacement / 2,
                               delta=abs(displacement) * 1e-6)
