"""Browser launch waits for successful startup; dependencies are installed once."""
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import run_web
from viralcut import __main__ as cli


class WebLauncherTests(unittest.TestCase):
    def test_browser_waits_for_server(self):
        server = SimpleNamespace(started=False, should_exit=False)
        def start(_):
            opener.assert_not_called()
            server.started = True
        with patch.object(cli.time, 'sleep', side_effect=start), patch.object(cli.webbrowser, 'open') as opener:
            cli._open_when_ready(server, 'http://127.0.0.1:8765/')
        opener.assert_called_once_with('http://127.0.0.1:8765/')

    def test_failed_startup_does_not_open_browser(self):
        with patch.object(cli.webbrowser, 'open') as opener:
            cli._open_when_ready(SimpleNamespace(started=False, should_exit=True), 'http://127.0.0.1:8765/')
        opener.assert_not_called()

    def test_repeated_launch_skips_install_and_forwards_port(self):
        with TemporaryDirectory(prefix='viralcut space ') as tmp:
            root = Path(tmp)
            req = root/'requirements.txt'; req.write_text('fastapi\n')
            env = root/'.venv-web'; python = env/('Scripts/python.exe' if run_web.os.name == 'nt' else 'bin/python')
            python.parent.mkdir(parents=True); python.touch()
            (env/'.requirements-sha256').write_text(hashlib.sha256(req.read_bytes()).hexdigest())
            with patch.object(run_web, 'ROOT', root), patch.object(run_web.sys, 'argv', ['run_web.py','--port','8770']), \
                 patch.object(run_web.subprocess, 'run') as install, patch.object(run_web.subprocess, 'call', return_value=0) as launch:
                self.assertEqual(run_web.main(), 0)
            install.assert_not_called()
            launch.assert_called_once_with([str(python),'-m','viralcut','--open-browser','--port','8770'],cwd=root)
