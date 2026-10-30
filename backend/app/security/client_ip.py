import hashlib
import secrets
from fastapi import Request

_PROCESS_SALT = secrets.token_hex(32)
UNKNOWN_CLIENT = "unknown"


def get_client_ip(request: Request, trust_proxy: bool) -> str:
    if trust_proxy:
        forwarded = request.headers.get("x-forwarded-for", "")
        hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
        if hops:
            return hops[-1]
    if request.client is not None and request.client.host:
        return request.client.host
    return UNKNOWN_CLIENT


def hash_client_ip(ip: str, salt: str | None) -> str:
    effective_salt = salt or _PROCESS_SALT
    return hashlib.sha256(f"{effective_salt}:{ip}".encode("utf-8")).hexdigest()
