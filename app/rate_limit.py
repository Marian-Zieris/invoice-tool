"""Jednoduchý in-memory rate limiter pro veřejné auth endpointy.

Drží stav jen v paměti jednoho procesu - pro současné nasazení (jeden uvicorn
worker, jeden kontejner) to stačí. Pokud appka v budoucnu poběží ve více
procesech/instancích najednou, je potřeba přesunout stav do sdíleného úložiště
(např. Redis) - limit by jinak šlo obejít zásahem na jinou instanci.
"""

import threading
import time
from collections import defaultdict
from typing import Dict, List, Optional

_WINDOW_SECONDS = 300  # 5 minut
_MAX_ATTEMPTS_PER_KEY = 5  # na kombinaci IP + email
_MAX_ATTEMPTS_PER_IP = 20  # napříč všemi emaily z jedné IP (credential stuffing)

_lock = threading.Lock()
_attempts: Dict[str, List[float]] = defaultdict(list)


def _prune(bucket_key: str, now: float) -> List[float]:
    timestamps = [t for t in _attempts[bucket_key] if now - t < _WINDOW_SECONDS]
    _attempts[bucket_key] = timestamps
    return timestamps


def seconds_until_retry(ip: str, email: str) -> Optional[int]:
    """None = pokus je povolený. Jinak počet sekund, než to má smysl zkusit znovu."""
    now = time.time()
    with _lock:
        per_key = _prune(f"key:{ip}:{email.lower()}", now)
        per_ip = _prune(f"ip:{ip}", now)
        if len(per_key) >= _MAX_ATTEMPTS_PER_KEY:
            return max(1, int(_WINDOW_SECONDS - (now - per_key[0])))
        if len(per_ip) >= _MAX_ATTEMPTS_PER_IP:
            return max(1, int(_WINDOW_SECONDS - (now - per_ip[0])))
    return None


def record_failed_attempt(ip: str, email: str) -> None:
    now = time.time()
    with _lock:
        _attempts[f"key:{ip}:{email.lower()}"].append(now)
        _attempts[f"ip:{ip}"].append(now)


def reset_attempts(ip: str, email: str) -> None:
    """Volá se po úspěšném loginu - smaže jen počítadlo pro tuhle konkrétní
    kombinaci IP+email, ne celou historii dané IP (sdílená síť/NAT by jinak
    mohla úspěšným loginem jednoho uživatele smazat limit pro útočníka)."""
    with _lock:
        _attempts.pop(f"key:{ip}:{email.lower()}", None)


def client_ip(forwarded_for: Optional[str], fallback: Optional[str]) -> str:
    """`X-Forwarded-For` má smysl důvěřovat jen když appka sedí za naším vlastním
    reverse proxy (nginx v produkci nastavuje hlavičku vždy a přepisuje tu
    klientskou) - port 8000 backendu proto nesmí být v produkci publikovaný
    ven, jinak by šlo hlavičku podvrhnout přímo (viz docker-compose.yml)."""
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return fallback or "unknown"
