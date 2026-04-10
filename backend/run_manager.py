from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Iterable, Literal

from backend.sorting.algorithms import ALGORITHM_MAP, CancelledError
from backend.sorting.algorithms.base import SortResult, SortStep
from backend.sorting.array_generator import ArrayGenerator
from backend.sorting.complexity import COMPLEXITY_MAP


RunStatus = Literal["running", "completed", "cancelled", "failed"]

MAX_STEPS_PER_PULL = 240
DEFAULT_PULL_LIMIT = 120
UI_MIN_ARRAY_SIZE = 20
UI_MAX_ARRAY_SIZE = 50
UI_ARRAY_SIZE_STEP = 10
STEP_BUFFER_LIMIT = 10_000
RUN_TIMEOUT_SECONDS = 60
RUN_RETENTION_SECONDS = 5 * 60
REAPER_INTERVAL_SECONDS = 15


@dataclass
class RunState:
    """Mutable run state stored in the global run registry."""

    run_id: str
    algorithm: str
    array_size: int
    input_type: str
    seed: int
    status: RunStatus = "running"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    steps: list[dict[str, Any]] = field(default_factory=list)
    result: dict[str, Any] | None = None
    error: str | None = None
    cancel_event: threading.Event = field(default_factory=threading.Event, repr=False)
    worker: threading.Thread | None = field(default=None, repr=False)
    watchdog: threading.Thread | None = field(default=None, repr=False)


class StepBufferOverflowError(RuntimeError):
    """Raised when a run exceeds the configured step buffer size."""


_RUNS: dict[str, RunState] = {}
_RUNS_LOCK = threading.Lock()
_REAPER_THREAD: threading.Thread | None = None


def _now() -> float:
    return time.time()


def _is_terminal(status: RunStatus) -> bool:
    return status in {"completed", "cancelled", "failed"}


def _serialize_step(step: SortStep) -> dict[str, Any]:
    return {
        "array": step.array,
        "comparing": step.comparing,
        "swapped": step.swapped,
        "stepNumber": step.step_number + 1,
        "algorithm": step.algorithm,
        "comparisons": step.comparisons,
        "swaps": step.swaps,
    }


def _serialize_result(run: RunState, result: SortResult, final_array: list[int]) -> dict[str, Any]:
    correct = final_array == sorted(final_array)
    complexity = COMPLEXITY_MAP.get(run.algorithm, {}).get("avg", "N/A")
    return {
        "algorithm": result.algorithm,
        "arraySize": result.array_size,
        "inputType": run.input_type,
        "durationMs": round(result.duration_ms, 4),
        "comparisons": result.comparisons,
        "swaps": result.swaps,
        "steps": result.steps,
        "correct": correct,
        "complexity": complexity,
    }


def _reaper_loop() -> None:
    while True:
        time.sleep(REAPER_INTERVAL_SECONDS)
        cutoff = _now() - RUN_RETENTION_SECONDS
        with _RUNS_LOCK:
            stale_ids = [
                run_id
                for run_id, run in _RUNS.items()
                if _is_terminal(run.status) and run.updated_at <= cutoff
            ]
            for run_id in stale_ids:
                _RUNS.pop(run_id, None)


def _ensure_reaper_thread() -> None:
    global _REAPER_THREAD
    if _REAPER_THREAD and _REAPER_THREAD.is_alive():
        return
    with _RUNS_LOCK:
        if _REAPER_THREAD and _REAPER_THREAD.is_alive():
            return
        _REAPER_THREAD = threading.Thread(
            target=_reaper_loop,
            name="sort-run-reaper",
            daemon=True,
        )
        _REAPER_THREAD.start()


def _run_timeout_watchdog(run_id: str) -> None:
    with _RUNS_LOCK:
        run = _RUNS.get(run_id)
        worker = run.worker if run else None

    if run is None or worker is None:
        return

    worker.join(RUN_TIMEOUT_SECONDS)
    if not worker.is_alive():
        return

    with _RUNS_LOCK:
        active = _RUNS.get(run_id)
        if active is None or _is_terminal(active.status):
            return
        active.status = "failed"
        active.error = "timeout"
        active.updated_at = _now()
        active.cancel_event.set()


def _execute_run(run_id: str) -> None:
    with _RUNS_LOCK:
        run = _RUNS.get(run_id)
        if run is None:
            return
        algorithm_name = run.algorithm
        input_type = run.input_type
        array_size = run.array_size
        seed = run.seed

    try:
        source = ArrayGenerator.generate(size=array_size, input_type=input_type, seed=seed)
        working = source.copy()
        algorithm = ALGORITHM_MAP[algorithm_name]()

        def on_step(step: SortStep) -> None:
            append_steps(run_id=run_id, steps=[step])

        result = algorithm.sort_steps(
            arr=working,
            on_step=on_step,
            cancelled_event=run.cancel_event,
        )
        finalize_run(
            run_id=run_id,
            status="completed",
            result=result,
            final_array=working,
        )
    except StepBufferOverflowError:
        # finalize_run already handled in append_steps.
        return
    except CancelledError:
        with _RUNS_LOCK:
            active = _RUNS.get(run_id)
            if active is None or _is_terminal(active.status):
                return
        finalize_run(run_id=run_id, status="cancelled")
    except Exception as exc:
        finalize_run(run_id=run_id, status="failed", error=str(exc))


