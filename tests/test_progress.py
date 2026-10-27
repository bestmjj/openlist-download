import os
import tempfile
import unittest
from unittest.mock import patch
from openlist_downloader.progress import TransferProgress, format_eta, format_size
from openlist_downloader.downloader import OpenListDownloader


class FakeResponse:
    headers = {"Content-Length": "6"}

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
        self.obj._print_lock = __import__("threading").Lock()
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
