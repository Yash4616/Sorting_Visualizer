import time
import threading
from typing import Callable
from .base import SortAlgorithm, SortStep, SortResult

class QuickSort(SortAlgorithm):
    name = "Quick Sort"

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

        def partition(low: int, high: int) -> int:
            nonlocal comparisons, swaps, step
            self.ensure_not_cancelled(cancelled_event)

            # Median-of-three pivot
            mid = low + (high - low) // 2

            comparisons += 1
            self.emit_step(
                on_step=on_step,
                cancelled_event=cancelled_event,
                arr=values,
                comparing=[low, mid],
                swapped=False,
                step_number=step,
                comparisons=comparisons,
                swaps=swaps,
            )
            step += 1
            if values[mid] < values[low]:
                values[low], values[mid] = values[mid], values[low]
                swaps += 1
                self.emit_step(
                    on_step=on_step,
                    cancelled_event=cancelled_event,
                    arr=values,
                    comparing=[low, mid],
                    swapped=True,
                    step_number=step,
                    comparisons=comparisons,
                    swaps=swaps,
                )
                step += 1

            comparisons += 1
            self.emit_step(
                on_step=on_step,
                cancelled_event=cancelled_event,
                arr=values,
                comparing=[low, high],
                swapped=False,
                step_number=step,
                comparisons=comparisons,
                swaps=swaps,
            )
            step += 1
            if values[high] < values[low]:
                values[low], values[high] = values[high], values[low]
                swaps += 1
                self.emit_step(
                    on_step=on_step,
                    cancelled_event=cancelled_event,
                    arr=values,
                    comparing=[low, high],
                    swapped=True,
                    step_number=step,
                    comparisons=comparisons,
                    swaps=swaps,
                )
                step += 1

            comparisons += 1
            self.emit_step(
                on_step=on_step,
                cancelled_event=cancelled_event,
                arr=values,
                comparing=[mid, high],
                swapped=False,
                step_number=step,
                comparisons=comparisons,
                swaps=swaps,
            )
            step += 1
            if values[mid] < values[high]:
                values[mid], values[high] = values[high], values[mid]
                swaps += 1
                self.emit_step(
                    on_step=on_step,
                    cancelled_event=cancelled_event,
                    arr=values,
                    comparing=[mid, high],
                    swapped=True,
                    step_number=step,
                    comparisons=comparisons,
                    swaps=swaps,
                )
                step += 1

            pivot = values[high]
            i = low - 1

            for j in range(low, high):
                self.ensure_not_cancelled(cancelled_event)
                comparisons += 1
                self.emit_step(
                    on_step=on_step,
                    cancelled_event=cancelled_event,
                    arr=values,
                    comparing=[j, high],
                    swapped=False,
                    step_number=step,
                    comparisons=comparisons,
                    swaps=swaps,
                )
                step += 1

                if values[j] <= pivot:
                    i += 1
                    if i != j:
                        values[i], values[j] = values[j], values[i]
                        swaps += 1
                        self.emit_step(
                            on_step=on_step,
                            cancelled_event=cancelled_event,
                            arr=values,
                            comparing=[i, j],
                            swapped=True,
                            step_number=step,
                            comparisons=comparisons,
                            swaps=swaps,
                        )
                        step += 1

            values[i + 1], values[high] = values[high], values[i + 1]
            swaps += 1
            self.emit_step(
                on_step=on_step,
                cancelled_event=cancelled_event,
                arr=values,
                comparing=[i + 1, high],
                swapped=True,
                step_number=step,
                comparisons=comparisons,
                swaps=swaps,
            )
            step += 1

            # Explicitly emit pivot placement confirmation.
            self.emit_step(
                on_step=on_step,
                cancelled_event=cancelled_event,
                arr=values,
                comparing=[i + 1],
                swapped=False,
                step_number=step,
                comparisons=comparisons,
                swaps=swaps,
            )
            step += 1
            return i + 1

        stack = []
        if n > 0:
            stack.append((0, n - 1))

        while stack:
            self.ensure_not_cancelled(cancelled_event)
            low, high = stack.pop()
            if low < high:
                p = partition(low, high)
                # push larger sub-array first to minimize stack depth
                if p - low < high - p:
                    stack.append((p + 1, high))
                    stack.append((low, p - 1))
                else:
                    stack.append((low, p - 1))
                    stack.append((p + 1, high))

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
