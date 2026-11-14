# Cryptobrute CPU and CUDA lab

Cryptobrute is an offline lab for comparing exhaustive search on a CPU and an NVIDIA GPU. Both backends search the same small, deterministic puzzle over synthetic 20-bit labels. The separate `audit` command reports confirmed unspent outputs for Bitcoin addresses you supply.

## Requirements

- Python 3.12 or newer. The CPU demo, audit, and their tests use the standard library.
- For CUDA, use 64-bit Python on Windows or Linux, an NVIDIA GPU with a compatible driver, and the CUDA Toolkit with NVRTC. Choose a toolkit release that supports your GPU's compute capability. The reference run uses CUDA 12.9 on Windows.

### CPU and GPU quick start

Run these commands from the repository root. Use `python3` or `py -3` if that is how your Python installation is invoked.

```sh
python -m cryptobrute_lab demo --backend cpu --size 1000003 --puzzle 2026
python -m cryptobrute_lab demo --backend cuda --size 1000003 --puzzle 2026
python -m cryptobrute_lab benchmark --backend both --size 1000003 --puzzle 2026 --runs 15 --warmups 3 --progress
```

Both demo commands should return target label `732983` and match `287831`. The input range is `0` through `size - 1`, with a maximum of 1,048,576 candidates. The CPU reference scans the whole range on one thread. The CUDA kernel assigns one candidate to each GPU thread and checks that its index is within range. A fixed permutation of the candidate index produces each label.

The demo reports the number of candidates scanned, scan time, and total elapsed time in nanoseconds. With `--progress`, the benchmark writes progress, cumulative candidate counts, candidates per second, and elapsed time to stderr after each measured scan. The JSON report on stdout includes all samples and the CUDA setup time. In PowerShell, append `| Tee-Object -FilePath .\benchmark.json` to display and save that report.

The Windows Toolkit installer normally sets `CUDA_PATH`. For a custom installation, set `$env:CUDA_PATH` to the toolkit root in PowerShell. On Linux, the default root is `/usr/local/cuda`. You can set `CUDA_PATH` or `CUDA_HOME` to another toolkit root. A driver-only installation typically lacks NVRTC. Use `--device 0` to select the first CUDA device, or use `--backend cpu` on a machine without CUDA.

- [CUDA Toolkit downloads](https://developer.nvidia.com/cuda-downloads)
- [NVIDIA NVRTC guide](https://docs.nvidia.com/cuda/nvrtc/)
- [Reference benchmark and raw samples](benchmarks/README.md)

## Generate and verify a regtest address

Install the optional signing dependency. These examples use PowerShell.

```powershell
python -m pip install -r requirements-key-demo.txt
python -m cryptobrute_lab regtest-match -i examples/regtest-addresses.txt
python -m cryptobrute_lab verify-key-demo examples/regtest-proof.json
python -m cryptobrute_lab key-demo --message "My Cryptobrute test" | Set-Content -Encoding utf8 proof.json
python -m cryptobrute_lab verify-key-demo proof.json
(Get-Content -Raw proof.json | ConvertFrom-Json).regtest_address | Set-Content -Encoding utf8 my-regtest-addresses.txt
python -m cryptobrute_lab regtest-match -i my-regtest-addresses.txt --proof proof.json
```

The bundled fixture derives its address from a public secp256k1 test vector and should match line 2. The fresh-key example generates one ephemeral secp256k1 key pair, signs the supplied message using ECDSA with SHA-256, and exports the public key, the DER signature in Base64, and the P2WPKH address. The verifier derives the address from the verified public key and checks the address in the report. Changing the message or using a different key invalidates the signature.

The match command accepts lowercase `bcrt1q` P2WPKH addresses, one per line. It validates their Bech32 checksums and reports the first exact match, its line number, the number of distinct addresses checked, and elapsed nanoseconds. The test fixture and fresh-key workflow both run offline. The CPU and GPU benchmark measures the synthetic puzzle described above.

Regtest addresses belong to a private Bitcoin test chain. Public explorers such as Blockchain.com show public chains. With a local Bitcoin Core node running in regtest mode, validate the bundled address and its output script:

```sh
bitcoin-cli -regtest validateaddress bcrt1qw508d6qejxtdg4y5r3zarvary0c5xw7kygt080
```

Expect `isvalid: true` and `scriptPubKey: 0014751e76e8199196d454941c45d1b3a323f1433bd6`. Address validation works before the address receives a transaction. To inspect confirmed outputs for the example address on your regtest chain, point `audit` at the regtest cookie and RPC port (18443 by default).

[Bitcoin Core regtest documentation](https://developer.bitcoin.org/examples/testing.html#regtest-mode) · [Bech32 specification](https://bips.dev/173/) · [Bitcoin Core regtest reference vector](https://github.com/bitcoin/bitcoin/issues/16855)

## Tests

The default test run exercises the CPU lab and the audit RPC contract. Installing the optional dependency also enables the key and regtest matching tests.

```sh
python -m unittest discover -s tests -v
```

Enable the CUDA tests explicitly. An enabled CUDA test run fails if it cannot access the GPU.

PowerShell

```powershell
$env:CRYPTOBRUTE_TEST_CUDA = "1"
python -m unittest discover -s tests -v
```

Linux shell

```sh
CRYPTOBRUTE_TEST_CUDA=1 python -m unittest discover -s tests -v
```

Set `CRYPTOBRUTE_CUDA_DEVICE` to select a GPU for the tests on a multi-GPU host.

## Bitcoin address audit

Run a synced Bitcoin Core node with RPC enabled on loopback and pass its RPC cookie file. The input is a UTF-8 file containing one address per line. Bitcoin Core validates each address against the node's network, then scans the confirmed UTXO set once for the list. The JSON result includes the network, block height, block hash, and the total in integer satoshis for each distinct address.

```sh
python -m cryptobrute_lab audit -i addresses.txt --cookie /path/to/.cookie --rpc-port 8332
```

The reported amounts reflect the node's chain at the returned block. They exclude pending transactions. A full UTXO scan may take several minutes on mainnet. Use `--timeout` to set the RPC timeout in seconds.

[Bitcoin Core RPC reference for `scantxoutset`](https://bitcoincore.org/en/doc/31.0.0/rpc/blockchain/scantxoutset/)
