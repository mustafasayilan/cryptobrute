from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
import os
import unittest

from cryptobrute_lab.benchmark import benchmark
from cryptobrute_lab.cli import main
from cryptobrute_lab.cuda import CudaError, CudaScanner
from cryptobrute_lab.puzzle import MAX_CANDIDATES, make_puzzle, scan_cpu, synthetic_label


class PuzzleTests(unittest.TestCase):
    def test_known_puzzle(self):
        self.assertEqual(make_puzzle(1_000_003, 2026), (732_983, 287_831))

    def test_first_and_last_candidates(self):
        self.assertEqual(scan_cpu(257, synthetic_label(0)), 0)
        self.assertEqual(scan_cpu(257, synthetic_label(256)), 256)
        self.assertEqual(scan_cpu(MAX_CANDIDATES, synthetic_label(MAX_CANDIDATES - 1)), MAX_CANDIDATES - 1)

    def test_missing_label(self):
        self.assertIsNone(scan_cpu(257, synthetic_label(257)))

    def test_invalid_size_target_and_puzzle_number(self):
        for size, target in ((0, 0), (MAX_CANDIDATES + 1, 0), (1, -1), (1, MAX_CANDIDATES)):
            with self.subTest(size=size, target=target):
                with self.assertRaises(ValueError):
                    scan_cpu(size, target)
        for number in (-1, 1 << 32):
            with self.subTest(number=number):
                with self.assertRaises(ValueError):
                    make_puzzle(1, number)

    def test_cpu_benchmark_records_each_timed_sample(self):
        result = benchmark(257, 2026, "cpu", 0, 5, 2)
        cpu = result["backends"]["cpu"]
        self.assertEqual(result["match"], 29)
        self.assertEqual(set(result["backends"]), {"cpu"})
        self.assertEqual(len(cpu["samples_ns"]), 5)
        self.assertGreater(cpu["candidates_per_second"], 0)

    def test_cli_error_exits_with_message(self):
        stderr = StringIO()
        with redirect_stderr(stderr):
            exit_code = main(["demo", "--size", "0"])
        self.assertEqual(exit_code, 1)
        self.assertIn("Candidate count", stderr.getvalue())

    def test_cli_cpu_demo_outputs_json(self):
        stdout = StringIO()
        with redirect_stdout(stdout):
            exit_code = main(["demo", "--size", "1"])
        self.assertEqual(exit_code, 0)
        result = json.loads(stdout.getvalue())
        self.assertEqual(result["match"], 0)
        self.assertEqual(result["candidates_scanned"], 1)
        self.assertGreater(result["scan_elapsed_ns"], 0)

    def test_benchmark_progress_preserves_json_output(self):
        stdout, stderr = StringIO(), StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main([
                "benchmark", "--backend", "cpu", "--size", "257",
                "--runs", "2", "--warmups", "1", "--progress",
            ])
        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(stdout.getvalue())["total_timed_candidates_per_backend"], 514)
        self.assertIn("cpu 2/2 | 514 timed candidates", stderr.getvalue())


@unittest.skipUnless(os.environ.get("CRYPTOBRUTE_TEST_CUDA") == "1", "Set CRYPTOBRUTE_TEST_CUDA=1 to test CUDA.")
class CudaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.device_index = int(os.environ.get("CRYPTOBRUTE_CUDA_DEVICE", "0"))
        cls.scanner = cls.enterClassContext(CudaScanner(cls.device_index))

    def test_matches_cpu_at_grid_boundaries(self):
        for size in (1, 255, 256, 257, 4_099, 1_000_003, MAX_CANDIDATES):
            with self.subTest(size=size):
                target, expected = make_puzzle(size, 2026)
                self.assertEqual(scan_cpu(size, target), expected)
                self.assertEqual(self.scanner.scan(size, target), expected)

    def test_buffer_resets_between_scans(self):
        self.assertEqual(self.scanner.scan(257, synthetic_label(256)), 256)
        self.assertIsNone(self.scanner.scan(257, synthetic_label(257)))
        self.assertEqual(self.scanner.scan(257, synthetic_label(0)), 0)

    def test_invalid_device_fails_explicitly(self):
        with self.assertRaisesRegex(CudaError, "unavailable"):
            with CudaScanner(-1):
                self.fail("Invalid device opened.")

    def test_benchmark_compares_both_backends(self):
        result = benchmark(4_099, 2026, "both", self.device_index, 3, 1)
        self.assertEqual(set(result["backends"]), {"cpu", "cuda"})
        for backend in result["backends"].values():
            self.assertEqual(len(backend["samples_ns"]), 3)
        self.assertEqual(self.scanner.scan(257, synthetic_label(0)), 0)