def _normalize_input_display(input_type: str) -> str:
    key = ArrayGenerator.normalize_input_type(input_type)
    return ArrayGenerator.DISPLAY_NAMES[key]


def create_run(algorithm: str, input_type: str, array_size: int) -> RunState:
    """Create and start a new sorting run.

    Args:
        algorithm: Canonical algorithm display name.
        input_type: Canonical input type display name.
        array_size: Number of elements to sort.

    Returns:
        Newly created ``RunState``.

    Raises:
        ValueError: If any input is invalid.
    """
    if algorithm not in ALGORITHM_MAP:
        raise ValueError(f"Unknown algorithm: {algorithm}")

    try:
        normalized_size = int(array_size)
    except (TypeError, ValueError) as exc:
        raise ValueError("arraySize must be an integer") from exc

    if normalized_size < UI_MIN_ARRAY_SIZE or normalized_size > UI_MAX_ARRAY_SIZE:
        raise ValueError(f"arraySize must be between {UI_MIN_ARRAY_SIZE} and {UI_MAX_ARRAY_SIZE}")

    if (normalized_size - UI_MIN_ARRAY_SIZE) % UI_ARRAY_SIZE_STEP != 0:
        raise ValueError(
            f"arraySize must increase by {UI_ARRAY_SIZE_STEP} (allowed: 20, 30, 40, 50)"
        )

    normalized_input = _normalize_input_display(input_type)
    run_id = str(uuid.uuid4())
    seed = ArrayGenerator.seed_from_run_id(run_id)

    run = RunState(
        run_id=run_id,
        algorithm=algorithm,
        array_size=normalized_size,
        input_type=normalized_input,
        seed=seed,
    )

    _ensure_reaper_thread()

    worker = threading.Thread(target=_execute_run, args=(run.run_id,), name=f"sort-run-{run.run_id}")
    worker.daemon = True
    watchdog = threading.Thread(
        target=_run_timeout_watchdog,
        args=(run.run_id,),
        name=f"sort-watchdog-{run.run_id}",
    )
    watchdog.daemon = True
    run.worker = worker
    run.watchdog = watchdog

    with _RUNS_LOCK:
        _RUNS[run.run_id] = run

    worker.start()
    watchdog.start()
    return run


def get_run(run_id: str) -> RunState:
    """Fetch a run by id.

    Args:
        run_id: Run identifier.

    Returns:
        The matching ``RunState``.

    Raises:
        KeyError: If the run does not exist.
    """
    with _RUNS_LOCK:
        run = _RUNS.get(run_id)
        if run is None:
            raise KeyError(f"Run not found: {run_id}")
        run.updated_at = _now()
        return run


def append_steps(run_id: str, steps: Iterable[SortStep]) -> None:
    """Append generated steps to a run's in-memory step buffer.

    Args:
        run_id: Run identifier.
        steps: Iterable of ``SortStep`` objects to append.

    Raises:
        KeyError: If the run does not exist.
        CancelledError: If the run is no longer active.
        StepBufferOverflowError: If the step buffer exceeds ``STEP_BUFFER_LIMIT``.
    """
    serialized_steps = [_serialize_step(step) for step in steps]
    if not serialized_steps:
        return

    with _RUNS_LOCK:
        run = _RUNS.get(run_id)
        if run is None:
            raise KeyError(f"Run not found: {run_id}")
        if run.status != "running":
            raise CancelledError("run is no longer active")

        required = len(run.steps) + len(serialized_steps)
        if required > STEP_BUFFER_LIMIT:
            run.status = "failed"
            run.error = f"step buffer limit exceeded ({STEP_BUFFER_LIMIT})"
            run.updated_at = _now()
            run.cancel_event.set()
            raise StepBufferOverflowError(run.error)

        run.steps.extend(serialized_steps)
        run.updated_at = _now()


def cancel_run(run_id: str) -> dict[str, Any]:
    """Cancel a run if it is still active.

    Args:
        run_id: Run identifier.

    Returns:
        JSON-ready cancellation payload.

    Raises:
        KeyError: If the run does not exist.
    """
    with _RUNS_LOCK:
        run = _RUNS.get(run_id)
        if run is None:
            raise KeyError(f"Run not found: {run_id}")

        if not _is_terminal(run.status):
            run.status = "cancelled"
            run.cancel_event.set()
            run.updated_at = _now()

        return {"runId": run.run_id, "status": run.status}


