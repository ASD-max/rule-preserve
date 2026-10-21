import hashlib
import importlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class RulePreserveBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rule_preserve = importlib.import_module("rule_preserve")

    def setUp(self):
        self._temporary_directory = tempfile.TemporaryDirectory(
            prefix="rule-preserve-tests-"
        )
        self.addCleanup(self._temporary_directory.cleanup)
        self.temp_root = Path(self._temporary_directory.name)
        self._case_number = 0
        self._spec_number = 0

    def make_case(self, source_bytes=b"alpha\nkeep me\nomega\n"):
        self._case_number += 1
        case_root = self.temp_root / f"case-{self._case_number:03d}"
        case_root.mkdir()
        source = case_root / "source.md"
        source.write_bytes(source_bytes)
        candidate = case_root / "candidate"
        candidate.mkdir()
        return source, candidate

    def workspace_path(self, name):
        path = self.temp_root / name
        if path.exists() or path.is_symlink():
            self.fail(f"workspace path already exists: {path}")
        return path

    def make_spec(
        self,
        source,
        core_files=None,
        blocks=None,
        source_sha256=None,
    ):
        return {
            "source_sha256": (
                hashlib.sha256(source.read_bytes()).hexdigest()
                if source_sha256 is None
                else source_sha256
            ),
            "core_files": ["core.md"] if core_files is None else core_files,
            "blocks": (
                [{"id": "exception", "start": 2, "end": 2}]
                if blocks is None
                else blocks
            ),
        }

    def write_core(self, candidate, text):
        path = candidate / "core.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
        return path

    def run_api(self, source, candidate, spec):
        return self.rule_preserve.check(source, candidate, spec)

    def run_cli(self, *arguments, timeout=15):
        return subprocess.run(
            [sys.executable, "-B", "-m", "rule_preserve", *arguments],
            cwd=PROJECT_ROOT,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            check=False,
        )

    def run_cli_check(self, source, candidate, spec):
        self._spec_number += 1
        spec_path = self.workspace_path(
            f"spec-{self._spec_number:03d}.json"
        )
        spec_path.write_text(
            json.dumps(spec, ensure_ascii=False),
            encoding="utf-8",
        )
        return self.run_cli(
            "check", str(source), str(candidate), str(spec_path)
        )

    def run_cli_check_raw_spec(self, source, candidate, spec_bytes):
        self._spec_number += 1
        spec_path = self.workspace_path(
            f"raw-spec-{self._spec_number:03d}.json"
        )
        spec_path.write_bytes(spec_bytes)
        return self.run_cli(
            "check", str(source), str(candidate), str(spec_path)
        )

    def assert_cli_error_shape(self, payload):
        self.assertEqual(payload.get("schema_version"), 1)
        self.assertEqual(payload.get("command"), "check")
        self.assertTrue(payload.get("error"))

    def assert_cli_check_shape(self, payload):
        self.assertEqual(payload.get("schema_version"), 1)
        self.assertEqual(payload.get("command"), "check")
        self.assertIsInstance(payload.get("pass"), bool)
        self.assertTrue(payload.get("blocks"))

    def assert_api_check_shape(self, payload):
        self.assertIsInstance(payload, dict)
        self.assertIsInstance(payload.get("pass"), bool)
        self.assertTrue(payload.get("blocks"))

    def assert_named_block_was_checked(self, payload):
        self.assertIn(
            "exception",
            json.dumps(payload["blocks"], ensure_ascii=False),
        )

    def assert_api_invalid(self, source, candidate, spec):
        with self.assertRaises((ValueError, OSError, UnicodeError)):
            self.run_api(source, candidate, spec)

    def test_complete_preservation_passes_api_and_cli(self):
        source, candidate = self.make_case()
        self.write_core(candidate, "heading\nkeep me\nfooter\n")
        spec = self.make_spec(source)

        result = self.run_api(source, candidate, spec)
        self.assert_api_check_shape(result)
        self.assertTrue(result["pass"])
        self.assert_named_block_was_checked(result)

        process = self.run_cli_check(source, candidate, spec)
        self.assertEqual(process.returncode, 0, process.stderr)
        payload = json.loads(process.stdout)
        self.assert_cli_check_shape(payload)
        self.assertTrue(payload["pass"])

    def test_missing_declared_exception_fails_as_valid_input(self):
        source, candidate = self.make_case()
        self.write_core(candidate, "heading\nreplacement\nfooter\n")
        spec = self.make_spec(source)

        result = self.run_api(source, candidate, spec)
        self.assert_api_check_shape(result)
        self.assertFalse(result["pass"])
        self.assert_named_block_was_checked(result)

        process = self.run_cli_check(source, candidate, spec)
        self.assertEqual(process.returncode, 1, process.stderr)
        payload = json.loads(process.stdout)
        self.assert_cli_check_shape(payload)
        self.assertFalse(payload["pass"])

    def test_duplicate_occurrences_across_files_fail(self):
        source, candidate = self.make_case()
        self.write_core(candidate, "keep me\n")
        nested = candidate / "nested"
        nested.mkdir()
        (nested / "other.txt").write_text("keep me\n", encoding="utf-8")
        spec = self.make_spec(source)

        result = self.run_api(source, candidate, spec)
        self.assert_api_check_shape(result)
        self.assertFalse(result["pass"])

        process = self.run_cli_check(source, candidate, spec)
        self.assertEqual(process.returncode, 1, process.stderr)
        payload = json.loads(process.stdout)
        self.assert_cli_check_shape(payload)
        self.assertFalse(payload["pass"])

    def test_duplicate_occurrences_within_one_file_fail(self):
        source, candidate = self.make_case()
        nested = candidate / "nested"
        nested.mkdir()
        (nested / "core.md").write_text(
            "keep me\nkeep me\n",
            encoding="utf-8",
        )
        spec = self.make_spec(source)
        spec["core_files"] = ["nested/core.md"]

        result = self.run_api(source, candidate, spec)
        self.assert_api_check_shape(result)
        self.assertFalse(result["pass"])

        process = self.run_cli_check(source, candidate, spec)
        self.assertEqual(process.returncode, 1, process.stderr)
        payload = json.loads(process.stdout)
        self.assert_cli_check_shape(payload)
        self.assertFalse(payload["pass"])

    def test_block_found_only_outside_declared_core_fails(self):
        source, candidate = self.make_case()
        self.write_core(candidate, "core has no exception\n")
        (candidate / "notes").mkdir()
        (candidate / "notes" / "extra.md").write_text(
            "keep me\n",
            encoding="utf-8",
        )
        spec = self.make_spec(source)

        result = self.run_api(source, candidate, spec)
        self.assert_api_check_shape(result)
        self.assertFalse(result["pass"])

        process = self.run_cli_check(source, candidate, spec)
        self.assertEqual(process.returncode, 1, process.stderr)
        payload = json.loads(process.stdout)
        self.assert_cli_check_shape(payload)
        self.assertFalse(payload["pass"])

    def test_overlapping_occurrences_count_separately(self):
        source, candidate = self.make_case(b"repeat\nrepeat\nrepeat\n")
        self.write_core(candidate, "repeat\nrepeat\nrepeat\n")
        spec = self.make_spec(
            source,
            blocks=[{"id": "overlap", "start": 1, "end": 2}],
        )

        result = self.run_api(source, candidate, spec)
        self.assert_api_check_shape(result)
        self.assertFalse(result["pass"])

        process = self.run_cli_check(source, candidate, spec)
        self.assertEqual(process.returncode, 1, process.stderr)
        payload = json.loads(process.stdout)
        self.assert_cli_check_shape(payload)
        self.assertFalse(payload["pass"])

    def test_multiline_block_end_is_inclusive_and_exact(self):
        source, candidate = self.make_case(
            b"alpha\nfirst\nsecond\nomega\n"
        )
        self.write_core(candidate, "heading\nfirst\nsecond\nfooter\n")
        spec = self.make_spec(
            source,
            blocks=[{"id": "pair", "start": 2, "end": 3}],
        )

        result = self.run_api(source, candidate, spec)
        self.assert_api_check_shape(result)
        self.assertTrue(result["pass"])

        process = self.run_cli_check(source, candidate, spec)
        self.assertEqual(process.returncode, 0, process.stderr)
        payload = json.loads(process.stdout)
        self.assert_cli_check_shape(payload)
        self.assertTrue(payload["pass"])

        truncated = self.workspace_path("truncated-candidate")
        truncated.mkdir()
        self.write_core(truncated, "heading\nfirst\nfooter\n")
        result = self.run_api(source, truncated, spec)
        self.assert_api_check_shape(result)
        self.assertFalse(result["pass"])

        process = self.run_cli_check(source, truncated, spec)
        self.assertEqual(process.returncode, 1, process.stderr)
        payload = json.loads(process.stdout)
        self.assert_cli_check_shape(payload)
        self.assertFalse(payload["pass"])

    def test_hash_invalidation_fails_closed_without_modifying_source(self):
        source, candidate = self.make_case()
        self.write_core(candidate, "keep me\n")
        original_source = source.read_bytes()
        spec = self.make_spec(source, source_sha256="0" * 64)

        self.assert_api_invalid(source, candidate, spec)
        self.assertEqual(source.read_bytes(), original_source)

        process = self.run_cli_check(source, candidate, spec)
        self.assertEqual(process.returncode, 2, process.stderr)
        self.assert_cli_error_shape(json.loads(process.stdout))
        self.assertEqual(source.read_bytes(), original_source)

    def test_exact_crlf_line_endings_are_preserved(self):
        source, candidate = self.make_case(
            b"alpha\r\nkeep me\r\nomega\r\n"
        )
        self.write_core(candidate, "heading\r\nkeep me\r\nfooter\r\n")
        spec = self.make_spec(source)

        result = self.run_api(source, candidate, spec)
        self.assert_api_check_shape(result)
        self.assertTrue(result["pass"])
        self.assert_named_block_was_checked(result)

        process = self.run_cli_check(source, candidate, spec)
        self.assertEqual(process.returncode, 0, process.stderr)
        payload = json.loads(process.stdout)
        self.assert_cli_check_shape(payload)
        self.assertTrue(payload["pass"])

    def test_utf8_unicode_block_is_preserved_exactly(self):
        source, candidate = self.make_case(
            "alpha\n例外：保留原规则\nomega\n".encode("utf-8")
        )
        self.write_core(
            candidate,
            "heading\n例外：保留原规则\nfooter\n",
        )
        spec = self.make_spec(source)

        result = self.run_api(source, candidate, spec)
        self.assert_api_check_shape(result)
        self.assertTrue(result["pass"])
        self.assert_named_block_was_checked(result)

        process = self.run_cli_check(source, candidate, spec)
        self.assertEqual(process.returncode, 0, process.stderr)
        payload = json.loads(process.stdout)
        self.assert_cli_check_shape(payload)
        self.assertTrue(payload["pass"])

    def test_lf_candidate_does_not_match_crlf_source(self):
        source, candidate = self.make_case(
            b"alpha\r\nkeep me\r\nomega\r\n"
        )
        self.write_core(candidate, "heading\nkeep me\nfooter\n")
        spec = self.make_spec(source)

        result = self.run_api(source, candidate, spec)
        self.assertFalse(result["pass"])

        process = self.run_cli_check(source, candidate, spec)
        self.assertEqual(process.returncode, 1, process.stderr)
        self.assertFalse(json.loads(process.stdout)["pass"])

    def test_missing_final_newline_is_a_byte_difference(self):
        source, candidate = self.make_case(b"keep me\n")
        self.write_core(candidate, "keep me")
        spec = self.make_spec(
            source,
            blocks=[{"id": "line", "start": 1, "end": 1}],
        )

        result = self.run_api(source, candidate, spec)
        self.assertFalse(result["pass"])

        process = self.run_cli_check(source, candidate, spec)
        self.assertEqual(process.returncode, 1, process.stderr)
        self.assertFalse(json.loads(process.stdout)["pass"])

    def test_absent_final_newline_is_matched_exactly(self):
        source, candidate = self.make_case(b"keep me")
        self.write_core(candidate, "keep me")
        spec = self.make_spec(
            source,
            blocks=[{"id": "line", "start": 1, "end": 1}],
        )

        result = self.run_api(source, candidate, spec)
        self.assertTrue(result["pass"])

        process = self.run_cli_check(source, candidate, spec)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertTrue(json.loads(process.stdout)["pass"])

    def test_partial_line_match_is_not_a_whole_line_occurrence(self):
        source, candidate = self.make_case()
        self.write_core(candidate, "prefix keep me suffix\n")
        spec = self.make_spec(source)

        result = self.run_api(source, candidate, spec)
        self.assertFalse(result["pass"])

        process = self.run_cli_check(source, candidate, spec)
        self.assertEqual(process.returncode, 1, process.stderr)
        self.assertFalse(json.loads(process.stdout)["pass"])

    def test_invalid_utf8_in_source_or_candidate_is_rejected(self):
        with self.subTest(component="source"):
            _, candidate = self.make_case()
            case_root = candidate.parent
            source = case_root / "source.md"
            source.write_bytes(b"\xff")
            self.write_core(candidate, "valid\n")
            spec = self.make_spec(
                source,
                blocks=[{"id": "line", "start": 1, "end": 1}],
            )

            self.assert_api_invalid(source, candidate, spec)
            process = self.run_cli_check(source, candidate, spec)
            self.assertEqual(process.returncode, 2, process.stderr)
            self.assert_cli_error_shape(json.loads(process.stdout))

        with self.subTest(component="candidate"):
            source, candidate = self.make_case(b"keep me\n")
            (candidate / "core.md").write_bytes(b"\xff")
            spec = self.make_spec(
                source,
                blocks=[{"id": "line", "start": 1, "end": 1}],
            )

            self.assert_api_invalid(source, candidate, spec)
            process = self.run_cli_check(source, candidate, spec)
            self.assertEqual(process.returncode, 2, process.stderr)
            self.assert_cli_error_shape(json.loads(process.stdout))

    def test_core_paths_cannot_escape_candidate_root(self):
        source, candidate = self.make_case()
        self.write_core(candidate, "keep me\n")
        outside = source.parent / "outside.md"
        outside.write_text("keep me\n", encoding="utf-8")
        bad_paths = [
            "../outside.md",
            "nested/../../outside.md",
            outside.name,
        ]

        for index, bad_path in enumerate(bad_paths, 1):
            with self.subTest(core_path=bad_path):
                candidate = (
                    source.parent / f"escape-candidate-{index}"
                )
                candidate.mkdir()
                self.write_core(candidate, "keep me\n")
                spec = self.make_spec(source, core_files=[bad_path])
                self.assert_api_invalid(source, candidate, spec)

                process = self.run_cli_check(source, candidate, spec)
                self.assertEqual(process.returncode, 2, process.stderr)
                self.assert_cli_error_shape(json.loads(process.stdout))

        with self.subTest(core_path="absolute"):
            candidate = source.parent / "absolute-path-candidate"
            candidate.mkdir()
            core = self.write_core(candidate, "keep me\n")
            spec = self.make_spec(source, core_files=[str(core)])

            self.assert_api_invalid(source, candidate, spec)
            process = self.run_cli_check(source, candidate, spec)
            self.assertEqual(process.returncode, 2, process.stderr)
            self.assert_cli_error_shape(json.loads(process.stdout))

    def test_nested_file_symlink_is_rejected(self):
        source, candidate = self.make_case()
        self.write_core(candidate, "keep me\n")
        target = candidate / "target.md"
        target.write_text("keep me\n", encoding="utf-8")
        try:
            (candidate / "linked.md").symlink_to(target)
        except (NotImplementedError, OSError) as error:
            self.skipTest(f"symlinks are unavailable: {error}")
        spec = self.make_spec(source)

        self.assertTrue((candidate / "linked.md").is_symlink())
        self.assert_api_invalid(source, candidate, spec)
        process = self.run_cli_check(source, candidate, spec)
        self.assertEqual(process.returncode, 2, process.stderr)
        self.assert_cli_error_shape(json.loads(process.stdout))

    def test_nested_directory_symlink_is_rejected(self):
        source, candidate = self.make_case()
        self.write_core(candidate, "keep me\n")
        target_directory = candidate / "target-directory"
        target_directory.mkdir()
        (target_directory / "other.md").write_text(
            "keep me\n",
            encoding="utf-8",
        )
        try:
            (candidate / "linked-directory").symlink_to(
                target_directory,
                target_is_directory=True,
            )
        except (NotImplementedError, OSError) as error:
            self.skipTest(f"symlinks are unavailable: {error}")
        spec = self.make_spec(source)

        self.assertTrue(
            (candidate / "linked-directory").is_symlink()
        )
        self.assert_api_invalid(source, candidate, spec)
        process = self.run_cli_check(source, candidate, spec)
        self.assertEqual(process.returncode, 2, process.stderr)
        self.assert_cli_error_shape(json.loads(process.stdout))

    def test_candidate_root_symlink_is_rejected(self):
        source, real_candidate = self.make_case()
        self.write_core(real_candidate, "keep me\n")
        candidate_link = source.parent / "candidate-link"
        try:
            candidate_link.symlink_to(real_candidate, target_is_directory=True)
        except (NotImplementedError, OSError) as error:
            self.skipTest(f"symlinks are unavailable: {error}")
        spec = self.make_spec(source)

        self.assertTrue(candidate_link.is_symlink())
        self.assert_api_invalid(source, candidate_link, spec)
        process = self.run_cli_check(source, candidate_link, spec)
        self.assertEqual(process.returncode, 2, process.stderr)
        self.assert_cli_error_shape(json.loads(process.stdout))

    def test_invalid_spec_shapes_are_rejected(self):
        source, candidate = self.make_case()
        self.write_core(candidate, "keep me\n")
        valid = self.make_spec(source)

        invalid_specs = {
            "not_object": [],
            "missing_hash": {
                "core_files": valid["core_files"],
                "blocks": valid["blocks"],
            },
            "hash_not_a_sha256": {
                **valid,
                "source_sha256": "g" * 64,
            },
            "uppercase_hash": {
                **valid,
                "source_sha256": valid["source_sha256"].upper(),
            },
            "short_hash": {**valid, "source_sha256": "a" * 63},
            "hash_not_string": {**valid, "source_sha256": 123},
            "core_files_missing": {
                "source_sha256": valid["source_sha256"],
                "blocks": valid["blocks"],
            },
            "empty_core_inventory": {**valid, "core_files": []},
            "core_inventory_not_list": {
                **valid,
                "core_files": "core.md",
            },
            "duplicate_core_path": {
                **valid,
                "core_files": ["core.md", "core.md"],
            },
            "core_path_not_string": {**valid, "core_files": [1]},
            "core_wrong_extension": {
                **valid,
                "core_files": ["core.json"],
            },
            "missing_core_file": {
                **valid,
                "core_files": ["missing.md"],
            },
            "blocks_not_list": {**valid, "blocks": valid["blocks"][0]},
            "block_not_object": {**valid, "blocks": ["line"]},
            "missing_block_id": {
                **valid,
                "blocks": [{"start": 2, "end": 2}],
            },
            "missing_block_start": {
                **valid,
                "blocks": [{"id": "line", "end": 2}],
            },
            "missing_block_end": {
                **valid,
                "blocks": [{"id": "line", "start": 2}],
            },
            "blocks_missing": {
                "source_sha256": valid["source_sha256"],
                "core_files": valid["core_files"],
            },
            "duplicate_ids": {
                **valid,
                "blocks": [
                    {"id": "same", "start": 2, "end": 2},
                    {"id": "same", "start": 3, "end": 3},
                ],
            },
            "blank_id": {
                **valid,
                "blocks": [{"id": "", "start": 2, "end": 2}],
            },
            "whitespace_id": {
                **valid,
                "blocks": [{"id": "   ", "start": 2, "end": 2}],
            },
            "bool_start": {
                **valid,
                "blocks": [{"id": "line", "start": True, "end": 2}],
            },
            "bool_end": {
                **valid,
                "blocks": [{"id": "line", "start": 2, "end": True}],
            },
            "zero_start": {
                **valid,
                "blocks": [{"id": "line", "start": 0, "end": 2}],
            },
            "end_before_one": {
                **valid,
                "blocks": [{"id": "line", "start": 1, "end": 0}],
            },
            "reversed_bounds": {
                **valid,
                "blocks": [{"id": "line", "start": 3, "end": 2}],
            },
            "bounds_past_source": {
                **valid,
                "blocks": [{"id": "line", "start": 2, "end": 99}],
            },
            "float_bound": {
                **valid,
                "blocks": [{"id": "line", "start": 2.0, "end": 2}],
            },
            "string_bound": {
                **valid,
                "blocks": [{"id": "line", "start": "2", "end": 2}],
            },
        }

        for name, spec in invalid_specs.items():
            with self.subTest(spec=name):
                self.assert_api_invalid(source, candidate, spec)

                process = self.run_cli_check(source, candidate, spec)
                self.assertEqual(process.returncode, 2, process.stderr)
                self.assert_cli_error_shape(json.loads(process.stdout))

    def test_blank_block_is_rejected(self):
        source, candidate = self.make_case(b"\nkeep me\n")
        self.write_core(candidate, "\nkeep me\n")
        spec = self.make_spec(
            source,
            blocks=[{"id": "blank-line", "start": 1, "end": 1}],
        )

        self.assert_api_invalid(source, candidate, spec)
        process = self.run_cli_check(source, candidate, spec)
        self.assertEqual(process.returncode, 2, process.stderr)
        self.assert_cli_error_shape(json.loads(process.stdout))

    def test_malformed_json_and_invalid_utf8_spec_are_cli_errors(self):
        source, candidate = self.make_case()
        self.write_core(candidate, "keep me\n")
        invalid_documents = {
            "malformed_json": b'{"source_sha256":',
            "invalid_utf8": b"\xff",
        }

        for name, document in invalid_documents.items():
            with self.subTest(spec=name):
                process = self.run_cli_check_raw_spec(
                    source,
                    candidate,
                    document,
                )
                self.assertEqual(process.returncode, 2, process.stderr)
                self.assert_cli_error_shape(json.loads(process.stdout))

    def test_wrong_arguments_are_json_errors(self):
        source, candidate = self.make_case()
        self.write_core(candidate, "keep me\n")

        processes = [
            self.run_cli(),
            self.run_cli("check", str(source), str(candidate)),
            self.run_cli(
                "check",
                str(source),
                str(candidate),
                str(source.parent / "missing-spec.json"),
                "extra",
            ),
        ]
        for process in processes:
            self.assertEqual(process.returncode, 2, process.stderr)
            payload = json.loads(process.stdout)
            self.assertEqual(payload.get("schema_version"), 1)
            if "check" in process.args:
                self.assertEqual(payload.get("command"), "check")
            self.assertTrue(payload.get("error"))

    def test_candidate_inventory_and_type_are_strict(self):
        with self.subTest(candidate="empty"):
            source, candidate = self.make_case()
            spec = self.make_spec(source)

            self.assert_api_invalid(source, candidate, spec)
            process = self.run_cli_check(source, candidate, spec)
            self.assertEqual(process.returncode, 2, process.stderr)
            self.assert_cli_error_shape(json.loads(process.stdout))

        with self.subTest(candidate="missing"):
            source, candidate = self.make_case()
            spec = self.make_spec(source)
            missing_candidate = source.parent / "missing-candidate"

            self.assert_api_invalid(source, missing_candidate, spec)
            process = self.run_cli_check(
                source,
                missing_candidate,
                spec,
            )
            self.assertEqual(process.returncode, 2, process.stderr)
            self.assert_cli_error_shape(json.loads(process.stdout))

        with self.subTest(candidate="not_directory"):
            _, placeholder_candidate = self.make_case(b"keep me\n")
            placeholder_candidate.rmdir()
            case_root = placeholder_candidate.parent
            source = case_root / "source.md"
            candidate_file = case_root / "candidate.md"
            candidate_file.write_text("keep me\n", encoding="utf-8")
            spec = self.make_spec(
                source,
                blocks=[{"id": "line", "start": 1, "end": 1}],
            )

            self.assert_api_invalid(source, candidate_file, spec)
            process = self.run_cli_check(source, candidate_file, spec)
            self.assertEqual(process.returncode, 2, process.stderr)
            self.assert_cli_error_shape(json.loads(process.stdout))

        with self.subTest(candidate="unsupported_file"):
            source, candidate = self.make_case(b"keep me\n")
            (candidate / "core.md").write_text(
                "keep me\n",
                encoding="utf-8",
            )
            (candidate / "metadata.json").write_text(
                "{}\n",
                encoding="utf-8",
            )
            spec = self.make_spec(
                source,
                blocks=[{"id": "line", "start": 1, "end": 1}],
            )

            self.assert_api_invalid(source, candidate, spec)
            process = self.run_cli_check(source, candidate, spec)
            self.assertEqual(process.returncode, 2, process.stderr)
            self.assert_cli_error_shape(json.loads(process.stdout))

    def test_check_is_read_only_for_source_and_candidate(self):
        source, candidate = self.make_case()
        core = self.write_core(candidate, "keep me\n")
        nested = candidate / "nested"
        nested.mkdir()
        other = nested / "other.txt"
        other.write_text("unrelated\n", encoding="utf-8")
        original = {
            source: source.read_bytes(),
            core: core.read_bytes(),
            other: other.read_bytes(),
        }
        original_entries = {
            path.relative_to(candidate).as_posix()
            for path in candidate.rglob("*")
        }
        spec = self.make_spec(source)

        result = self.run_api(source, candidate, spec)
        self.assert_api_check_shape(result)
        self.assertTrue(result["pass"])
        for path, expected in original.items():
            self.assertEqual(path.read_bytes(), expected)
        self.assertEqual(
            {
                path.relative_to(candidate).as_posix()
                for path in candidate.rglob("*")
            },
            original_entries,
        )

        process = self.run_cli_check(source, candidate, spec)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assert_cli_check_shape(json.loads(process.stdout))
        for path, expected in original.items():
            self.assertEqual(path.read_bytes(), expected)
        self.assertEqual(
            {
                path.relative_to(candidate).as_posix()
                for path in candidate.rglob("*")
            },
            original_entries,
        )

    def test_audit_command_is_absent_and_returns_json_error(self):
        process = self.run_cli("audit")
        self.assertEqual(process.returncode, 2, process.stderr)
        payload = json.loads(process.stdout)
        self.assertEqual(payload.get("schema_version"), 1)
        self.assertIsNone(payload.get("command"))
        self.assertTrue(payload.get("error"))

    def test_help_and_version_are_successful_text(self):
        for argument in ("--help", "--version"):
            with self.subTest(argument=argument):
                process = self.run_cli(argument)
                self.assertEqual(process.returncode, 0, process.stderr)
                self.assertTrue(process.stdout.strip())
                with self.assertRaises(json.JSONDecodeError):
                    json.loads(process.stdout)


if __name__ == "__main__":
    unittest.main()
