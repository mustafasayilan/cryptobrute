from contextlib import ExitStack
from datetime import datetime, timezone
import os
import platform
from statistics import median
from time import perf_counter_ns

from .cuda import CudaScanner
from .puzzle import make_puzzle, scan_cpu


def benchmark(size, puzzle_number, backend, device, runs, warmups, *, on_sample=None):
    benchmark_start = perf_counter_ns()
    if runs < 1 or warmups < 0:
        raise ValueError("Runs must be positive and warmups must be non-negative.")
    target, expected = make_puzzle(size, puzzle_number)
    measured_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with ExitStack() as stack:
        scanners = {}
        results = {}
        if backend in ("cpu", "both"):
            scanners["cpu"] = scan_cpu
            results["cpu"] = {"worker_threads": 1}
        if backend in ("cuda", "both"):
            start = perf_counter_ns()
            scanner = stack.enter_context(CudaScanner(device))
            setup_ns = perf_counter_ns() - start
            scanners["cuda"] = scanner.scan
            results["cuda"] = {**scanner.info, "setup_ns": setup_ns}
        if not scanners:
            raise ValueError(f"Unknown backend: {backend}")

        for result in results.values():
            result["samples_ns"] = []
        order = list(scanners)
        for iteration in range(warmups + runs):
            backends = order if iteration % 2 == 0 else reversed(order)
            for name in backends:
                scan = scanners[name]
                start = perf_counter_ns()
                found = scan(size, target)
                elapsed = perf_counter_ns() - start
                if found != expected:
                    raise RuntimeError(f"{name} returned {found}, expected {expected}.")
                if iteration >= warmups:
                    samples = results[name]["samples_ns"]
                    samples.append(elapsed)
                    if on_sample is not None:
                        on_sample(name, len(samples), elapsed)

    for result in results.values():
        result["median_ns"] = median(result["samples_ns"])
        result["candidates_per_second"] = round(size * 1_000_000_000 / result["median_ns"])

    return {
        "measured_at_utc": measured_at,
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "processor": platform.processor(),
        "logical_processors": os.cpu_count(),
        "candidate_count": size,
        "puzzle_number": puzzle_number,
        "target_label": target,
        "match": expected,
        "warmups": warmups,
        "runs": runs,
        "candidates_per_timed_scan": size,
        "total_timed_candidates_per_backend": size * runs,
        "elapsed_ns": perf_counter_ns() - benchmark_start,
        "backends": results,
    }
