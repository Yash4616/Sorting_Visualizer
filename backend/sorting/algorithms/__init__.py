"""Sorting algorithm registry used by the Flask run manager."""

from backend.sorting.complexity import COMPLEXITY_MAP

from .base import CancelledError, SortAlgorithm, SortResult, SortStep
from .bubble_sort import BubbleSort
from .heap_sort import HeapSort
from .insertion_sort import InsertionSort
from .merge_sort import MergeSort
from .quick_sort import QuickSort
from .selection_sort import SelectionSort

ALGORITHM_MAP: dict[str, type] = {
    BubbleSort.name: BubbleSort,
    SelectionSort.name: SelectionSort,
    InsertionSort.name: InsertionSort,
    MergeSort.name: MergeSort,
    HeapSort.name: HeapSort,
    QuickSort.name: QuickSort,
}

__all__ = [
    "CancelledError",
    "SortAlgorithm",
    "SortStep",
    "SortResult",
    "ALGORITHM_MAP",
    "COMPLEXITY_MAP",
]
