"""Shared dataclasses and base class for sorting algorithm implementations."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class SortStep:
    """Represents one visualizable sorting step."""

    array: list[int]
    comparing: list[int]
    swapped: bool
    step_number: int
    algorithm: str
    comparisons: int = 0
    swaps: int = 0


@dataclass
class SortResult:
    """Represents the final result of a sorting run."""

    algorithm: str
    array_size: int
    input_type: str
    duration_ms: float
    comparisons: int
    swaps: int
    steps: int
    correct: bool


class CancelledError(RuntimeError):
    """Raised when a sorting run is cancelled or timed out."""


StepHandler = Callable[[SortStep], None]


class SortAlgorithm:
    """Base class for sorting algorithms that emit visualization steps."""

    name: str = "Base"

    def sort_steps(
        self,
        arr: list[int],
        on_step: StepHandler,
        cancelled_event: threading.Event,
    ) -> SortResult:
        """Sort input values and emit intermediate steps to ``on_step``."""
        raise NotImplementedError

    @staticmethod
    def ensure_not_cancelled(cancelled_event: threading.Event) -> None:
        """Raise ``CancelledError`` when the run has been cancelled."""
        if cancelled_event.is_set():
            raise CancelledError("cancelled")

    def emit_step(
        self,
        on_step: StepHandler,
        cancelled_event: threading.Event,
        arr: list[int],
        comparing: list[int],
        swapped: bool,
        step_number: int,
        comparisons: int,
        swaps: int,
    ) -> None:
        """Emit one immutable step snapshot after cancellation checks."""
        self.ensure_not_cancelled(cancelled_event)
        on_step(
            self._make_step(
                arr=arr,
                comparing=comparing,
                swapped=swapped,
                step_number=step_number,
                comparisons=comparisons,
                swaps=swaps,
            )
        )

    def _make_step(
        self,
        arr: list[int],
        comparing: list[int],
        swapped: bool,
        step_number: int,
        comparisons: int = 0,
        swaps: int = 0,
    ) -> SortStep:
        """Construct an immutable step snapshot for UI transport."""
        return SortStep(
            array=arr.copy(),
            comparing=comparing.copy(),
            swapped=swapped,
            step_number=step_number,
            algorithm=self.name,
            comparisons=comparisons,
            swaps=swaps,
        )
