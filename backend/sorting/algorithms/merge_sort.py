import time
import threading
from typing import Callable
from .base import SortAlgorithm, SortStep, SortResult

class MergeSort(SortAlgorithm):
    name = "Merge Sort"

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
        temp = values.copy()

        def merge(left: int, mid: int, right: int):
            nonlocal comparisons, swaps, step
            self.ensure_not_cancelled(cancelled_event)

            for p in range(left, right + 1):
                temp[p] = values[p]

            i = left
            j = mid + 1

            for k in range(left, right + 1):
                self.ensure_not_cancelled(cancelled_event)

                if i > mid:
                    values[k] = temp[j]
                    swaps += 1
                    self.emit_step(
                        on_step=on_step,
                        cancelled_event=cancelled_event,
                        arr=values,
                        comparing=[k, j],
                        swapped=True,
                        step_number=step,
                        comparisons=comparisons,
                        swaps=swaps,
                    )
                    step += 1
                    j += 1
                    continue

                if j > right:
                    values[k] = temp[i]
                    swaps += 1
                    self.emit_step(
                        on_step=on_step,
                        cancelled_event=cancelled_event,
                        arr=values,
                        comparing=[k, i],
                        swapped=True,
                        step_number=step,
                        comparisons=comparisons,
                        swaps=swaps,
                    )
                    step += 1
                    i += 1
                    continue

                comparisons += 1
                self.emit_step(
                    on_step=on_step,
                    cancelled_event=cancelled_event,
                    arr=values,
                    comparing=[i, j],
                    swapped=False,
                    step_number=step,
                    comparisons=comparisons,
                    swaps=swaps,
                )
                step += 1

                if temp[i] <= temp[j]:
                    values[k] = temp[i]
                    swaps += 1
                    self.emit_step(
                        on_step=on_step,
                        cancelled_event=cancelled_event,
                        arr=values,
                        comparing=[k, i],
                        swapped=True,
                        step_number=step,
                        comparisons=comparisons,
                        swaps=swaps,
                    )
                    step += 1
                    i += 1
                else:
                    values[k] = temp[j]
                    swaps += 1
                    self.emit_step(
                        on_step=on_step,
                        cancelled_event=cancelled_event,
                        arr=values,
                        comparing=[k, j],
                        swapped=True,
                        step_number=step,
                        comparisons=comparisons,
                        swaps=swaps,
                    )
                    step += 1
                    j += 1

        def sort(left: int, right: int):
            self.ensure_not_cancelled(cancelled_event)
            if left < right:
                mid = left + (right - left) // 2
                sort(left, mid)
                sort(mid + 1, right)
                merge(left, mid, right)

        if n > 0:
            sort(0, n - 1)

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
