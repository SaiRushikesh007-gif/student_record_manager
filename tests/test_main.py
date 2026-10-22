"""Test suite for Student Record Manager. Run: python -m unittest -v"""

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import main  # noqa: E402


class BaseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "students.json"
        patcher = mock.patch.object(main, "DATA_FILE", self.path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_fn(self, fn, inputs, *args):
        out = io.StringIO()
        with mock.patch("builtins.input", side_effect=list(inputs)), redirect_stdout(out):
            fn(*args)
        return out.getvalue()

    def write_raw(self, text):
        self.path.write_text(text, encoding="utf-8")

    def disk(self):
        return json.loads(self.path.read_text(encoding="utf-8"))


class TestMarksValidation(unittest.TestCase):
    def test_boundaries(self):
        for v in (0, 100, 0.0, 99.99, 40):
            self.assertTrue(main.is_valid_marks(v))
        for v in (-0.01, 100.01, -1, 101):
            self.assertFalse(main.is_valid_marks(v))

    def test_hard_cases(self):
        for v in (float("nan"), float("inf"), float("-inf"), True, False, None, "50", [50]):
            self.assertFalse(main.is_valid_marks(v), repr(v))

    def test_parse_marks(self):
        self.assertEqual(main.parse_marks(" 82.5 "), 82.5)
        self.assertEqual(main.parse_marks("1e1"), 10.0)
        for bad in ("abc", "", "nan", "inf", "-inf", "101", "-5", "7 5", "75,5"):
            self.assertIsNone(main.parse_marks(bad), bad)


class TestInputHelpers(BaseTest):
    def test_get_valid_marks_retries(self):
        with mock.patch("builtins.input", side_effect=["abc", "nan", "inf", "150", "-1", "", "88"]), \
                redirect_stdout(io.StringIO()):
            self.assertEqual(main.get_valid_marks(), 88.0)

    def test_nonempty_text_retries_and_strips(self):
        with mock.patch("builtins.input", side_effect=["", "   ", "  Bob  "]), redirect_stdout(io.StringIO()):
            self.assertEqual(main.get_nonempty_text("x"), "Bob")

    def test_max_length(self):
        with mock.patch("builtins.input", side_effect=["a" * 40, "ok"]), redirect_stdout(io.StringIO()):
            self.assertEqual(main.get_nonempty_text("x", 32), "ok")

    def test_yes_no(self):
        with mock.patch("builtins.input", side_effect=["maybe", "", "Y"]), redirect_stdout(io.StringIO()):
            self.assertTrue(main.get_yes_no("?"))
        with mock.patch("builtins.input", side_effect=["NO"]), redirect_stdout(io.StringIO()):
            self.assertFalse(main.get_yes_no("?"))


class TestFind(unittest.TestCase):
    def test_case_and_whitespace_and_unicode(self):
        s = [{"student_id": "ABC1", "name": "A", "marks": 1.0},
             {"student_id": "Straße", "name": "B", "marks": 2.0}]
        self.assertEqual(main.find_student_index(s, "abc1"), 0)
        self.assertEqual(main.find_student_index(s, "  ABC1 "), 0)
        self.assertEqual(main.find_student_index(s, "STRASSE"), 1)
        self.assertEqual(main.find_student_index(s, "zzz"), -1)
        self.assertEqual(main.find_student_index([], "a"), -1)


class TestStorage(BaseTest):
    def test_missing_file(self):
        self.assertEqual(main.load_students(), [])

    def test_roundtrip_unicode(self):
        data = [{"student_id": "1", "name": "Søren 李雷 😀", "marks": 55.5}]
        self.assertTrue(main.save_students(data))
        self.assertEqual(main.load_students(), data)

    def test_corrupt_json(self):
        self.write_raw("{not json")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main.load_students(), [])

    def test_empty_file(self):
        self.write_raw("")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main.load_students(), [])

    def test_wrong_top_level_type(self):
        self.write_raw('{"a": 1}')
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main.load_students(), [])

    def test_invalid_bytes(self):
        self.path.write_bytes(b"\xff\xfe\x00bad")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main.load_students(), [])

    def test_bad_records_skipped_not_crash(self):
        raw = json.dumps([
            {"student_id": "1", "name": "Good", "marks": 50},
            {"student_id": "2", "name": "NoMarks"},
            {"name": "NoId", "marks": 10},
            {"student_id": "3", "name": "Bad", "marks": 500},
            {"student_id": "4", "name": "Str", "marks": "70"},
            {"student_id": "5", "name": "Bool", "marks": True},
            {"student_id": 6, "name": "IntId", "marks": 10},
            {"student_id": "  ", "name": "Blank", "marks": 10},
            "junk", None, 42, [],
        ])
        self.write_raw(raw)
        out = io.StringIO()
        with redirect_stdout(out):
            result = main.load_students()
        self.assertEqual([s["student_id"] for s in result], ["1"])
        self.assertIsInstance(result[0]["marks"], float)
        self.assertIn("skipped", out.getvalue())

    def test_nan_in_file_rejected(self):
        self.write_raw('[{"student_id":"1","name":"N","marks":NaN}]')
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main.load_students(), [])

    def test_duplicate_ids_in_file(self):
        self.write_raw(json.dumps([
            {"student_id": "A1", "name": "First", "marks": 10},
            {"student_id": "a1", "name": "Second", "marks": 20},
        ]))
        with redirect_stdout(io.StringIO()):
            result = main.load_students()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "First")

    def test_save_failure_returns_false_and_keeps_old_file(self):
        original = [{"student_id": "1", "name": "Keep", "marks": 1.0}]
        main.save_students(original)
        with mock.patch("main.os.replace", side_effect=OSError("boom")), redirect_stdout(io.StringIO()):
            self.assertFalse(main.save_students([]))
        self.assertEqual(self.disk(), original)
        self.assertEqual([p for p in os.listdir(self.tmp.name) if p.endswith(".tmp")], [])

    def test_unwritable_directory(self):
        with mock.patch.object(main, "DATA_FILE", Path(self.tmp.name) / "nope" / "s.json"), \
                redirect_stdout(io.StringIO()):
            self.assertFalse(main.save_students([]))


