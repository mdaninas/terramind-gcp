import pytest

from terramind.api.__main__ import main


@pytest.mark.parametrize("port", ["bad", "0", "65536", "-1"])
def test_invalid_port(monkeypatch, port):
    monkeypatch.setenv("PORT", port)
    with pytest.raises(SystemExit, match="PORT must be an integer"):
        main()


def test_server_respects_cloud_run_port_and_disables_access_logs(monkeypatch):
    captured = {}
    monkeypatch.delenv("HOST", raising=False)
    monkeypatch.setenv("PORT", "9090")
    monkeypatch.setattr(
        "terramind.api.__main__.uvicorn.run", lambda *args, **kwargs: captured.update(kwargs)
    )
    main()
    assert captured["port"] == 9090
    assert captured["host"] == "127.0.0.1"
    assert captured["access_log"] is False
    assert captured["proxy_headers"] is False
