import importlib.util
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "msfvenom_generator", ROOT / "MSFVenomPayloadGeneratorv4.0.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class GuidedGeneratorTests(unittest.TestCase):
    def test_guided_preflight_has_no_external_execution(self):
        output = io.StringIO()
        with patch("shutil.which", return_value=None), redirect_stdout(output):
            self.assertEqual(MODULE.guided_preflight(), 0)
        self.assertIn("ejecución guiada", output.getvalue())
        self.assertIn("no se ejecutaron comandos externos", output.getvalue())

    def test_http_server_keeps_process_directory_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            server = MODULE.PayloadHTTPServer(directory)
            before = Path.cwd()
            with patch.object(server, "_obtener_ip_local", return_value="127.0.0.1"):
                server.iniciar()
                server.detener()
            self.assertEqual(Path.cwd(), before)

    def test_netcat_rejects_invalid_port_before_process(self):
        sender = MODULE.PayloadSender("/tmp/lab-marker")
        with patch.object(MODULE.subprocess, "run") as run:
            with self.assertRaises(ValueError):
                sender.enviar_nc("127.0.0.1", "4444;id")
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
