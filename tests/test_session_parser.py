import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from session_parser import (
    LogPositionTracker,
    SessionDeduplicator,
    extract_ip,
    parse_session_event,
)


class ParseSessionEventTests(unittest.TestCase):
    def test_ipv4_valida(self):
        ev = parse_session_event(
            "Meterpreter session 1 opened (192.168.1.10:4444)"
        )
        self.assertEqual(ev, {"id": "1", "type": "meterpreter", "ip": "192.168.1.10", "ip_version": 4})

    def test_ipv4_invalida_rechazada(self):
        # 999 no es un octeto válido: el regex antiguo lo aceptaba.
        self.assertIsNone(parse_session_event("Meterpreter session 1 opened (999.999.999.999)"))
        self.assertIsNone(parse_session_event("Meterpreter session 1 opened (256.1.1.1)"))

    def test_ipv6_sin_corchetes(self):
        ev = parse_session_event("Command shell session 2 opened (2001:db8::1)")
        self.assertEqual(ev["ip"], "2001:db8::1")
        self.assertEqual(ev["ip_version"], 6)
        self.assertEqual(ev["type"], "shell")

    def test_ipv6_con_corchetes_y_puerto(self):
        ev = parse_session_event("Meterpreter session 3 opened ([2001:db8::1]:4444)")
        self.assertEqual(ev["ip"], "2001:db8::1")
        self.assertEqual(ev["ip_version"], 6)

    def test_ipv6_link_local_con_zona(self):
        ev = parse_session_event("Meterpreter session 4 opened (fe80::1%eth0)")
        self.assertEqual(ev["ip"], "fe80::1")

    def test_sin_evento_o_sin_ip(self):
        self.assertIsNone(parse_session_event("nada que ver aquí"))
        self.assertIsNone(parse_session_event("Meterpreter session 5 opened (sin ip)"))

    def test_extract_ip_primera_valida(self):
        self.assertEqual(extract_ip("de 10.0.0.5 a 2001:db8::2"), "10.0.0.5")
        self.assertIsNone(extract_ip("999.1.1.1 y texto"))


class DeduplicatorTests(unittest.TestCase):
    def test_misma_sesion_no_se_notifica_dos_veces(self):
        d = SessionDeduplicator()
        self.assertTrue(d.is_new("1"))
        self.assertFalse(d.is_new("1"))
        self.assertTrue(d.is_new("2"))


class LogPositionTrackerTests(unittest.TestCase):
    def test_rotacion_resetea_posicion(self):
        t = LogPositionTracker()
        t.advance(5000)
        self.assertEqual(t.update(100), 0)
        self.assertEqual(t.update(200), 0)

    def test_sin_rotacion_mantiene_posicion(self):
        t = LogPositionTracker()
        t.advance(100)
        self.assertEqual(t.update(5000), 100)


if __name__ == "__main__":
    unittest.main()
