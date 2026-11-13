"""Parseo de eventos de sesión de msfconsole.

Reemplazo del regex solo-IPv4 que había en SessionMonitor:
- Valida con ipaddress, así 999.999.999.999 se rechaza.
- Acepta IPv4 e IPv6, con o sin corchetes y con o sin puerto.
- No ejecuta nada: solo parsea texto de log, para laboratorio autorizado.

Ejemplos aceptados:
    Meterpreter session 1 opened (192.168.1.10:4444)
    Command shell session 2 opened (2001:db8::1:4444)
    Meterpreter session 3 opened ([2001:db8::1]:4444)
    [*] Meterpreter session 4 opened (fe80::1%eth0)
"""

from __future__ import annotations

import ipaddress
import re

_SESSION_RE = re.compile(
    r"(Meterpreter|Command shell)\s+session\s+(\d+)\s+opened",
    re.IGNORECASE,
)

# Candidatos a IP: secuencias sin espacios que pueden contener :, ., %, corchetes.
_TOKEN_RE = re.compile(r"\[?[0-9A-Fa-f:.%]+\]?(?::\d+)?")


def _clean_token(token: str) -> str | None:
    """Quita corchetes, puerto y zona de un candidato y valida con ipaddress."""
    token = token.strip().strip(",;()")
    if not token:
        return None
    # IPv6 con corchetes y puerto: [2001:db8::1]:4444
    if token.startswith("["):
        end = token.find("]")
        if end == -1:
            return None
        token = token[1:end]
    else:
        # IPv4 con puerto: 192.168.1.10:4444 -> quita :4444 solo si lo que
        # queda es una IPv4 válida. Para IPv6 sin corchetes no se quita nada:
        # 2001:db8::1:4444 es ambiguo y se intenta tal cual primero.
        if token.count(":") == 1 and "." in token:
            token = token.rsplit(":", 1)[0]
    # Zona link-local: fe80::1%eth0
    if "%" in token:
        token = token.split("%", 1)[0]
    try:
        ip = ipaddress.ip_address(token)
    except ValueError:
        return None
    # ipaddress acepta "1.2.3.4" pero también cosas como "0x..."? No: solo
    # literales válidos. Rechaza además direcciones con octetos fuera de rango.
    return str(ip)


def extract_ip(text: str) -> str | None:
    """Devuelve la primera IP válida (v4 o v6) encontrada en text, o None."""
    for match in _TOKEN_RE.finditer(text):
        ip = _clean_token(match.group(0))
        if ip is not None:
            return ip
    return None


def parse_session_event(text: str) -> dict | None:
    """Parsea una línea de log de msfconsole.

    Devuelve {"id": str, "type": "meterpreter"|"shell", "ip": str,
    "ip_version": 4|6} o None si no es un evento de sesión con IP válida.
    """
    match = _SESSION_RE.search(text)
    if not match:
        return None
    kind = match.group(1).lower()
    session_type = "meterpreter" if "meterpreter" in kind else "shell"
    rest = text[match.end():]
    ip = extract_ip(rest)
    if ip is None:
        return None
    return {
        "id": match.group(2),
        "type": session_type,
        "ip": ip,
        "ip_version": ipaddress.ip_address(ip).version,
    }


class SessionDeduplicator:
    """Recuerda ids ya vistos para no notificar la misma sesión dos veces."""

    def __init__(self) -> None:
        self.seen: set[str] = set()

    def is_new(self, session_id: str) -> bool:
        if session_id in self.seen:
            return False
        self.seen.add(session_id)
        return True


class LogPositionTracker:
    """Posición de lectura de un log con detección de rotación.

    Si el archivo se achica (rotación/truncado), la posición vuelve a 0
    en vez de quedarse más allá del final y perder líneas.
    """

    def __init__(self) -> None:
        self.position = 0

    def update(self, size: int) -> int:
        if size < self.position:
            self.position = 0
        return self.position

    def advance(self, new_position: int) -> None:
        self.position = new_position
