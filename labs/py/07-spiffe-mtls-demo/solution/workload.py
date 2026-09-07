"""Lab 07 — reference solution."""
from __future__ import annotations

from typing import Iterable, Optional


class SpiffeID:
    __slots__ = ("trust_domain", "path", "_raw")

    def __init__(self, trust_domain: str, path: str, raw: str) -> None:
        self.trust_domain = trust_domain
        self.path = path
        self._raw = raw

    @classmethod
    def parse(cls, s: str) -> "SpiffeID":
        if not isinstance(s, str):
            raise ValueError(f"SPIFFE id must be a string, got {type(s).__name__}")
        prefix = "spiffe://"
        if not s.startswith(prefix):
            raise ValueError(f"SPIFFE id must start with 'spiffe://': {s!r}")
        rest = s[len(prefix):]
        if "/" not in rest:                       # root id: spiffe://example.org
            trust_domain, path = rest, ""
        else:
            trust_domain, path = rest.split("/", 1)
            path = "/" + path                     # path RETAINS the leading slash
        if not trust_domain:
            raise ValueError(f"SPIFFE id has an empty trust domain: {s!r}")
        return cls(trust_domain=trust_domain, path=path, raw=s)

    def __str__(self) -> str:
        return self._raw

    def __repr__(self) -> str:
        return f"SpiffeID({self._raw!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SpiffeID):
            return NotImplemented
        return self._raw == other._raw

    def __ne__(self, other: object) -> bool:
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

    def __hash__(self) -> int:
        return hash(self._raw)


class Workload:
    def __init__(self, id: SpiffeID, service: str) -> None:
        self.id = id
        self.service = service

    def __repr__(self) -> str:
        return f"Workload({self.service!r}, {str(self.id)!r})"


class TrustBundle:
    def __init__(self, trust_domain: str,
                 federates_with: Optional[Iterable[str]] = None) -> None:
        self.trust_domain = trust_domain
        self.federates_with: set[str] = set(federates_with or ())

    def validate(self, id: SpiffeID) -> bool:
        return id.trust_domain == self.trust_domain

    def trusts(self, id: SpiffeID) -> bool:
        if self.validate(id):
            return True
        return id.trust_domain in self.federates_with

    def __repr__(self) -> str:
        return (f"TrustBundle({self.trust_domain!r}, "
                f"federates_with={sorted(self.federates_with)!r})")


class AuthorizationPolicy:
    def __init__(self, trust_domain: str, expected_id_prefix: str,
                 allowed_prefixes: Iterable[str]) -> None:
        self.trust_domain = trust_domain
        self.expected_id_prefix = expected_id_prefix
        self.allowed_prefixes = list(allowed_prefixes)

    @staticmethod
    def match_source(workload_id: SpiffeID, expected_id_prefix: str) -> bool:
        return workload_id.path.startswith(expected_id_prefix)

    @staticmethod
    def match_resource(path: str, allowed_prefixes: Iterable[str]) -> bool:
        return any(path.startswith(p) for p in allowed_prefixes)

    def authorize(self, workload: Workload, resource: str) -> bool:
        if workload.id.trust_domain != self.trust_domain:
            return False
        if not self.match_source(workload.id, self.expected_id_prefix):
            return False
        return self.match_resource(resource, self.allowed_prefixes)

    def authorize_cross(self, workload: Workload, resource: str,
                        local_bundle: TrustBundle,
                        federated_bundle: TrustBundle) -> bool:
        if not self.match_source(workload.id, self.expected_id_prefix):
            return False
        if not self.match_resource(resource, self.allowed_prefixes):
            return False
        if workload.id.trust_domain == local_bundle.trust_domain:
            return local_bundle.validate(workload.id)
        if workload.id.trust_domain not in local_bundle.federates_with:
            return False
        return federated_bundle.validate(workload.id)


def handshake(client_workload: Workload, server_workload: Workload,
              client_bundle: TrustBundle, server_bundle: TrustBundle) -> dict:
    client_saw = str(server_workload.id)     # SAN the client saw on the server
    server_saw = str(client_workload.id)     # SAN the server saw on the client
    client_ok = client_bundle.trusts(server_workload.id)
    server_ok = server_bundle.trusts(client_workload.id)

    if not client_ok and not server_ok:
        reason = (f"client does not trust server id {client_saw} "
                  f"(domain '{server_workload.id.trust_domain}' not in bundle "
                  f"{client_bundle!r}) and server does not trust client id "
                  f"{server_saw} (domain '{client_workload.id.trust_domain}' "
                  f"not in bundle {server_bundle!r})")
    elif not client_ok:
        reason = (f"client does not trust server id {client_saw} "
                  f"(domain '{server_workload.id.trust_domain}' not in bundle "
                  f"{client_bundle!r})")
    elif not server_ok:
        reason = (f"server does not trust client id {server_saw} "
                  f"(domain '{client_workload.id.trust_domain}' not in bundle "
                  f"{server_bundle!r})")
    else:
        reason = "mutual trust established"

    return {
        "established": client_ok and server_ok,
        "reason": reason,
        "client_saw": client_saw,
        "server_saw": server_saw,
    }
