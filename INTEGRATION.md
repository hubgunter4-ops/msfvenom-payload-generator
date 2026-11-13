# Integración de session_parser y msfconsole_manager

Estos dos módulos nuevos reparan, sin tocar el generador de payloads:

- `session_parser.py`: `parse_session_event()` valida con `ipaddress`
  IPv4 e IPv6 (con corchetes, puerto y zona), rechaza 999.999.999.999,
  deduplica por id con `SessionDeduplicator` y detecta rotación de log
  con `LogPositionTracker`.
- `msfconsole_manager.py`: `MsfConsoleManager` con `start/stop/is_running`,
  `terminate` -> `wait` -> `kill`, y context manager. Sin `shell=True`.

## Integrado el 2026-11-13

Ya está cableado en `MSFVenomPayloadGeneratorv4.0.py`: `SessionMonitor._procesar` usa `parse_session_event`, `_monitorear` resetea la posición si el log rota, y `MSFVenomGenerator.lanzar_listener` arranca msfconsole con `MsfConsoleManager` (con `detener_listener()` para pararlo). Ver `tests/test_integration.py`.

## Cómo se cableó (referencia)

En `SessionMonitor._procesar`, en vez del regex solo IPv4:

```python
from session_parser import parse_session_event, SessionDeduplicator
# en __init__: self._dedup = SessionDeduplicator()
# en _procesar, por cada línea:
ev = parse_session_event(linea)
if ev and self._dedup.is_new(ev["id"]):
    self._notificar(ev)
```

En `AutoListener.lanzar_listener`, en vez de `subprocess.Popen` suelto:

```python
from msfconsole_manager import MsfConsoleManager
self.listener_manager = MsfConsoleManager()
proc = self.listener_manager.start(rc_path)
# al salir / detener: self.listener_manager.stop()
```

## Tests

```bash
python3 -m unittest discover -s tests -v
# 16 tests, solo mocks, sin ejecutar msfvenom ni msfconsole reales.
```

Solo laboratorio autorizado. No se añade extracción, stealth ni bypass.
