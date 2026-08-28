import json
import unittest
from pathlib import Path

from src.parser import FtlParser
from src.pyodide_api import (
    PYODIDE_API_SCHEMA,
    handle_request_json,
)


class InMemoryParserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.path = Path("inputs/ponte_3.ftl")
        cls.raw = cls.path.read_bytes()
        cls.text = cls.raw.decode("latin-1")

    def test_text_and_bytes_match_file_parser(self) -> None:
        expected = FtlParser(self.path).parse().to_dict()

        self.assertEqual(FtlParser.from_text(self.text).parse().to_dict(), expected)
        self.assertEqual(FtlParser.from_bytes(self.raw).parse().to_dict(), expected)


class PyodideApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ftl_text = Path("inputs/ponte_3.ftl").read_bytes().decode("latin-1")

    def call(self, operation: str, **options):
        response_json = handle_request_json(
            json.dumps(
                {
                    "operation": operation,
                    "name": "ponte_3",
                    "ftl_text": self.ftl_text,
                    "options": options,
                },
                ensure_ascii=False,
            )
        )
        return json.loads(response_json)

    def test_parse_returns_json_native_model(self) -> None:
        response = self.call("parse")

        self.assertTrue(response["ok"])
        self.assertEqual(response["schema"], PYODIDE_API_SCHEMA)
        self.assertEqual(response["operation"], "parse")
        self.assertEqual(response["result"]["summary"]["node_count"], 10)
        self.assertEqual(response["result"]["summary"]["member_count"], 19)
        self.assertEqual(len(response["result"]["model"]["members"]), 19)

    def test_axial_analysis_can_include_samples(self) -> None:
        response = self.call("analyze_axial", include_samples=True)
        analysis = response["result"]["analysis"]

        self.assertTrue(response["ok"])
        self.assertEqual(analysis["units"]["force"], "N")
        self.assertEqual(len(analysis["members"]), 19)
        self.assertTrue(
            all("samples" in member["axial_force"] for member in analysis["members"])
        )

    def test_stick_sizing_returns_analysis_and_counts(self) -> None:
        response = self.call("size_sticks")
        result = response["result"]

        self.assertTrue(response["ok"])
        self.assertEqual(result["stick_counts"]["total_required_layers"], 144)
        self.assertEqual(result["stick_counts"]["total_physical_sticks"], 408)
        self.assertEqual(len(result["analysis"]["members"]), 19)

    def test_invalid_request_returns_structured_error(self) -> None:
        response = json.loads(
            handle_request_json(json.dumps({"operation": "unknown", "ftl_text": "x"}))
        )

        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "invalid_request")

    def test_invalid_json_returns_structured_error(self) -> None:
        response = json.loads(handle_request_json("{invalid"))

        self.assertFalse(response["ok"])
        self.assertIsNone(response["operation"])
        self.assertEqual(response["error"]["code"], "invalid_json")


if __name__ == "__main__":
    unittest.main()
