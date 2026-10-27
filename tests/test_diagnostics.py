import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from openlist_downloader.diagnostics import (
    _curl_config_url,
    active_proxy_environment,
    describe_probe,
    probe_curl_ipv4,
    probe_python,
)
from openlist_downloader.downloader import OpenListDownloader


class FakeResponse:
    def __init__(self, chunks, status=206):
        self.chunks = chunks
        self.status_code = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size):
        return iter(self.chunks)


class DiagnosticsTests(unittest.TestCase):
    @patch("openlist_downloader.diagnostics.requests.Session")
    def test_python_probe_limits_download_and_bypasses_proxy(self, make_session):
        session = make_session.return_value
        session.get.return_value = FakeResponse([b"a" * 8192] * 5)
        result = probe_python(
            "https://cdn.example.test/video.mp4?signature=secret",
            10000, 20, bypass_proxy=True,
        )
        self.assertEqual(result["status"], 206)
        self.assertEqual(result["received"], 10000)
        self.assertIsNone(result["error"])
        self.assertFalse(session.trust_env)
        self.assertEqual(session.get.call_args.kwargs["headers"]["Range"],
                         "bytes=0-9999")
        session.close.assert_called_once()

    @patch("openlist_downloader.diagnostics.subprocess.run")
    @patch("openlist_downloader.diagnostics.shutil.which", return_value="/usr/bin/curl")
    def test_curl_uses_stdin_for_signed_url(self, which, run):
        run.return_value = SimpleNamespace(
            stdout="206 2097152 1.5", stderr="", returncode=0,
        )
        url = 'https://cdn.example.test/download?signature=secret&test=1'
        result = probe_curl_ipv4(url, 2097152, 30)
        self.assertEqual(result["received"], 2097152)
        self.assertEqual(result["status"], 206)
        self.assertIsNone(result["error"])
        cmd = run.call_args.args[0]
        self.assertNotIn("secret", " ".join(cmd))
        self.assertIn("--noproxy", cmd)
        self.assertIn("--ipv4", cmd)
        self.assertIn(url, run.call_args.kwargs["input"])
        self.assertIn('url = "', _curl_config_url(url))

    def test_environment_lists_names_not_values(self):
        with patch.dict("os.environ", {"HTTPS_PROXY": "http://password:secret@proxy.example"}, clear=True):
            self.assertEqual(active_proxy_environment(), ["HTTPS_PROXY"])

    @patch("openlist_downloader.downloader.probe_curl_ipv4")
    @patch("openlist_downloader.downloader.probe_python")
    @patch("openlist_downloader.downloader.active_proxy_environment", return_value=[])
    def test_cli_diagnosis_does_not_log_signed_url(self, proxy_env, python_probe, curl_probe):
        python_probe.return_value = {
            "status": 206, "received": 2097152, "elapsed": 10.0,
            "speed": 209715.2, "error": None,
        }
        curl_probe.return_value = python_probe.return_value
        obj = OpenListDownloader.__new__(OpenListDownloader)
        obj.openlist_url = "http://localhost:8003"
        obj.timeout = 30
        obj.remote_path = "/aliyun/videos"
        obj.load_filelist = lambda: [
            {"path": "/aliyun/videos/video.mp4", "size": 10485760},
        ]
        reply = Mock()
        reply.json.return_value = {
            "code": 200,
            "data": {"raw_url": "https://cdn.example.test/a?signature=secret"},
        }
        obj.session = Mock()
        obj.session.post.return_value = reply
        output = []
        obj.print = output.append
        obj.diagnose_speed()
        combined = "\n".join(output)
        self.assertIn("cdn.example.test", combined)
        self.assertIn("Python 当前网络配置", combined)
        self.assertIn("curl IPv4", combined)
        self.assertNotIn("signature=secret", combined)
        self.assertEqual(python_probe.call_count, 2)


if __name__ == "__main__":
    unittest.main()
