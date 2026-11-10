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
    if service not in {"analysis", "events", "portal"}:
        raise SystemExit("TERRAMIND_SERVICE must be analysis, events or portal")
    if (
        service == "portal"
        and os.environ.get("PORTAL_AUTH_MODE", "demo") == "demo"
        and os.environ.get("HOST", "127.0.0.1") not in {"127.0.0.1", "localhost", "::1"}
    ):
        raise SystemExit("Demo portal must bind to loopback")
    uvicorn.run(
        {
            "analysis": "terramind.api.app:app",
            "events": "terramind.events.app:app",
            "portal": "terramind.portal.app:app",
        }[service],
        host=os.environ.get("HOST", "127.0.0.1"),
        port=port,
        access_log=False,
        proxy_headers=False,
        server_header=False,
    )


if __name__ == "__main__":
    main()