class TestAdd(BaseTest):
    def test_add_and_persist(self):
        students = []
        out = self.run_fn(main.add_student, ["S1", "Alice", "90"], students)
        self.assertIn("added successfully", out)
        self.assertEqual(students, [{"student_id": "S1", "name": "Alice", "marks": 90.0}])
        self.assertEqual(self.disk(), students)

    def test_duplicate_id_case_insensitive_reprompts(self):
        students = [{"student_id": "S1", "name": "A", "marks": 1.0}]
        out = self.run_fn(main.add_student, ["s1", " S1 ", "S2", "Bob", "70"], students)
        self.assertIn("already exists", out)
        self.assertEqual([s["student_id"] for s in students], ["S1", "S2"])

    def test_invalid_then_valid_marks_and_boundaries(self):
        students = []
        self.run_fn(main.add_student, ["a", "A", "-1", "101", "x", "0"], students)
        self.run_fn(main.add_student, ["b", "B", "100"], students)
        self.assertEqual([s["marks"] for s in students], [0.0, 100.0])

    def test_save_failure_rolls_back(self):
        students = []
        with mock.patch("main.save_students", return_value=False):
            out = self.run_fn(main.add_student, ["S1", "A", "50"], students)
        self.assertEqual(students, [])
        self.assertIn("not added", out)

    def test_whitespace_trimmed(self):
        students = []
        self.run_fn(main.add_student, ["  S1  ", "  Al  Bo  ", " 50 "], students)
        self.assertEqual(students[0]["student_id"], "S1")
        self.assertEqual(students[0]["name"], "Al  Bo")


class TestViewSearch(BaseTest):
    def test_view_empty(self):
        self.assertIn("No student records", self.run_fn(main.view_students, [], []))

    def test_view_long_values_do_not_break_layout(self):
        s = [{"student_id": "X" * 32, "name": "N" * 100, "marks": 99.999}]
        out = self.run_fn(main.view_students, [], s)
        row = out.strip().splitlines()[-1]
        self.assertEqual(len(row), 54)
        self.assertIn("100.00", row)

    def test_search_found_and_not_found(self):
        s = [{"student_id": "A1", "name": "Ann", "marks": 66.666}]
        out = self.run_fn(main.search_student, ["a1"], s)
        self.assertIn("Ann", out)
        self.assertIn("66.67", out)
        self.assertIn("not found", self.run_fn(main.search_student, ["zz"], s))
        self.assertIn("not found", self.run_fn(main.search_student, ["zz"], []))


class TestUpdate(BaseTest):
    def make(self):
        s = [{"student_id": "A1", "name": "Ann", "marks": 50.0}]
        main.save_students(s)
        return s

    def test_update_name_only(self):
        s = self.make()
        self.run_fn(main.update_student, ["a1", "Anna", "n"], s)
        self.assertEqual(s[0]["name"], "Anna")
        self.assertEqual(s[0]["marks"], 50.0)
        self.assertEqual(self.disk(), s)

    def test_update_marks_only_with_retry(self):
        s = self.make()
        self.run_fn(main.update_student, ["A1", "", "y", "abc", "200", "75.5"], s)
        self.assertEqual(s[0], {"student_id": "A1", "name": "Ann", "marks": 75.5})

    def test_update_both(self):
        s = self.make()
        self.run_fn(main.update_student, ["A1", "Zed", "Y", "0"], s)
        self.assertEqual(s[0], {"student_id": "A1", "name": "Zed", "marks": 0.0})

    def test_invalid_yes_no_reprompts_instead_of_aborting(self):
        s = self.make()
        out = self.run_fn(main.update_student, ["A1", "", "maybe", "n"], s)
        self.assertIn("Please enter y or n", out)
        self.assertIn("No changes", out)

    def test_no_change_does_not_save(self):
        s = self.make()
        with mock.patch("main.save_students") as sv:
            self.run_fn(main.update_student, ["A1", "", "n"], s)
        sv.assert_not_called()

    def test_not_found(self):
        self.assertIn("not found", self.run_fn(main.update_student, ["q"], []))

    def test_save_failure_restores(self):
        s = self.make()
        with mock.patch("main.save_students", return_value=False):
            self.run_fn(main.update_student, ["A1", "Changed", "y", "99"], s)
        self.assertEqual(s[0], {"student_id": "A1", "name": "Ann", "marks": 50.0})


