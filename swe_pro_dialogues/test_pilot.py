import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from pilot import HERE, merge_additions, prepare_stages, read
from pro_rows import requirement_items
from verify_pilot import read_lines, verify


class ProPilotTests(unittest.TestCase):
    def test_source_formatting_does_not_create_extra_requirements(self):
        text = "Required scope first.\n\n- A multiline example\n-------------\n  - a nested item\n\n-Another rule"
        self.assertEqual(requirement_items(text), {
            "r1": "Required scope first.", "r2": "A multiline example\n-------------\n  - a nested item",
            "r3": "Another rule"})

    def test_temporary_requirement_must_be_retired_in_a_revision(self):
        plan = read(HERE / "plans.json")[0]
        row = {"requirements": "- native exception\n- no YAML\n- other inputs unchanged"}
        self.assertEqual(prepare_stages(row, plan)[0][-1]["retired_ids"], ["t1"])
        for field, value in (("retire", []), ("type", "addition"), ("bullets", [2])):
            invalid = deepcopy(plan)
            invalid["stages"][-1][field] = value
            with self.assertRaises(ValueError):
                prepare_stages(row, invalid)

    def test_only_adjacent_compatible_updates_can_be_combined(self):
        records = read_lines(HERE / "pilot_v1/candidates.jsonl")
        mixed = next(r for r in records if r["trajectory_type"] == "mixed")
        with self.assertRaises(ValueError):
            merge_additions(mixed, [1, 2])

    def test_four_message_record_counts_as_the_same_original(self):
        self.assertEqual(verify(HERE / "pilot_v1")["originals"], 5)
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for path in (HERE / "pilot_v1").iterdir():
                (folder / path.name).write_bytes(path.read_bytes())
            with (folder / "length_comparison.jsonl").open("a") as stream:
                stream.write("\n")
            with self.assertRaisesRegex(ValueError, "Length comparison differs"):
                verify(folder)


if __name__ == "__main__":
    unittest.main()
