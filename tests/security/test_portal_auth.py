import json
import time
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from google.auth import crypt, jwt

from scripts.check_public_files import main as check_public_files
from terramind.portal.app import create_app
from terramind.portal.oidc import GoogleOIDC, NoRedirect
from terramind.portal.settings import PortalSettings
from terramind.portal.store import PortalStore, owner_key


def settings(**changes):
    return PortalSettings(
        auth_mode="google",
        origin="https://portal.example.invalid",
        client_id="123-synthetic.apps.googleusercontent.com",
        client_secret="synthetic-client-secret",
        allowed_emails=("analyst@example.invalid",),
        **changes,
    )


def test_google_auth_request_has_fixed_redirect_state_nonce_and_pkce():
    provider = GoogleOIDC(settings())
    uri = provider.authorize("synthetic-state", "synthetic-nonce", "synthetic-verifier")
    parsed = urlsplit(uri)
    values = parse_qs(parsed.query)
    assert parsed.scheme == "https" and parsed.netloc == "accounts.google.com"
    assert values["redirect_uri"] == ["https://portal.example.invalid/auth/callback"]
    assert values["scope"] == ["openid email"]
    assert values["state"] == ["synthetic-state"] and values["nonce"] == ["synthetic-nonce"]
    assert values["code_challenge_method"] == ["S256"]
    assert "synthetic-verifier" not in uri
    assert "synthetic-client-secret" not in repr(provider.settings)


@pytest.fixture(scope="module")
def signing_key():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    public_pem = private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return crypt.RSASigner.from_string(private_pem, key_id="synthetic-key"), public_pem.decode()


@pytest.mark.parametrize(
    "failure",
    [
        "none",
        "signature",
        "issuer",
        "audience",
        "expired",
        "future",
        "nonce",
        "email",
        "unverified",
        "azp",
        "missing-sub",
    ],
)
def test_actual_google_auth_verifier_rejects_invalid_signed_claims(
    monkeypatch, signing_key, failure
):
    provider = GoogleOIDC(settings())
    now = int(time.time())
    claims = {
        "iss": "https://accounts.google.com",
        "aud": provider.settings.client_id,
        "iat": now,
        "exp": now + 300,
        "sub": "synthetic-subject",
        "nonce": "synthetic-nonce",
        "email": "analyst@example.invalid",
        "email_verified": True,
    }
    if failure == "issuer":
        claims["iss"] = "https://attacker.invalid"
    elif failure == "audience":
        claims["aud"] = "other-client.apps.googleusercontent.com"
    elif failure == "expired":
        claims["exp"] = now - 300
    elif failure == "future":
        claims["iat"] = now + 300
    elif failure == "nonce":
        claims["nonce"] = "another-browser"
    elif failure == "email":
        claims["email"] = "other@example.invalid"
    elif failure == "unverified":
        claims["email_verified"] = False
    elif failure == "azp":
        claims["azp"] = "other-client"
    elif failure == "missing-sub":
        claims.pop("sub")
    signer, public = signing_key
    token = jwt.encode(signer, claims).decode()
    if failure == "signature":
        prefix, signature = token.rsplit(".", 1)
        token = prefix + "." + ("A" if signature[0] != "A" else "B") + signature[1:]

    class TokenResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, bound):
            assert bound == 65537
            return json.dumps({"id_token": token}).encode()

    class TokenEndpoint:
        def open(self, request, timeout):
            assert request.full_url == "https://oauth2.googleapis.com/token" and timeout == 10
            values = parse_qs(request.data.decode())
            assert values["code_verifier"] == ["synthetic-verifier"]
            assert values["redirect_uri"] == [provider.settings.callback]
            return TokenResponse()

    def certificate_request(url, **kwargs):
        assert url == "https://www.googleapis.com/oauth2/v1/certs" and kwargs["timeout"] == 5
        return SimpleNamespace(status=200, data=json.dumps({"synthetic-key": public}).encode())

    monkeypatch.setattr("terramind.portal.oidc.build_opener", lambda handler: TokenEndpoint())
    monkeypatch.setattr(
        "google.auth.transport.requests.Request", lambda **kwargs: certificate_request
    )
    if failure == "none":
        assert provider.exchange(
            "synthetic-code", "synthetic-nonce", "synthetic-verifier"
        ) == owner_key("google", "synthetic-subject")
    else:
        with pytest.raises(ValueError, match="authentication failed"):
            provider.exchange("synthetic-code", "synthetic-nonce", "synthetic-verifier")


def test_secure_google_cookie_uses_host_prefix_and_no_demo_endpoint(tmp_path):
    config = settings(database=tmp_path / "private.sqlite3")
    database = PortalStore(config.database)
    with TestClient(create_app(config, database), base_url=config.origin) as client:
        response = client.get("/login")
        cookie = response.headers["set-cookie"]
        assert cookie.startswith("__Host-terramind_session=")
        assert "Secure" in cookie and "HttpOnly" in cookie and "Path=/" in cookie
        assert "Domain=" not in cookie
        assert "max-age" in response.headers["strict-transport-security"]
        assert client.post("/auth/demo").status_code == 404
    database.close()


@pytest.mark.parametrize(
    "origin",
    [
        "http://public.example.invalid",
        "https://portal.invalid/path",
        "https://name:password@portal.invalid",
        "https://portal.invalid?return=evil",
    ],
)
def test_invalid_origins_cannot_become_callback_or_cookie_destinations(origin):
    with pytest.raises(ValueError):
        PortalSettings(origin=origin)


def test_demo_accounts_and_cloud_analysis_fail_closed_outside_development(monkeypatch):
    with pytest.raises(ValueError):
        PortalSettings(origin="https://portal.invalid")
    with pytest.raises(ValueError):
        PortalSettings(analysis_mode="cloud")
    monkeypatch.setenv("K_SERVICE", "synthetic-cloud-run")
    with pytest.raises(ValueError):
        PortalSettings()
    assert (
        NoRedirect().redirect_request(None, None, 302, "", None, "https://attacker.invalid") is None
    )


@pytest.mark.parametrize("suffix", [".sqlite3", ".sqlite3-journal", ".db", ".db-wal"])
def test_public_file_check_rejects_portal_database_and_journals(
    tmp_path, monkeypatch, capsys, suffix
):
    monkeypatch.chdir(tmp_path)
    name = "private" + suffix
    (tmp_path / name).write_bytes(b"synthetic-private-database")
    monkeypatch.setattr("subprocess.check_output", lambda *args, **kwargs: name.encode() + b"\0")
    assert check_public_files() == 1
    assert "synthetic-private-database" not in capsys.readouterr().out
