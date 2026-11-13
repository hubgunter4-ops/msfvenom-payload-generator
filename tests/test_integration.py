"""Integración: el script principal usa session_parser y msfconsole_manager.

Carga MSFVenomPayloadGeneratorv4.0.py por ruta (su nombre no es importable)
y comprueba, solo con mocks, que:
- SessionMonitor._procesar detecta IPv4 e IPv6, deduplica y rechaza IPv4 inválida.
- MSFVenomGenerator.lanzar_listener arranca msfconsole vía MsfConsoleManager.
- detener_listener detiene monitor y proceso.
Sin ejecutar msfvenom ni msfconsole reales. Solo laboratorio autorizado.
"""
import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MAIN = ROOT / "MSFVenomPayloadGeneratorv4.0.py"


def load_main():
    spec = importlib.util.spec_from_file_location("msfvenom_main", MAIN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class SessionMonitorIntegrationTests(unittest.TestCase):
    def test_procesar_ipv4_ipv6_deduplica_y_rechaza_invalida(self):
        mod = load_main()
        seen = []

        def callback(info):
            seen.append(info)

        monitor = mod.SessionMonitor(callback)
        chunk = (
            "Meterpreter session 1 opened (192.168.1.10:4444)\n"
            "Command shell session 2 opened ([2001:db8::1]:4444)\n"
            "Meterpreter session 1 opened (192.168.1.10:4444)\n"
            "Meterpreter session 3 opened (999.999.999.999)\n"
        )
        monitor._procesar(chunk)
        self.assertEqual(len(seen), 2)
        self.assertEqual(seen[0]["id"], "1")
        self.assertEqual(seen[0]["tipo"], "meterpreter")
        self.assertEqual(seen[0]["ip"], "192.168.1.10")
        self.assertIn("timestamp", seen[0])
        self.assertEqual(seen[1]["id"], "2")
        self.assertEqual(seen[1]["tipo"], "shell")
        self.assertEqual(seen[1]["ip"], "2001:db8::1")
        self.assertEqual(monitor.sesiones_vistas, {"1", "2"})


class LanzarListenerIntegrationTests(unittest.TestCase):
    def test_lanzar_y_detener_con_manager(self):
        mod = load_main()
        fake_proc = MagicMock()
        fake_proc.pid = 4321
        fake_proc.poll.return_value = None
        fake_proc.wait.return_value = 0
        monitor_instance = MagicMock()
        with patch("msfconsole_manager.subprocess.Popen", return_value=fake_proc), \
                patch.object(mod, "SessionMonitor", return_value=monitor_instance), \
                patch("time.sleep", return_value=None):
            gen = mod.MSFVenomGenerator()
            proc = gen.lanzar_listener("/tmp/test.rc", background=True)
            self.assertIs(proc, fake_proc)
            self.assertIsNotNone(getattr(gen, "listener_manager", None))
            self.assertTrue(gen.listener_manager.is_running())
            monitor_instance.iniciar.assert_called_once()
            gen.detener_listener()
        fake_proc.terminate.assert_called_once()
        monitor_instance.detener.assert_called_once()


if __name__ == "__main__":
    unittest.main()
