"""Production entry point. Raw URL access logging is deliberately disabled."""

import os

import uvicorn


def main() -> None:
    try:
        port = int(os.environ.get("PORT", "8080"))
    except ValueError:
        raise SystemExit("PORT must be an integer between 1 and 65535") from None
    if not 1 <= port <= 65535:
        raise SystemExit("PORT must be an integer between 1 and 65535")
    service = os.environ.get("TERRAMIND_SERVICE", "analysis")
    if service not in {"analysis", "events"}:
        raise SystemExit("TERRAMIND_SERVICE must be analysis or events")
    uvicorn.run(
        "terramind.events.app:app" if service == "events" else "terramind.api.app:app",
        host=os.environ.get("HOST", "127.0.0.1"),
        port=port,
        access_log=False,
        proxy_headers=False,
        server_header=False,
    )


if __name__ == "__main__":
    main()
