extern "C" __global__ void scan_synthetic_labels(
    unsigned int size, unsigned int target, unsigned int* match
) {
    const unsigned int candidate = blockIdx.x * blockDim.x + threadIdx.x;
    if (candidate >= size) {
        return;
    }

    const unsigned int word = (candidate * 0x7C4D1u + 0x1A39Bu) & 0xFFFFFu;
    const unsigned int label = word ^ (word >> 9);
    if (label == target) {
        atomicMin(match, candidate);
    }
}
