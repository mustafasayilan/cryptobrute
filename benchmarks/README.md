# CPU and CUDA benchmark

Measured on November 13, 2026 on Windows 11 (build 26300), with an Intel Core i9-14900KF, an NVIDIA GeForce RTX 4090, NVIDIA driver 621.14, CUDA/NVRTC 12.9 and CPython 3.12.14. The CPU reference used one worker thread.

| Candidates per scan | CPU median | CUDA median | CUDA setup | CPU / CUDA scan time | Raw samples |
| ---: | ---: | ---: | ---: | ---: | :--- |
| 4,099 | 0.3308 ms | 0.0209 ms | 134.9364 ms | 15.8× | [JSON](rtx4090-4099.json) |
| 65,537 | 5.5906 ms | 0.0588 ms | 122.1915 ms | 95.1× | [JSON](rtx4090-65537.json) |
| 1,000,003 | 86.7405 ms | 0.0682 ms | 125.8671 ms | 1,271.9× | [JSON](rtx4090-1000003.json) |

Each backend ran 3 warmups and 15 timed scans per size. The CPU and GPU evaluated the same synthetic label puzzle and returned the expected result on every run. The command alternates backend order. CUDA scan time includes resetting the result buffer, launching the kernel and copying the result back to the host. Setup time includes NVRTC compilation and CUDA context, module and buffer initialization. Each JSON report includes all timing samples, the total timed candidate count and wall-clock duration for the combined benchmark.

The ratios describe repeated scans of this 20-bit synthetic workload against a single-threaded Python reference. For a one-off GPU run, include setup time. Timing varies by device, driver and system load.

```powershell
foreach ($size in 4099, 65537, 1000003) {
    python -m cryptobrute_lab benchmark --backend both --size $size --puzzle 2026 --runs 15 --warmups 3 --progress
}
```
