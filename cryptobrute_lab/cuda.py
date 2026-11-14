import ctypes as ct
from ctypes.util import find_library
import os
from pathlib import Path
import sys

from .puzzle import validate_scan

THREADS_PER_BLOCK = 256
NO_MATCH = 0xFFFFFFFF
COMPUTE_CAPABILITY_MAJOR = 75
COMPUTE_CAPABILITY_MINOR = 76


class CudaError(RuntimeError):
    pass


def bind(library, name, arguments, result=ct.c_int):
    try:
        function = getattr(library, name)
    except AttributeError as exc:
        raise CudaError(f"CUDA library is missing {name}.") from exc
    function.argtypes = arguments
    function.restype = result
    return function


def load_driver():
    if ct.sizeof(ct.c_void_p) != 8:
        raise CudaError("The CUDA backend requires 64-bit Python.")
    try:
        if sys.platform == "win32":
            return ct.WinDLL("nvcuda.dll", winmode=0x800)  # Search System32.
        if sys.platform.startswith("linux"):
            return ct.CDLL("libcuda.so.1")
    except OSError as exc:
        raise CudaError("The NVIDIA CUDA driver could not be loaded.") from exc
    raise CudaError("The CUDA backend supports Windows and Linux.")


def compile_kernel(architecture):
    toolkit = os.environ.get("CUDA_PATH") or os.environ.get("CUDA_HOME")
    try:
        if sys.platform == "win32":
            if not toolkit:
                raise CudaError("Set CUDA_PATH to the installed CUDA Toolkit directory.")
            bin_directory = Path(toolkit).resolve() / "bin"
            libraries = list(bin_directory.glob("nvrtc64_*_0.dll"))
            if not libraries:
                raise CudaError(f"NVRTC was not found in {bin_directory}.")
            with os.add_dll_directory(str(bin_directory)):
                return compile_cubin(ct.CDLL(str(libraries[0])), architecture)

        lib_directory = Path(toolkit or "/usr/local/cuda") / "lib64"
        library = lib_directory / "libnvrtc.so"
        library_name = str(library.resolve()) if library.is_file() else find_library("nvrtc")
        if not library_name:
            raise CudaError("NVRTC was not found. Set CUDA_PATH to your CUDA Toolkit directory.")
        return compile_cubin(ct.CDLL(library_name), architecture)
    except OSError as exc:
        raise CudaError(f"NVRTC could not be loaded: {exc}") from exc


def compile_cubin(library, architecture):
    handle = ct.c_void_p
    size_pointer = ct.POINTER(ct.c_size_t)
    int_pointer = ct.POINTER(ct.c_int)
    char_pointer = ct.c_char_p
    error_string = bind(library, "nvrtcGetErrorString", [ct.c_int], char_pointer)

    def check(function, *arguments):
        status = function(*arguments)
        if status:
            message = error_string(status).decode("ascii", errors="replace")
            raise CudaError(f"{function.__name__}: {message}")

    version = bind(library, "nvrtcVersion", [int_pointer, int_pointer])
    major, minor = ct.c_int(), ct.c_int()
    check(version, ct.byref(major), ct.byref(minor))

    create = bind(
        library, "nvrtcCreateProgram",
        [ct.POINTER(handle), char_pointer, char_pointer, ct.c_int,
         ct.POINTER(char_pointer), ct.POINTER(char_pointer)],
    )
    destroy = bind(library, "nvrtcDestroyProgram", [ct.POINTER(handle)])
    compile_program = bind(
        library, "nvrtcCompileProgram", [handle, ct.c_int, ct.POINTER(char_pointer)]
    )
    get_log_size = bind(library, "nvrtcGetProgramLogSize", [handle, size_pointer])
    get_log = bind(library, "nvrtcGetProgramLog", [handle, ct.c_void_p])
    get_size = bind(library, "nvrtcGetCUBINSize", [handle, size_pointer])
    get_cubin = bind(library, "nvrtcGetCUBIN", [handle, ct.c_void_p])

    source_file = Path(__file__).with_name("synthetic_scan.cu")
    program = handle()
    check(create, ct.byref(program), source_file.read_bytes(), source_file.name.encode(), 0, None, None)
    try:
        options = (char_pointer * 1)(f"--gpu-architecture=sm_{architecture}".encode("ascii"))
        status = compile_program(program, len(options), options)
        if status:
            log_size = ct.c_size_t()
            check(get_log_size, program, ct.byref(log_size))
            log = ct.create_string_buffer(log_size.value)
            check(get_log, program, log)
            message = log.value.decode("utf-8", errors="replace").strip()
            status_text = error_string(status).decode("ascii", errors="replace")
            raise CudaError(f"NVRTC could not compile for sm_{architecture}: {message or status_text}")

        cubin_size = ct.c_size_t()
        check(get_size, program, ct.byref(cubin_size))
        cubin = ct.create_string_buffer(cubin_size.value)
        check(get_cubin, program, cubin)
        return cubin, f"{major.value}.{minor.value}"
    finally:
        destroy(ct.byref(program))


