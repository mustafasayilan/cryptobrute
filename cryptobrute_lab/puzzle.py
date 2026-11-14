LABEL_MASK = (1 << 20) - 1
MAX_CANDIDATES = LABEL_MASK + 1


def validate_scan(size, target):
    if not 1 <= size <= MAX_CANDIDATES:
        raise ValueError(f"Candidate count must be between 1 and {MAX_CANDIDATES}.")
    if not 0 <= target <= LABEL_MASK:
        raise ValueError("Target must be a 20-bit synthetic label.")


def synthetic_label(candidate):
    """Return the label from a fixed permutation of 20-bit integers."""
    word = (candidate * 0x7C4D1 + 0x1A39B) & LABEL_MASK
    return word ^ (word >> 9)


def make_puzzle(size, puzzle_number):
    validate_scan(size, 0)
    if not 0 <= puzzle_number <= 0xFFFFFFFF:
        raise ValueError("Puzzle number must be an unsigned 32-bit integer.")
    expected = ((puzzle_number * 0x9E3779B1 + 0x51ED270B) & 0xFFFFFFFF) % size
    return synthetic_label(expected), expected


def scan_cpu(size, target):
    validate_scan(size, target)
    match = None
    for candidate in range(size):
        if synthetic_label(candidate) == target:
            match = candidate
    return match
