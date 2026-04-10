"""Deterministic input-array generation for sorting runs."""

from __future__ import annotations

import hashlib
import random

class ArrayGenerator:
    """Generates arrays for supported visualization input distributions."""

    MIN_SIZE: int = 20
    MAX_SIZE: int = 50

    INPUT_TYPES: tuple[str, ...] = (
        "RANDOM",
        "NEARLY_SORTED",
        "REVERSED",
        "FEW_UNIQUE",
    )

    DISPLAY_NAMES: dict[str, str] = {
        "RANDOM": "Random",
        "NEARLY_SORTED": "Nearly Sorted",
        "REVERSED": "Reversed",
        "FEW_UNIQUE": "Few Unique",
    }

    DISPLAY_TO_KEY: dict[str, str] = {
        display: key for key, display in DISPLAY_NAMES.items()
    }

    @classmethod
    def normalize_input_type(cls, input_type: str) -> str:
        """Normalize a user-facing input type into its canonical key."""
        display = input_type.strip()
        if display in cls.DISPLAY_TO_KEY:
            return cls.DISPLAY_TO_KEY[display]

        token = display.upper().replace(" ", "_")
        if token in cls.INPUT_TYPES:
            return token

        raise ValueError(
            f"Unknown input_type '{input_type}'. Expected one of: "
            f"{', '.join(cls.DISPLAY_TO_KEY.keys())}"
        )

    @staticmethod
    def seed_from_run_id(run_id: str) -> int:
        """Create a deterministic integer seed from a run identifier."""
        digest = hashlib.sha256(run_id.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], byteorder="big", signed=False)

    @classmethod
    def generate(cls, size: int, input_type: str, seed: int) -> list[int]:
        """Generate an array for the provided input type and deterministic seed."""
        bounded_size = max(cls.MIN_SIZE, min(cls.MAX_SIZE, int(size)))
        rng = random.Random(seed)
        key = cls.normalize_input_type(input_type)

        if key == "RANDOM":
            return [rng.randint(1, bounded_size * 3) for _ in range(bounded_size)]

        if key == "NEARLY_SORTED":
            arr = list(range(1, bounded_size + 1))
            swaps = max(1, bounded_size // 8)
            for _ in range(swaps):
                i = rng.randrange(0, bounded_size)
                j = rng.randrange(0, bounded_size)
                arr[i], arr[j] = arr[j], arr[i]
            return arr

        if key == "REVERSED":
            return list(range(bounded_size, 0, -1))

        if key == "FEW_UNIQUE":
            unique_count = max(3, min(7, bounded_size // 6 + 2))
            pool = [rng.randint(1, bounded_size) for _ in range(unique_count)]
            return [rng.choice(pool) for _ in range(bounded_size)]

        raise ValueError(f"Unsupported input_type key: {key}")