class CudaScanner:
    """Own a CUDA context and its scan buffer on the calling thread."""

    def __init__(self, device_index=0):
        self.device_index = device_index
        self._context = None

    def __enter__(self):
        if self._context is not None:
            raise CudaError("This CUDA scanner is already open.")
        driver = load_driver()
        handle = ct.c_void_p
        handle_pointer = ct.POINTER(handle)
        int_pointer = ct.POINTER(ct.c_int)
        device_pointer = ct.c_uint64
        self._error_name = bind(driver, "cuGetErrorName", [ct.c_int, ct.POINTER(ct.c_char_p)])
        self._destroy_context = bind(driver, "cuCtxDestroy_v2", [handle])

        self._call(bind(driver, "cuInit", [ct.c_uint]), 0)
        get_count = bind(driver, "cuDeviceGetCount", [int_pointer])
        count = ct.c_int()
        self._call(get_count, ct.byref(count))
        if not 0 <= self.device_index < count.value:
            raise CudaError(f"CUDA device {self.device_index} is unavailable ({count.value} detected).")

        get_device = bind(driver, "cuDeviceGet", [int_pointer, ct.c_int])
        get_name = bind(driver, "cuDeviceGetName", [ct.c_void_p, ct.c_int, ct.c_int])
        get_attribute = bind(driver, "cuDeviceGetAttribute", [int_pointer, ct.c_int, ct.c_int])
        get_version = bind(driver, "cuDriverGetVersion", [int_pointer])

        device, major, minor, driver_version = ct.c_int(), ct.c_int(), ct.c_int(), ct.c_int()
        device_name = ct.create_string_buffer(256)
        self._call(get_device, ct.byref(device), self.device_index)
        self._call(get_name, device_name, len(device_name), device)
        self._call(get_attribute, ct.byref(major), COMPUTE_CAPABILITY_MAJOR, device)
        self._call(get_attribute, ct.byref(minor), COMPUTE_CAPABILITY_MINOR, device)
        self._call(get_version, ct.byref(driver_version))

        cubin, nvrtc_version = compile_kernel(f"{major.value}{minor.value}")
        self.info = {
            "device_index": self.device_index,
            "device": device_name.value.decode("utf-8", errors="replace"),
            "compute_capability": f"{major.value}.{minor.value}",
            "driver_api_version": driver_version.value,
            "nvrtc_version": nvrtc_version,
        }

        create_context = bind(driver, "cuCtxCreate_v2", [handle_pointer, ct.c_uint, ct.c_int])
        load_module = bind(driver, "cuModuleLoadData", [handle_pointer, handle])
        get_kernel = bind(driver, "cuModuleGetFunction", [handle_pointer, handle, ct.c_char_p])
        alloc = bind(driver, "cuMemAlloc_v2", [ct.POINTER(device_pointer), ct.c_size_t])

        self._reset = bind(driver, "cuMemsetD32_v2", [device_pointer, ct.c_uint32, ct.c_size_t])
        self._launch = bind(
            driver, "cuLaunchKernel",
            [handle, ct.c_uint, ct.c_uint, ct.c_uint, ct.c_uint, ct.c_uint, ct.c_uint,
             ct.c_uint, handle, handle_pointer, handle_pointer],
        )
        self._copy = bind(driver, "cuMemcpyDtoH_v2", [handle, device_pointer, ct.c_size_t])

        context, module, self._kernel = handle(), handle(), handle()
        self._match_buffer = device_pointer()
        self._call(create_context, ct.byref(context), 0, device)
        try:
            self._call(load_module, ct.byref(module), cubin)
            self._call(get_kernel, ct.byref(self._kernel), module, b"scan_synthetic_labels")
            self._call(alloc, ct.byref(self._match_buffer), ct.sizeof(ct.c_uint32))
        except BaseException:
            self._destroy_context(context)
            raise
        self._context = context
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        # Destroying the context also releases its module and device buffer.
        context, self._context = self._context, None
        if exc_type is None:
            self._call(self._destroy_context, context)
        else:
            self._destroy_context(context)

    def _call(self, function, *arguments):
        status = function(*arguments)
        if status:
            name = ct.c_char_p()
            self._error_name(status, ct.byref(name))
            message = name.value.decode("ascii", errors="replace") if name.value else str(status)
            raise CudaError(f"{function.__name__}: {message}")

    def scan(self, size, target):
        validate_scan(size, target)
        if self._context is None:
            raise CudaError("Open the CUDA scanner before using it.")
        candidate_count, target_label, match = ct.c_uint32(size), ct.c_uint32(target), ct.c_uint32()
        arguments = (ct.c_void_p * 3)(
            ct.addressof(candidate_count), ct.addressof(target_label), ct.addressof(self._match_buffer)
        )
        blocks = (size + THREADS_PER_BLOCK - 1) // THREADS_PER_BLOCK
        self._call(self._reset, self._match_buffer, NO_MATCH, 1)
        self._call(
            self._launch, self._kernel, blocks, 1, 1, THREADS_PER_BLOCK, 1, 1, 0, None, arguments, None
        )
        self._call(self._copy, ct.byref(match), self._match_buffer, ct.sizeof(match))
        return None if match.value == NO_MATCH else match.value
