import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from msfconsole_manager import MsfConsoleManager


def _fake_proc(poll_result=None):
    proc = MagicMock()
    proc.pid = 1234
    proc.poll.return_value = poll_result
    proc.wait.return_value = 0
    return proc


class MsfConsoleManagerTests(unittest.TestCase):
    def test_start_usa_lista_sin_shell(self):
        mgr = MsfConsoleManager()
        proc = _fake_proc()
        with patch("msfconsole_manager.subprocess.Popen", return_value=proc) as popen:
            got = mgr.start("/tmp/listener.rc")
            popen.assert_called_once()
            args, kwargs = popen.call_args
            self.assertEqual(args[0], ["msfconsole", "-q", "-r", "/tmp/listener.rc"])
            self.assertNotIn("shell", kwargs)
            self.assertIs(got, proc)
            self.assertEqual(mgr.pid, 1234)
            self.assertTrue(mgr.is_running())

    def test_start_doble_falla(self):
        mgr = MsfConsoleManager()
        with patch("msfconsole_manager.subprocess.Popen", return_value=_fake_proc()):
            mgr.start("/tmp/a.rc")
            with self.assertRaises(RuntimeError):
                mgr.start("/tmp/b.rc")

    def test_stop_terminate_y_espera(self):
        mgr = MsfConsoleManager()
        proc = _fake_proc()
        # poll: None mientras corre (check en stop), 0 tras wait (return)
        proc.poll.side_effect = [None, 0]
        with patch("msfconsole_manager.subprocess.Popen", return_value=proc):
            mgr.start("/tmp/a.rc")
            self.assertTrue(mgr.stop(timeout=5))
        proc.terminate.assert_called_once()
        proc.wait.assert_called_once_with(timeout=5)
        proc.kill.assert_not_called()

    def test_stop_hace_kill_si_no_termina(self):
        mgr = MsfConsoleManager()
        proc = _fake_proc()
        proc.poll.side_effect = [None, 0]
        proc.wait.side_effect = [subprocess.TimeoutExpired(cmd="msfconsole", timeout=5), 0]
        with patch("msfconsole_manager.subprocess.Popen", return_value=proc):
            mgr.start("/tmp/a.rc")
            self.assertTrue(mgr.stop(timeout=5))
        proc.kill.assert_called_once()

    def test_stop_idempotente_y_sin_proceso(self):
        mgr = MsfConsoleManager()
        self.assertTrue(mgr.stop())
        proc = _fake_proc(poll_result=0)
        with patch("msfconsole_manager.subprocess.Popen", return_value=proc):
            mgr.start("/tmp/a.rc")
            self.assertTrue(mgr.stop())
        proc.terminate.assert_not_called()

    def test_context_manager_detiene_al_salir(self):
        proc = _fake_proc()
        proc.poll.side_effect = [None, None, 0]
        with patch("msfconsole_manager.subprocess.Popen", return_value=proc):
            with MsfConsoleManager() as mgr:
                mgr.start("/tmp/a.rc")
                self.assertTrue(mgr.is_running())
        proc.terminate.assert_called_once()


if __name__ == "__main__":
    unittest.main()
