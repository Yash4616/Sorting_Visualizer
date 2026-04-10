"""Big-O complexity metadata for supported algorithms."""

from __future__ import annotations

COMPLEXITY_MAP: dict[str, dict[str, str]] = {
    "Bubble Sort": {
        "avg": "O(N^2)",
        "best": "O(N)",
        "worst": "O(N^2)",
        "space": "O(1)",
    },
    "Selection Sort": {
        "avg": "O(N^2)",
        "best": "O(N^2)",
        "worst": "O(N^2)",
        "space": "O(1)",
    },
    "Insertion Sort": {
        "avg": "O(N^2)",
        "best": "O(N)",
        "worst": "O(N^2)",
        "space": "O(1)",
    },
    "Merge Sort": {
        "avg": "O(N log N)",
        "best": "O(N log N)",
        "worst": "O(N log N)",
        "space": "O(N)",
    },
    "Quick Sort": {
        "avg": "O(N log N)",
        "best": "O(N log N)",
        "worst": "O(N^2)",
        "space": "O(log N)",
    },
    "Heap Sort": {
        "avg": "O(N log N)",
        "best": "O(N log N)",
        "worst": "O(N log N)",
        "space": "O(1)",
    },
}
