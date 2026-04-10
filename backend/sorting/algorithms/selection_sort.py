import time
import threading
from typing import Callable

from .base import SortAlgorithm, SortResult, SortStep

class SelectionSort(SortAlgorithm):
    """Selection Sort implementation."""

    name = "Selection Sort"

    def sort_steps(
        self,
        arr: list[int],
        on_step: Callable[[SortStep], None],
        cancelled_event: threading.Event,
    ) -> SortResult:
        values = arr
        n = len(values)
        comparisons = 0
        swaps = 0
        step = 0
        start = time.perf_counter()
        original_sorted = sorted(values)

        for i in range(n):
            self.ensure_not_cancelled(cancelled_event)
            min_idx = i
            for j in range(i + 1, n):
                self.ensure_not_cancelled(cancelled_event)
                comparisons += 1
                self.emit_step(
                    on_step=on_step,
                    cancelled_event=cancelled_event,
                    arr=values,
                    comparing=[min_idx, j],
                    swapped=False,
                    step_number=step,
                    comparisons=comparisons,
                    swaps=swaps,
                )
                step += 1

                if values[j] < values[min_idx]:
                    min_idx = j

            if min_idx != i:
                values[i], values[min_idx] = values[min_idx], values[i]
                swaps += 1
                self.emit_step(
                    on_step=on_step,
                    cancelled_event=cancelled_event,
                    arr=values,
                    comparing=[i, min_idx],
                    swapped=True,
                    step_number=step,
                    comparisons=comparisons,
                    swaps=swaps,
                )
                step += 1

        duration_ms = (time.perf_counter() - start) * 1000.0
        return SortResult(
            algorithm=self.name,
            array_size=len(values),
            input_type="",
            duration_ms=duration_ms,
            comparisons=comparisons,
            swaps=swaps,
            steps=step,
            correct=(values == original_sorted),
        )
