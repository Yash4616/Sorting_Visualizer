import argparse
import platform
import sys

from backend import create_app
from waitress import serve


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5000
DEFAULT_WORKERS = 4

def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the Flask API server."""
    parser = argparse.ArgumentParser(description="Sorting Visualizer Web Backend")
    parser.add_argument(
        "--host",
        type=str,
        default=DEFAULT_HOST,
        help=f"Flask bind host (default: {DEFAULT_HOST})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Flask bind port (default: {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable Flask debug mode",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=f"Waitress worker threads in production (default: {DEFAULT_WORKERS})",
    )
    return parser.parse_args()


def print_startup_banner(host: str, port: int, debug: bool, workers: int) -> None:
    """Print a consistent startup banner for local and production runs."""
    mode = "development" if debug else "production"
    python_version = platform.python_version()
    lines = [
        "=" * 64,
        "Sorting Visualizer Backend",
        f"Mode    : {mode}",
        f"Host    : {host}",
        f"Port    : {port}",
        f"Workers : {workers if not debug else 'threaded dev server'}",
        f"Python  : {python_version} ({sys.executable})",
        "=" * 64,
    ]
    print("\n".join(lines))


def main() -> None:
    """Start the Flask backend server."""
    args = parse_args()
    workers = max(1, int(args.workers))
    app = create_app(
        {
            "DEBUG": bool(args.debug),
            "SERVE_FRONTEND": not bool(args.debug),
        }
    )

    print_startup_banner(host=args.host, port=args.port, debug=args.debug, workers=workers)

    if args.debug:
        app.run(host=args.host, port=args.port, debug=True, threaded=True)
        return

    serve(app, host=args.host, port=args.port, threads=workers)

if __name__ == "__main__":
    main()
