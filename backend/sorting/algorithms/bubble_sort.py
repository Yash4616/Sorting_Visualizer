import time
import threading
from typing import Callable

from .base import SortAlgorithm, SortResult, SortStep

class BubbleSort(SortAlgorithm):
    """Optimized Bubble Sort with early exit."""

    name = "Bubble Sort"

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
            swapped_this_pass = False
            for j in range(n - i - 1):
                self.ensure_not_cancelled(cancelled_event)
                comparisons += 1
                did_swap = values[j] > values[j + 1]
                if did_swap:
                    values[j], values[j + 1] = values[j + 1], values[j]
                    swaps += 1
                    swapped_this_pass = True

                self.emit_step(
                    on_step=on_step,
                    cancelled_event=cancelled_event,
                    arr=values,
                    comparing=[j, j + 1],
                    swapped=did_swap,
                    step_number=step,
                    comparisons=comparisons,
                    swaps=swaps,
                )
                step += 1

            if not swapped_this_pass:
                break

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
