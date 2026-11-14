import argparse
import json
from pathlib import Path
import sys
from time import perf_counter_ns

from .audit import BitcoinRpc, audit_addresses, read_addresses
from .benchmark import benchmark
from .cuda import CudaScanner
from .puzzle import MAX_CANDIDATES, make_puzzle, scan_cpu


def run_demo(args):
    command_start = perf_counter_ns()
    target, expected = make_puzzle(args.size, args.puzzle)
    result = {
        "backend": args.backend,
        "candidate_count": args.size,
        "puzzle_number": args.puzzle,
        "target_label": target,
    }
    if args.backend == "cuda":
        with CudaScanner(args.device) as scanner:
            start = perf_counter_ns()
            match = scanner.scan(args.size, target)
            elapsed = perf_counter_ns() - start
            result["cuda"] = scanner.info
    else:
        start = perf_counter_ns()
        match = scan_cpu(args.size, target)
        elapsed = perf_counter_ns() - start
    if match != expected:
        raise RuntimeError(f"{args.backend} returned {match}, expected {expected}.")
    result["match"] = match
    result["candidates_scanned"] = args.size
    result["scan_elapsed_ns"] = elapsed
    result["elapsed_ns"] = perf_counter_ns() - command_start
    return result


def run_benchmark(args):
    start = perf_counter_ns()

    def report_sample(backend, completed, scan_ns):
        total = (perf_counter_ns() - start) / 1e9
        rate = f"{args.size * 1e9 / scan_ns:,.0f} candidates/s" if scan_ns else "rate unavailable"
        print(
            f"{backend} {completed}/{args.runs} | {completed * args.size:,} timed candidates "
            f"| {rate} | scan {scan_ns / 1e6:.3f} ms | elapsed {total:.3f} s",
            file=sys.stderr,
            flush=True,
        )

    return benchmark(
        args.size, args.puzzle, args.backend, args.device, args.runs, args.warmups,
        on_sample=report_sample if args.progress else None,
    )


def run_audit(args):
    addresses = read_addresses(args.addresses)
    with BitcoinRpc(args.cookie, args.rpc_port, args.timeout) as rpc:
        return audit_addresses(rpc, addresses)


def load_key_demo():
    try:
        from . import key_demo
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Install the key demo dependency with python -m pip install -r requirements-key-demo.txt."
        ) from exc
    return key_demo


def run_key_demo(args):
    key_demo = load_key_demo()
    from .regtest import verified_regtest_address

    message = key_demo.DEFAULT_MESSAGE if args.message is None else args.message
    proof = key_demo.generate_proof(message)
    address = verified_regtest_address(proof)
    return {**proof, "regtest_address": address}


def read_proof(path):
    proof = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(proof, dict) and "proof" in proof:
        nested = proof["proof"]
        if isinstance(nested, dict) and "regtest_address" in proof:
            address = proof["regtest_address"]
            if nested.get("regtest_address", address) != address:
                raise ValueError("The report contains conflicting regtest addresses.")
            return {**nested, "regtest_address": address}
        return nested
    return proof


def run_verify_key_demo(args):
    key_demo = load_key_demo()
    from .regtest import verified_regtest_address

    proof = read_proof(args.proof)
    address = verified_regtest_address(proof)
    return {"verified": True, "format": key_demo.PROOF_FORMAT, "regtest_address": address}


def run_regtest_match(args):
    load_key_demo()
    from .regtest import match_regtest_address

    proof = read_proof(args.proof) if args.proof is not None else None
    if args.proof is not None and not isinstance(proof, dict):
        raise ValueError("The key proof must be a JSON object.")
    return match_regtest_address(args.addresses, proof)


def add_puzzle_options(parser):
    parser.add_argument("--size", type=int, default=MAX_CANDIDATES, help="Number of synthetic candidates")
    parser.add_argument("--puzzle", type=int, default=2026, help="Reproducible puzzle number")
    parser.add_argument("--device", type=int, default=0, help="CUDA device index")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Cryptobrute educational CPU and CUDA lab")
    commands = parser.add_subparsers(dest="command", required=True)

    demo = commands.add_parser("demo", help="Solve one synthetic label puzzle")
    add_puzzle_options(demo)
    demo.add_argument("--backend", choices=("cpu", "cuda"), default="cpu")
    demo.set_defaults(run=run_demo)

    timing = commands.add_parser("benchmark", help="Measure and verify repeated synthetic scans")
    add_puzzle_options(timing)
    timing.add_argument("--backend", choices=("cpu", "cuda", "both"), default="both")
    timing.add_argument("--runs", type=int, default=15, help="Timed runs per backend")
    timing.add_argument("--warmups", type=int, default=3, help="Untimed runs per backend")
    timing.add_argument("--progress", action="store_true", help="Print progress and scan rate to stderr")
    timing.set_defaults(run=run_benchmark)

    audit = commands.add_parser("audit", help="Read confirmed UTXOs for supplied Bitcoin addresses")
    audit.add_argument("-i", "--addresses", type=Path, required=True, help="Text file with one address per line")
    audit.add_argument("--cookie", type=Path, required=True, help="Path to Bitcoin Core's RPC cookie")
    audit.add_argument("--rpc-port", type=int, default=8332, help="Local Bitcoin Core RPC port")
    audit.add_argument("--timeout", type=int, default=600, help="RPC timeout in seconds")
    audit.set_defaults(run=run_audit)

    key_demo = commands.add_parser("key-demo", help="Generate one secp256k1 key pair and sign a test message")
    key_demo.add_argument("--message", help="UTF-8 text to sign")
    key_demo.set_defaults(run=run_key_demo)

    verify = commands.add_parser("verify-key-demo", help="Verify a key-demo signature with its public key")
    verify.add_argument("proof", type=Path, help="JSON file produced by key-demo or regtest-match")
    verify.set_defaults(run=run_verify_key_demo)

    regtest = commands.add_parser("regtest-match", help="Match a verified regtest address against a text file")
    regtest.add_argument("-i", "--addresses", type=Path, required=True, help="One regtest P2WPKH address per line")
    regtest.add_argument("--proof", type=Path, help="Use the public proof from key-demo instead of the test vector")
    regtest.set_defaults(run=run_regtest_match)

    args = parser.parse_args(argv)
    try:
        print(json.dumps(args.run(args), indent=2))
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130
    return 0
