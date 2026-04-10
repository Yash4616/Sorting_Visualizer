import time
import threading
from typing import Callable
from .base import SortAlgorithm, SortStep, SortResult

class InsertionSort(SortAlgorithm):
    name = "Insertion Sort"

    def sort_steps(
        self,
        arr: list[int],
        on_step: Callable[[SortStep], None],
        cancelled_event: threading.Event,
    ) -> SortResult:
        values = arr
        n = len(values)
        comparisons = swaps = step = 0
        start = time.perf_counter()
        original_sorted = sorted(values)

        for i in range(1, n):
            self.ensure_not_cancelled(cancelled_event)
            key = values[i]
            j = i - 1

            while j >= 0:
                self.ensure_not_cancelled(cancelled_event)
                comparisons += 1
                self.emit_step(
                    on_step=on_step,
                    cancelled_event=cancelled_event,
                    arr=values,
                    comparing=[j, j + 1],
                    swapped=False,
                    step_number=step,
                    comparisons=comparisons,
                    swaps=swaps,
                )
                step += 1

                if values[j] > key:
                    values[j + 1] = values[j]
                    swaps += 1
                    self.emit_step(
                        on_step=on_step,
                        cancelled_event=cancelled_event,
                        arr=values,
                        comparing=[j, j + 1],
                        swapped=True,
                        step_number=step,
                        comparisons=comparisons,
                        swaps=swaps,
                    )
                    step += 1
                    j -= 1
                else:
                    break

            insert_index = j + 1
            values[insert_index] = key
            if insert_index != i:
                swaps += 1
                self.emit_step(
                    on_step=on_step,
                    cancelled_event=cancelled_event,
                    arr=values,
                    comparing=[insert_index, i],
                    swapped=True,
                    step_number=step,
                    comparisons=comparisons,
                    swaps=swaps,
                )
                step += 1

        duration_ms = (time.perf_counter() - start) * 1000
        return SortResult(
            algorithm=self.name,
            array_size=len(values),
            input_type="",
            duration_ms=duration_ms,
            comparisons=comparisons,
            swaps=swaps,
            steps=step,
            correct=(values == original_sorted)
        )
