from __future__ import annotations

from http import HTTPStatus
from typing import Any

from flask import Blueprint, jsonify, request

from backend.run_manager import (
    MAX_STEPS_PER_PULL,
    SortRunManager,
    UI_ARRAY_SIZE_STEP,
    UI_MAX_ARRAY_SIZE,
    UI_MIN_ARRAY_SIZE,
    active_run_count,
)


def _json_error(message: str, status: int) -> tuple[Any, int]:
    return jsonify({"error": message}), status


def _parse_non_negative_int(raw: str, field_name: str) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer") from exc
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return value


def _parse_limit(raw: str) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("limit must be an integer") from exc
    if value < 1 or value > MAX_STEPS_PER_PULL:
        raise ValueError(f"limit must be between 1 and {MAX_STEPS_PER_PULL}")
    return value


def create_api_blueprint(run_manager: SortRunManager) -> Blueprint:
    api = Blueprint("api", __name__, url_prefix="/api")

    @api.errorhandler(Exception)
    def handle_api_exception(_: Exception) -> tuple[Any, int]:
        return _json_error("internal server error", HTTPStatus.INTERNAL_SERVER_ERROR)

    @api.get("/health")
    def health() -> tuple[Any, int]:
        return jsonify({"status": "ok", "runs": active_run_count()}), HTTPStatus.OK

    @api.get("/config")
    def config() -> tuple[Any, int]:
        return jsonify(run_manager.config_payload()), HTTPStatus.OK

    @api.post("/runs")
    def create_run() -> tuple[Any, int]:
        if not request.is_json:
            return _json_error("request must be application/json", HTTPStatus.BAD_REQUEST)

        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return _json_error("request body must be a JSON object", HTTPStatus.BAD_REQUEST)

        algorithm = payload.get("algorithm")
        array_size = payload.get("arraySize")
        input_type = payload.get("inputType")

        if not isinstance(algorithm, str) or not algorithm.strip():
            return _json_error("algorithm must be a non-empty string", HTTPStatus.BAD_REQUEST)

        if not isinstance(input_type, str) or not input_type.strip():
            return _json_error("inputType must be a non-empty string", HTTPStatus.BAD_REQUEST)

        if not isinstance(array_size, int) or isinstance(array_size, bool):
            return _json_error("arraySize must be an integer", HTTPStatus.BAD_REQUEST)

        if array_size < UI_MIN_ARRAY_SIZE or array_size > UI_MAX_ARRAY_SIZE:
            return _json_error(
                f"arraySize must be between {UI_MIN_ARRAY_SIZE} and {UI_MAX_ARRAY_SIZE}",
                HTTPStatus.BAD_REQUEST,
            )

        if (array_size - UI_MIN_ARRAY_SIZE) % UI_ARRAY_SIZE_STEP != 0:
            return _json_error(
                f"arraySize must increase by {UI_ARRAY_SIZE_STEP} (allowed: 20, 30, 40, 50)",
                HTTPStatus.BAD_REQUEST,
            )

        config_payload = run_manager.config_payload()
        known_algorithms = set(config_payload["algorithms"])
        known_input_types = set(config_payload["inputTypes"])

        if algorithm not in known_algorithms:
            return _json_error("algorithm must be one of the configured algorithms", HTTPStatus.BAD_REQUEST)

        if input_type not in known_input_types:
            return _json_error("inputType must be one of the configured input types", HTTPStatus.BAD_REQUEST)

        try:
            run = run_manager.start_run(algorithm=algorithm, array_size=int(array_size), input_type=input_type)
        except ValueError as exc:
            return _json_error(str(exc), HTTPStatus.BAD_REQUEST)

        return jsonify({"runId": run.run_id}), HTTPStatus.CREATED

    @api.get("/runs/<run_id>")
    def get_run(run_id: str) -> tuple[Any, int]:
        cursor_raw = request.args.get("cursor", default="0")
        limit_raw = request.args.get("limit", default="120")

        try:
            cursor = _parse_non_negative_int(cursor_raw, "cursor")
            limit = _parse_limit(limit_raw)
        except ValueError as exc:
            return _json_error(str(exc), HTTPStatus.BAD_REQUEST)

        try:
            payload = run_manager.poll_run(run_id, cursor=cursor, limit=limit)
        except KeyError:
            return _json_error("Run not found", HTTPStatus.NOT_FOUND)

        total_steps = int(payload.get("totalSteps", 0))
        next_cursor = int(payload.get("nextCursor", 0))
        status = str(payload.get("status", "failed"))
        payload["hasMore"] = (next_cursor < total_steps) or (status == "running")

        if status != "completed":
            payload["result"] = None
        if status != "failed":
            payload["error"] = None

        return jsonify(payload), HTTPStatus.OK

    @api.post("/runs/<run_id>/cancel")
    def cancel_run(run_id: str) -> tuple[Any, int]:
        try:
            payload = run_manager.cancel_run(run_id)
        except KeyError:
            return _json_error("Run not found", HTTPStatus.NOT_FOUND)

        return jsonify(payload), HTTPStatus.OK

    return api
