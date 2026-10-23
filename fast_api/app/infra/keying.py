import hashlib
import json
from typing import Any


def _normalize(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _normalize(obj[k]) for k in sorted(obj)}
    if isinstance(obj, list):
        return [_normalize(i) for i in obj]
    return obj


def build_fingerprint(query_params: dict[str, Any] | None, body: dict[str, Any] | None) -> str:
    payload = {
        "query": _normalize(query_params or {}),
        "body": _normalize(body or {}),
    }
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def build_cache_key(route: str, scope: str, fingerprint: str) -> str:
    return f"cache:v1:{route}:{scope}:{fingerprint}"


def build_rate_limit_key(route: str, scope: str, bucket: int) -> str:
    return f"rl:v1:{route}:{scope}:{bucket}"