class TestDelete(BaseTest):
    def make(self):
        s = [{"student_id": "A1", "name": "Ann", "marks": 50.0},
             {"student_id": "B2", "name": "Bob", "marks": 60.0},
             {"student_id": "C3", "name": "Cy", "marks": 70.0}]
        main.save_students(s)
        return s

    def test_delete_confirmed_middle(self):
        s = self.make()
        self.run_fn(main.delete_student, ["b2", "y"], s)
        self.assertEqual([x["student_id"] for x in s], ["A1", "C3"])
        self.assertEqual(len(self.disk()), 2)

    def test_delete_cancelled(self):
        s = self.make()
        out = self.run_fn(main.delete_student, ["B2", "n"], s)
        self.assertIn("cancelled", out)
        self.assertEqual(len(s), 3)

    def test_ambiguous_confirm_reprompts(self):
        s = self.make()
        self.run_fn(main.delete_student, ["B2", "", "ok", "y"], s)
        self.assertEqual(len(s), 2)

    def test_not_found(self):
        s = self.make()
        self.assertIn("not found", self.run_fn(main.delete_student, ["zz"], s))
        self.assertEqual(len(s), 3)

    def test_save_failure_restores_at_same_position(self):
        s = self.make()
        with mock.patch("main.save_students", return_value=False):
            self.run_fn(main.delete_student, ["B2", "y"], s)
        self.assertEqual([x["student_id"] for x in s], ["A1", "B2", "C3"])


class TestStatistics(BaseTest):
    def test_empty(self):
        self.assertIsNone(main.calculate_statistics([]))
        self.assertIn("No records", self.run_fn(main.show_statistics, [], []))

    def test_values(self):
        s = [{"student_id": str(i), "name": f"N{i}", "marks": m}
             for i, m in enumerate([39.99, 40.0, 100.0, 0.0])]
        st = main.calculate_statistics(s)
        self.assertEqual(st["count"], 4)
        self.assertAlmostEqual(st["average"], (39.99 + 40 + 100 + 0) / 4)
        self.assertEqual(st["highest"]["marks"], 100.0)
        self.assertEqual(st["lowest"]["marks"], 0.0)
        self.assertEqual(st["passed"], 2)   # 40 passes, 39.99 does not
        self.assertEqual(st["failed"], 2)

    def test_single_student_and_output(self):
        s = [{"student_id": "1", "name": "Solo", "marks": 40.0}]
        out = self.run_fn(main.show_statistics, [], s)
        self.assertIn("40.00 (Solo)", out)
        self.assertIn("Passed (40+):       1", out)

    def test_ties_do_not_crash(self):
        s = [{"student_id": "1", "name": "A", "marks": 50.0},
             {"student_id": "2", "name": "B", "marks": 50.0}]
        self.assertEqual(main.calculate_statistics(s)["average"], 50.0)

    def test_large_class(self):
        s = [{"student_id": str(i), "name": "n", "marks": float(i % 101)} for i in range(5000)]
        self.assertEqual(main.calculate_statistics(s)["count"], 5000)


class TestMainLoop(BaseTest):
    def run_main(self, inputs):
        out = io.StringIO()
        with mock.patch("builtins.input", side_effect=list(inputs)), redirect_stdout(out):
            main.main()
        return out.getvalue()

    def test_exit(self):
        self.assertIn("Goodbye", self.run_main(["7"]))

    def test_invalid_options(self):
        out = self.run_main(["", "abc", "0", "8", "1.0", "7"])
        self.assertEqual(out.count("Invalid option"), 5)

    def test_eof_exits_cleanly(self):
        out = io.StringIO()
        with mock.patch("builtins.input", side_effect=EOFError), redirect_stdout(out):
            main.main()
        self.assertIn("Exiting", out.getvalue())

    def test_ctrl_c_exits_cleanly(self):
        out = io.StringIO()
        with mock.patch("builtins.input", side_effect=KeyboardInterrupt), redirect_stdout(out):
            main.main()
        self.assertIn("Exiting", out.getvalue())

    def test_full_workflow_persists_across_restart(self):
        self.run_main(["1", "S1", "Ann", "35", "1", "S2", "Bob", "80",
                       "4", "s1", "Anna", "y", "45", "6", "5", "S2", "y", "7"])
        self.assertEqual(self.disk(), [{"student_id": "S1", "name": "Anna", "marks": 45.0}])
        out = self.run_main(["2", "3", "s1", "7"])
        self.assertIn("Anna", out)

    def test_runs_as_script(self):
        import subprocess
        r = subprocess.run([sys.executable, str(Path(main.__file__))],
                           input="7\n", capture_output=True, text=True, timeout=20)
        self.assertEqual(r.returncode, 0)
        self.assertIn("Goodbye", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