def finalize_run(
    run_id: str,
    status: RunStatus,
    result: SortResult | None = None,
    error: str | None = None,
    final_array: list[int] | None = None,
) -> None:
    """Finalize a run as completed, failed, or cancelled.

    Args:
        run_id: Run identifier.
        status: Target terminal status.
        result: Optional ``SortResult`` when status is ``completed``.
        error: Optional error message when status is ``failed``.
        final_array: Final sorted array used for correctness verification.
    """
    with _RUNS_LOCK:
        run = _RUNS.get(run_id)
        if run is None or _is_terminal(run.status):
            return

        run.updated_at = _now()

        if status == "completed":
            if result is None or final_array is None:
                run.status = "failed"
                run.error = "internal error: missing final result"
                run.cancel_event.set()
                return
            run.status = "completed"
            run.result = _serialize_result(run=run, result=result, final_array=final_array)
            run.error = None
            return

        if status == "cancelled":
            run.status = "cancelled"
            run.cancel_event.set()
            if error:
                run.error = error
            return

        run.status = "failed"
        run.error = error or "internal server error"
        run.cancel_event.set()


def list_runs() -> list[dict[str, Any]]:
    """List all runs currently retained in memory.

    Returns:
        List of JSON-ready run summaries.
    """
    with _RUNS_LOCK:
        return [
            {
                "runId": run.run_id,
                "status": run.status,
                "algorithm": run.algorithm,
                "arraySize": run.array_size,
                "inputType": run.input_type,
                "createdAt": run.created_at,
                "updatedAt": run.updated_at,
                "totalSteps": len(run.steps),
            }
            for run in _RUNS.values()
        ]


def active_run_count() -> int:
    """Return count of currently running jobs."""
    with _RUNS_LOCK:
        return sum(1 for run in _RUNS.values() if run.status == "running")


def poll_run(run_id: str, cursor: int, limit: int = DEFAULT_PULL_LIMIT) -> dict[str, Any]:
    """Return paginated run state and step slices for polling clients."""
    safe_cursor = max(0, int(cursor))
    safe_limit = max(1, min(MAX_STEPS_PER_PULL, int(limit)))

    with _RUNS_LOCK:
        run = _RUNS.get(run_id)
        if run is None:
            raise KeyError(f"Run not found: {run_id}")

        total_steps = len(run.steps)
        next_cursor = min(total_steps, safe_cursor + safe_limit)
        payload_steps = run.steps[safe_cursor:next_cursor]
        has_more = (next_cursor < total_steps) or (run.status == "running")
        run.updated_at = _now()

        return {
            "runId": run.run_id,
            "status": run.status,
            "steps": payload_steps,
            "nextCursor": next_cursor,
            "totalSteps": total_steps,
            "hasMore": has_more,
            "result": run.result if run.status == "completed" else None,
            "error": run.error if run.status == "failed" else None,
        }


def config_payload() -> dict[str, Any]:
    """Return the backend configuration used by the frontend UI."""
    return {
        "algorithms": list(ALGORITHM_MAP.keys()),
        "inputTypes": [ArrayGenerator.DISPLAY_NAMES[key] for key in ArrayGenerator.INPUT_TYPES],
        "arraySize": {
            "min": UI_MIN_ARRAY_SIZE,
            "max": UI_MAX_ARRAY_SIZE,
            "step": UI_ARRAY_SIZE_STEP,
            "default": 50,
        },
        "complexity": COMPLEXITY_MAP,
    }


class SortRunManager:
    """Compatibility wrapper around module-level run manager functions."""

    def __init__(self) -> None:
        _ensure_reaper_thread()

    def start_run(self, algorithm: str, array_size: int, input_type: str) -> RunState:
        return create_run(algorithm=algorithm, array_size=array_size, input_type=input_type)

    def get_run(self, run_id: str) -> RunState:
        return get_run(run_id)

    def poll_run(self, run_id: str, cursor: int, limit: int = DEFAULT_PULL_LIMIT) -> dict[str, Any]:
        return poll_run(run_id=run_id, cursor=cursor, limit=limit)

    def cancel_run(self, run_id: str) -> dict[str, Any]:
        return cancel_run(run_id)

    def list_runs(self) -> list[dict[str, Any]]:
        return list_runs()

    def config_payload(self) -> dict[str, Any]:
        return config_payload()


__all__ = [
    "DEFAULT_PULL_LIMIT",
    "MAX_STEPS_PER_PULL",
    "RUN_TIMEOUT_SECONDS",
    "RUN_RETENTION_SECONDS",
    "STEP_BUFFER_LIMIT",
    "UI_MIN_ARRAY_SIZE",
    "UI_MAX_ARRAY_SIZE",
    "UI_ARRAY_SIZE_STEP",
    "RunState",
    "SortRunManager",
    "active_run_count",
    "append_steps",
    "cancel_run",
    "config_payload",
    "create_run",
    "finalize_run",
    "get_run",
    "list_runs",
    "poll_run",
]
