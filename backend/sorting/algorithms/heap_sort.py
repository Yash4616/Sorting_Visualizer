import time
import threading
from typing import Callable
from .base import SortAlgorithm, SortStep, SortResult

class HeapSort(SortAlgorithm):
    name = "Heap Sort"

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

        def heapify(length: int, i: int):
            nonlocal comparisons, swaps, step
            self.ensure_not_cancelled(cancelled_event)
            largest = i
            left = 2 * i + 1
            right = 2 * i + 2

            if left < length:
                self.ensure_not_cancelled(cancelled_event)
                comparisons += 1
                self.emit_step(
                    on_step=on_step,
                    cancelled_event=cancelled_event,
                    arr=values,
                    comparing=[left, largest],
                    swapped=False,
                    step_number=step,
                    comparisons=comparisons,
                    swaps=swaps,
                )
                step += 1
                if values[left] > values[largest]:
                    largest = left

            if right < length:
                self.ensure_not_cancelled(cancelled_event)
                comparisons += 1
                self.emit_step(
                    on_step=on_step,
                    cancelled_event=cancelled_event,
                    arr=values,
                    comparing=[right, largest],
                    swapped=False,
                    step_number=step,
                    comparisons=comparisons,
                    swaps=swaps,
                )
                step += 1
                if values[right] > values[largest]:
                    largest = right

            if largest != i:
                values[i], values[largest] = values[largest], values[i]
                swaps += 1
                self.emit_step(
                    on_step=on_step,
                    cancelled_event=cancelled_event,
                    arr=values,
                    comparing=[i, largest],
                    swapped=True,
                    step_number=step,
                    comparisons=comparisons,
                    swaps=swaps,
                )
                step += 1
                heapify(length, largest)

        # Build Max Heap
        for i in range(n // 2 - 1, -1, -1):
            self.ensure_not_cancelled(cancelled_event)
            heapify(n, i)

        # Extract elements
        for i in range(n - 1, 0, -1):
            self.ensure_not_cancelled(cancelled_event)
            values[0], values[i] = values[i], values[0]
            swaps += 1
            self.emit_step(
                on_step=on_step,
                cancelled_event=cancelled_event,
                arr=values,
                comparing=[0, i],
                swapped=True,
                step_number=step,
                comparisons=comparisons,
                swaps=swaps,
            )
            step += 1
            heapify(i, 0)

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
