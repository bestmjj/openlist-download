"""Bounded download speed probes for a signed OpenList raw_url.

Never print or put signed URLs on a subprocess command line. Each probe reads at
most sample_bytes and does not write any downloaded content to disk.
"""

import os
import shutil
import subprocess
import time

import requests

try:
    from .progress import format_size
except ImportError:
    from progress import format_size


PROXY_ENV_NAMES = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
                   "http_proxy", "https_proxy", "all_proxy")


def active_proxy_environment():
    """Return proxy variable names only (values may contain passwords)."""
    return [name for name in PROXY_ENV_NAMES if os.environ.get(name)]


def _result(status=None, received=0, elapsed=0, error=None):
    speed = received / elapsed if elapsed > 0 else 0.0
    return {
        "status": status,
        "received": received,
        "elapsed": elapsed,
        "speed": speed,
        "error": error,
    }


def describe_probe(label, probe):
    """Display only status and measurements; never include a signed URL."""
    if probe["error"]:
        return "[DIAG] {}：失败（{}，HTTP={}）".format(
            label, probe["error"], probe["status"] or "--"
        )
    return "[DIAG] {}：HTTP {}，接收 {}，耗时 {:.1f}s，平均 {}/s".format(
        label,
        probe["status"],
        format_size(probe["received"]),
        probe["elapsed"],
        format_size(probe["speed"]),
    )


def probe_python(url, sample_bytes, timeout, bypass_proxy=False):
    """Match the downloader's requests transport, optionally bypassing env proxy."""
    session = requests.Session()
    session.trust_env = not bypass_proxy
    received = 0
    started = time.monotonic()
    status = None
    try:
        with session.get(
            url,
            headers={"Range": "bytes=0-{}".format(sample_bytes - 1)},
            stream=True,
            timeout=(min(timeout, 10), min(timeout, 20)),
        ) as response:
            status = response.status_code
            response.raise_for_status()
            for block in response.iter_content(chunk_size=65536):
                if not block:
                    continue
                received += min(len(block), sample_bytes - received)
                if received >= sample_bytes:
                    break
        return _result(status, received, time.monotonic() - started)
    except requests.RequestException as exc:
        # requests errors often embed the full signed URL: log the type only.
        return _result(status, received, time.monotonic() - started,
                       type(exc).__name__)
    finally:
        session.close()


def _curl_config_url(url):
    """Pass curl's signed URL via stdin rather than exposing it in argv or logs."""
    escaped = (url.replace("\\", "\\\\")
                   .replace('"', '\\"')
                   .replace("\r", "%0D")
                   .replace("\n", "%0A"))
    return 'url = "{}"\n'.format(escaped)


def probe_curl_ipv4(url, sample_bytes, timeout):
    """Use curl over IPv4 without environment proxies as a comparison."""
    if not shutil.which("curl"):
        return _result(error="curl 未安装")
    max_seconds = max(30, min(60, int(timeout) * 2))
    cmd = [
        "curl", "--silent", "--show-error", "--location", "--http1.1",
        "--ipv4", "--noproxy", "*",
        "--range", "0-{}".format(sample_bytes - 1),
        "--max-filesize", str(sample_bytes),
        "--connect-timeout", "10", "--max-time", str(max_seconds),
        "--output", "/dev/null", "--write-out",
        "%{http_code} %{size_download} %{time_total}",
        "--config", "-",
    ]
    try:
        done = subprocess.run(
            cmd, input=_curl_config_url(url), text=True, capture_output=True,
            timeout=max_seconds + 5, check=False,
        )
        parts = done.stdout.strip().split()
        if len(parts) != 3:
            return _result(error="curl 退出码 {}".format(done.returncode))
        status = int(parts[0])
        received = min(sample_bytes, int(float(parts[1])))
        elapsed = float(parts[2])
        error = "curl 退出码 {}".format(done.returncode) if done.returncode else None
        return _result(status, received, elapsed, error)
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        return _result(error=type(exc).__name__)
