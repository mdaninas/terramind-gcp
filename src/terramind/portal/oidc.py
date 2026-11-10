"""Google authorization-code flow; verified provider tokens are never retained."""

import base64
import hashlib
import json
import secrets
from typing import Any, Protocol
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from terramind.portal.settings import PortalSettings
from terramind.portal.store import owner_key


class IdentityProvider(Protocol):
    def authorize(self, state: str, nonce: str, verifier: str) -> str: ...
    def exchange(self, code: str, nonce: str, verifier: str) -> str: ...


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> None:
        return None


class GoogleOIDC:
    def __init__(self, settings: PortalSettings):
        self.settings = settings

    def authorize(self, state: str, nonce: str, verifier: str) -> str:
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .decode()
            .rstrip("=")
        )
        return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(
            {
                "client_id": self.settings.client_id,
                "redirect_uri": self.settings.callback,
                "response_type": "code",
                "scope": "openid email",
                "state": state,
                "nonce": nonce,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "access_type": "online",
                "prompt": "select_account",
            }
        )

    def verified_identity(self, claims: dict[str, Any], nonce: str) -> str:
        # Signature, issuer, audience and expiry are verified by google-auth before this check.
        if (
            not isinstance(claims.get("nonce"), str)
            or not secrets.compare_digest(claims["nonce"].encode(), nonce.encode())
            or claims.get("email_verified") is not True
            or not isinstance(claims.get("email"), str)
            or claims["email"].lower() not in self.settings.allowed_emails
            or not isinstance(claims.get("sub"), str)
            or not 1 <= len(claims["sub"]) <= 255
            or claims.get("aud") != self.settings.client_id
            or claims.get("azp", self.settings.client_id) != self.settings.client_id
        ):
            raise ValueError("Google account is not authorized")
        return owner_key("google", claims["sub"])

    def exchange(self, code: str, nonce: str, verifier: str) -> str:
        if not code or len(code) > 4096:
            raise ValueError("Invalid authorization code")
        import requests
        from google.auth.transport.requests import Request as GoogleRequest
        from google.oauth2 import id_token

        body = urlencode(
            {
                "code": code,
                "client_id": self.settings.client_id,
                "client_secret": self.settings.client_secret,
                "redirect_uri": self.settings.callback,
                "grant_type": "authorization_code",
                "code_verifier": verifier,
            }
        ).encode()
        request = Request(
            "https://oauth2.googleapis.com/token",
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            with build_opener(NoRedirect()).open(request, timeout=10) as response:
                raw = response.read(64 * 1024 + 1)
            if len(raw) > 64 * 1024:
                raise ValueError("OAuth response exceeds its limit")
            payload = json.loads(raw)
            token = payload["id_token"]
            if not isinstance(token, str) or len(token) > 16 * 1024:
                raise ValueError("Invalid identity token")
            with requests.Session() as session:
                transport = GoogleRequest(session=session)

                def bounded_request(*args: Any, **kwargs: Any) -> Any:
                    kwargs["timeout"] = 5
                    return transport(*args, **kwargs)

                claims = id_token.verify_oauth2_token(  # type: ignore[no-untyped-call]
                    token,
                    bounded_request,
                    audience=self.settings.client_id,
                    clock_skew_in_seconds=30,
                )
            return self.verified_identity(claims, nonce)
        except Exception:
            raise ValueError("Google authentication failed") from None
