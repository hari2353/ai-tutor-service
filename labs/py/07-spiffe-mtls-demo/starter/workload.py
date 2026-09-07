"""Lab 07 — SPIFFE-style workload identity + mTLS authorization.

Fill in every TODO. Tests define done.

Rules:
  * Pure stdlib, pure logic — no network, no real TLS, no time.sleep().
  * Parsing must be strict: a malformed SPIFFE id is an attack surface,
    not a string-editing exercise.
"""
from __future__ import annotations

from typing import Iterable, Optional


# --------------------------------------------------------------------------- identity
class SpiffeID:
    """spiffe://<trust-domain>/<path> — a workload's globally unique name."""

    __slots__ = ("trust_domain", "path", "_raw")

    def __init__(self, trust_domain: str, path: str, raw: str) -> None:
        self.trust_domain = trust_domain
        self.path = path
        self._raw = raw

    @classmethod
    def parse(cls, s: str) -> "SpiffeID":
        """Parse 'spiffe://trust-domain/path' strictly.

        Raises ValueError on: missing spiffe:// scheme, empty trust domain.
        A root id (spiffe://example.org, no path) is legal — path == "".
        A non-root path RETAINS its leading slash: "/backend/payments".
        """
        # TODO(step 1): strict parse -> (trust_domain, path, raw)
        raise NotImplementedError

    def __str__(self) -> str:
        return self._raw

    def __repr__(self) -> str:
        return f"SpiffeID({self._raw!r})"

    def __eq__(self, other: object) -> bool:
        # TODO(step 2): equality on the FULL id string, not just the path
        raise NotImplementedError

    def __ne__(self, other: object) -> bool:
        # TODO(step 3)
        raise NotImplementedError

    def __hash__(self) -> int:
        return hash(self._raw)


class Workload:
    """A named service holding a SPIFFE id (its SVID's SAN)."""

    def __init__(self, id: SpiffeID, service: str) -> None:
        self.id = id
        self.service = service

    def __repr__(self) -> str:
        return f"Workload({self.service!r}, {str(self.id)!r})"


# --------------------------------------------------------------------------- trust
class TrustBundle:
    """The trust domains one side accepts ids from.

    federates_with: foreign trust domains this bundle ALSO trusts.
    Empty by default — a foreign domain is DENIED until explicitly listed.
    """

    def __init__(self, trust_domain: str,
                 federates_with: Optional[Iterable[str]] = None) -> None:
        self.trust_domain = trust_domain
        self.federates_with: set[str] = set(federates_with or ())

    def validate(self, id: SpiffeID) -> bool:
        """True iff the id belongs to THIS trust domain (locals only —
        federation never leaks into validate())."""
        # TODO(step 4)
        raise NotImplementedError

    def trusts(self, id: SpiffeID) -> bool:
        """Local OR federated — what an mTLS handshake actually checks."""
        # TODO(step 5)
        raise NotImplementedError

    def __repr__(self) -> str:
        return (f"TrustBundle({self.trust_domain!r}, "
                f"federates_with={sorted(self.federates_with)!r})")


# --------------------------------------------------------------------------- policy
class AuthorizationPolicy:
    """Prefix-based source + resource rules, scoped to one trust domain."""

    def __init__(self, trust_domain: str, expected_id_prefix: str,
                 allowed_prefixes: Iterable[str]) -> None:
        self.trust_domain = trust_domain
        self.expected_id_prefix = expected_id_prefix
        self.allowed_prefixes = list(allowed_prefixes)

    @staticmethod
    def match_source(workload_id: SpiffeID, expected_id_prefix: str) -> bool:
        """True iff the workload's id PATH startswith the expected prefix."""
        # TODO(step 6)
        raise NotImplementedError

    @staticmethod
    def match_resource(path: str, allowed_prefixes: Iterable[str]) -> bool:
        """True iff the resource path startswith any allowed prefix."""
        # TODO(step 7)
        raise NotImplementedError

    def authorize(self, workload: Workload, resource: str) -> bool:
        """Same trust domain AND source prefix matches AND resource allowed."""
        # TODO(step 8)
        raise NotImplementedError

    def authorize_cross(self, workload: Workload, resource: str,
                        local_bundle: TrustBundle,
                        federated_bundle: TrustBundle) -> bool:
        """Federation-aware authorize.

        Local workloads: local_bundle.validate(id) must hold.
        Foreign workloads: local_bundle must federate with the workload's
        trust domain AND federated_bundle must actually own the id.
        Prefix rules apply to foreigners too — federation grants trust,
        not blanket access.
        """
        # TODO(step 9)
        raise NotImplementedError


# --------------------------------------------------------------------------- mTLS
def handshake(client_workload: Workload, server_workload: Workload,
              client_bundle: TrustBundle, server_bundle: TrustBundle) -> dict:
    """Simulated mTLS: BOTH directions validated, SANs recorded either way.

    The client must validate the server's id against a bundle it trusts
    (federation counts), and the server must validate the client's id the
    same way. One failed direction kills the whole handshake.
    """
    # TODO(step 10):
    #   client_saw  = the SAN the client saw on the server's cert
    #   server_saw  = the SAN the server saw on the client's cert
    #   client_ok   = client_bundle.trusts(server's id)
    #   server_ok   = server_bundle.trusts(client's id)
    #   established = client_ok AND server_ok, with a reason naming the
    #                 failing side/direction when not established.
    raise NotImplementedError
