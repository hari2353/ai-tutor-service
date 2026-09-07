"""Lab 06 — reference solution."""
from __future__ import annotations

import base64
import hashlib
import secrets
import time
from typing import Optional


class SystemClock:
    def now(self) -> float:
        return time.time()


class FakeClock:
    def __init__(self, t: float = 0.0) -> None:
        self.t = t

    def now(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def pkce_s256_challenge(verifier: str) -> str:
    return _b64url(hashlib.sha256(verifier.encode("ascii")).digest())


def pkce_verifier_ok(verifier: str) -> bool:
    if not 43 <= len(verifier) <= 128:
        return False
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")
    return all(ch in allowed for ch in verifier)


class OAuthError(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class AuthorizationServer:
    def __init__(self, clock, code_ttl: float = 60.0,
                 require_s256: bool = True) -> None:
        self.clock = clock
        self.code_ttl = code_ttl
        self.require_s256 = require_s256
        self.clients: dict[str, dict] = {}
        self._codes: dict[str, dict] = {}
        self.tokens_issued: list[dict] = []

    def register_client(self, client_id: str, redirect_uris: list[str],
                        scopes: list[str]) -> None:
        self.clients[client_id] = {
            "redirect_uris": list(redirect_uris),
            "scopes": set(scopes),
        }

    def authorize(self, client_id: str, redirect_uri: str, scope: str,
                  code_challenge: str, code_challenge_method: str = "S256",
                  state: str = "x") -> str:
        client = self.clients.get(client_id)
        if client is None:
            raise OAuthError("unknown client_id")
        if redirect_uri not in client["redirect_uris"]:
            raise OAuthError("redirect_uri mismatch")
        requested = set(scope.split())
        if not requested or not requested <= client["scopes"]:
            raise OAuthError("scope not allowed")
        if self.require_s256 and code_challenge_method != "S256":
            raise OAuthError("plain challenge not allowed — S256 required")
        if not code_challenge:
            raise OAuthError("code_challenge required")
        code = secrets.token_urlsafe(32)
        self._codes[code] = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "code_challenge": code_challenge,
            "expires_at": self.clock.now() + self.code_ttl,
            "used": False,
        }
        return f"?code={code}&state={state}"

    def token(self, grant_type: str, code: str, client_id: str,
              redirect_uri: str, code_verifier: str) -> dict:
        if grant_type != "authorization_code":
            raise OAuthError("unsupported_grant_type")
        rec = self._codes.get(code)
        if rec is None:
            raise OAuthError("invalid_grant: unknown code")
        if rec["used"]:
            raise OAuthError("invalid_grant: code already redeemed")
        if self.clock.now() >= rec["expires_at"]:
            del self._codes[code]
            raise OAuthError("invalid_grant: code expired")
        if rec["client_id"] != client_id or rec["redirect_uri"] != redirect_uri:
            raise OAuthError("invalid_grant: code is bound to a different client/redirect")
        if pkce_s256_challenge(code_verifier) != rec["code_challenge"]:
            raise OAuthError("invalid_grant: PKCE verification failed")
        rec["used"] = True
        access_token = secrets.token_urlsafe(32)
        payload = {"access_token": access_token, "token_type": "Bearer",
                   "scope": rec["scope"]}
        self.tokens_issued.append(payload)
        return payload


class ClientApp:
    def __init__(self, client_id: str, redirect_uri: str) -> None:
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        self.verifier: Optional[str] = None
        self.state: Optional[str] = None
        self.tokens: Optional[dict] = None

    def begin(self) -> dict:
        self.verifier = _b64url(secrets.token_bytes(48))   # 64-char unreserved
        self.state = secrets.token_urlsafe(16)
        return {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "openid profile",
            "code_challenge": pkce_s256_challenge(self.verifier),
            "code_challenge_method": "S256",
            "state": self.state,
        }

    def complete(self, server: "AuthorizationServer", callback_params: dict) -> dict:
        if "error" in callback_params:
            raise OAuthError(callback_params["error"])
        if callback_params.get("state") != self.state:
            raise OAuthError("state mismatch on callback")
        code = callback_params.get("code", "")
        self.tokens = server.token(
            grant_type="authorization_code", code=code,
            client_id=self.client_id, redirect_uri=self.redirect_uri,
            code_verifier=self.verifier or "")
        return self.tokens


class ProtectedResource:
    def __init__(self, server: AuthorizationServer) -> None:
        self.server = server

    def get(self, access_token: str) -> dict:
        for issued in self.server.tokens_issued:
            if issued["access_token"] == access_token:
                return {"resource": "profile", "scope": issued["scope"]}
        raise OAuthError("invalid_token")
