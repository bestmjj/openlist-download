import os
import tempfile
import unittest
import threading
from unittest.mock import patch
from openlist_downloader.progress import TransferProgress, format_eta, format_size
from openlist_downloader.downloader import OpenListDownloader


class FakeResponse:
    headers = {"Content-Length": "6"}
    url = "https://cdn.example.test/media?signature=private-key"
    history = []

    def __init__(self, chunks):
        self.chunks = chunks

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size):
        return iter(self.chunks)


class ProgressTests(unittest.TestCase):
    def test_formatting(self):
        self.assertEqual(format_size(1048576), "1.0 MiB")
        self.assertEqual(format_eta(65), "01:05")

    def test_percentage_speed_eta(self):
        lines = []
        now = [0.]
        tracker = TransferProgress("test.mp4", 2048, lines.append, interval=1, clock=lambda: now[0])
        tracker.update(1024)
        now[0] = 1.
        tracker.update(1)
        self.assertIn("50.0%", lines[0])
        self.assertIn("1.0 KiB/s", lines[0])
        self.assertIn("ETA 00:01", lines[0])
        tracker.update(1023)
        tracker.finish()
        self.assertIn("100.0%", lines[-1])

    def test_unknown_total(self):
        lines = []
        now = [0.]
        tracker = TransferProgress("test.mp4", None, lines.append, interval=1, clock=lambda: now[0])
        now[0] = 2.
        tracker.update(2048)
        self.assertIn("大小未知", lines[0])


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.obj = OpenListDownloader.__new__(OpenListDownloader)
        self.obj.timeout = 30
        self.obj._print_lock = threading.Lock()
        self.obj._stop_event = threading.Event()
        self.logs = []
        self.obj.print = self.logs.append

    @patch("openlist_downloader.downloader.requests.request")
    def test_complete_download_promotes_part(self, request):
        request.return_value = FakeResponse([b"abc", b"def"])
        with tempfile.TemporaryDirectory() as directory:
            dst = os.path.join(directory, "video.mp4")
            self.assertTrue(self.obj._download_stream("https://example.com", dst, 6))
            with open(dst, "rb") as file:
                self.assertEqual(file.read(), b"abcdef")
            self.assertFalse(os.path.exists(dst + ".part"))
            self.assertTrue(any("100.0%" in line for line in self.logs))
            self.assertTrue(any("实际下载域名：cdn.example.test" in line for line in self.logs))
            self.assertNotIn("private-key", "\n".join(self.logs))

    @patch("openlist_downloader.downloader.requests.request")
    def test_redirect_domains_logged_without_signed_url(self, request):
        from types import SimpleNamespace

        redirect_response = FakeResponse([b"abc", b"def"])
        redirect_response.history = [
            SimpleNamespace(url="https://openlist.example.test/p/file?sign=hidden-value"),
        ]
        request.return_value = redirect_response
        with tempfile.TemporaryDirectory() as directory:
            dst = os.path.join(directory, "video.mp4")
            self.assertTrue(self.obj._download_stream("https://openlist.example.test/p/file", dst, 6))
        self.assertTrue(any("下载跳转域名：openlist.example.test -> cdn.example.test" in line for line in self.logs))
        self.assertNotIn("hidden-value", "\n".join(self.logs))
        self.assertNotIn("private-key", "\n".join(self.logs))

    @patch("openlist_downloader.downloader.requests.request")
    def test_interrupt_stops_writing_and_preserves_part(self, request):
        def chunks():
            yield b"abc"
            self.obj._stop_event.set()
            yield b"def"
        request.return_value = FakeResponse(chunks())
        with tempfile.TemporaryDirectory() as directory:
            dst = os.path.join(directory, "video.mp4")
            self.assertFalse(self.obj._download_stream("https://example.com", dst, 6))
            self.assertFalse(os.path.exists(dst))
            with open(dst + ".part", "rb") as file:
                self.assertEqual(file.read(), b"abc")
            self.assertFalse(any("已保存" in line for line in self.logs))

    def test_ctrl_c_cancels_pending_work_and_sets_stop_signal(self):
        self.obj.login = lambda: None
        self.obj.load_filelist = lambda: [{"path": "/test"}]
        self.obj.local_save_dir = "/tmp"
        self.obj.download_file = lambda path, local: True
        with patch("openlist_downloader.downloader.as_completed", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.obj.run(download_only=True, workers=1)
        self.assertTrue(self.obj._stop_event.is_set())

    @patch("openlist_downloader.downloader.requests.request")
    def test_incomplete_download_keeps_final_untouched(self, request):
        request.return_value = FakeResponse([b"abc"])
        with tempfile.TemporaryDirectory() as directory:
            dst = os.path.join(directory, "video.mp4")
            with open(dst, "wb") as file:
                file.write(b"existing")
            with self.assertRaises(ValueError):
                self.obj._download_stream("https://example.com", dst, 6)
            with open(dst, "rb") as file:
                self.assertEqual(file.read(), b"existing")
            self.assertTrue(os.path.exists(dst + ".part"))


if __name__ == "__main__":
    unittest.main()
