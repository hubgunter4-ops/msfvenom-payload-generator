"""Gestión del ciclo de vida de un proceso msfconsole.

El código anterior lanzaba subprocess.Popen(["msfconsole", ...]) y devolvía
el Popen sin seguimiento: no había stop, ni comprobación de si seguía vivo,
ni limpieza al salir, así que el proceso podía quedar huérfano.

Esta clase no añade ninguna capacidad ofensiva nueva: solo envuelve el
Popen que ya existía, con terminate -> wait -> kill, y context manager.
No ejecuta nada por sí sola; el comando se pasa explícitamente.
Solo para laboratorio autorizado.
"""

from __future__ import annotations

import subprocess
from typing import Optional, Sequence


class MsfConsoleManager:
    """Dueño de un proceso msfconsole: start, stop, is_running, context manager."""

    def __init__(self, command: Optional[Sequence[str]] = None) -> None:
        self._command = list(command) if command else None
        self._proc: Optional[subprocess.Popen] = None

    @property
    def pid(self) -> Optional[int]:
        return self._proc.pid if self._proc is not None else None

    @property
    def process(self) -> Optional[subprocess.Popen]:
        return self._proc

    def start(self, rc_path: str, command: Optional[Sequence[str]] = None) -> subprocess.Popen:
        if self.is_running():
            raise RuntimeError("msfconsole ya está en ejecución (PID %s)" % self.pid)
        cmd = list(command) if command is not None else self._command
        if cmd is None:
            cmd = ["msfconsole", "-q", "-r", rc_path]
        # Sin shell=True: la lista se ejecuta tal cual, sin interpretar la shell.
        self._proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        return self._proc

    def poll(self) -> Optional[int]:
        if self._proc is None:
            return None
        return self._proc.poll()

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def stop(self, timeout: float = 5.0) -> bool:
        """Detiene el proceso si sigue vivo. Devuelve True si quedó detenido.

        Secuencia: terminate, esperar `timeout`, y kill solo si no termina.
        Idempotente: llamarlo dos veces, o sin haber arrancado, no falla.
        """
        proc = self._proc
        if proc is None:
            return True
        if proc.poll() is not None:
            return True
        proc.terminate()
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=timeout)
        return proc.poll() is not None

    def __enter__(self) -> "MsfConsoleManager":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()
        return None
