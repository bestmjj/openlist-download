#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import requests
import threading
from urllib.parse import urlparse
try:
    from .progress import TransferProgress
except ImportError:
    from progress import TransferProgress
from concurrent.futures import ThreadPoolExecutor, as_completed


class OpenListDownloader:
    """
    用于从 OpenList 服务下载文件的类。
    
    该类提供与 OpenList 实例进行身份验证、递归列出文件以及将文件下载到本地目录的功能。
    """

    def __init__(self, config_path="config.json"):
        """
        初始化 OpenListDownloader。
        
        Args:
            config_path (str): 配置 JSON 文件的路径。默认为 "config.json"。
        """
        self.config_path = config_path
        self.load_config()
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "openlist-downloader/1.0"
        })
        self.token = None
        self._print_lock = threading.Lock()

    def load_config(self):
        """
        从 JSON 文件加载配置。
        
        从指定的配置文件中读取配置值并相应地设置实例属性。必需的配置键包括：
        - openlist_url: OpenList 实例的 URL
        - username: 用于身份验证的用户名
        - password: 用于身份验证的密码
        - remote_path: 要从中下载的远程目录路径
        - local_save_dir: 保存下载文件的本地目录
        
        可选配置键及其默认值：
        - page_size: 每页的项目数（默认：200）
        - timeout: 请求超时时间（秒）（默认：30）
        - skip_existing: 跳过现有文件（默认：True）
        - upload: 上传配置对象（可选）
          - local_path: 本地待上传文件目录
          - remote_upload_path: 远程上传目标目录
        """
        with open(self.config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        self.openlist_url = config["openlist_url"].strip().rstrip("/")
        self.username = config.get("username")
        self.password = config.get("password")
        # self.token = config.get("token")  # 可选，当前优先用账号登录
        self.remote_path = config["remote_path"]
        self.local_save_dir = config["local_save_dir"]
        self.page_size = config.get("page_size", 200)
        self.timeout = config.get("timeout", 30)
        self.skip_existing = config.get("skip_existing", True)
        self.upload_config = config.get("upload", {})

    def login(self):
        """
        与 OpenList 实例进行身份验证。
        
        使用提供的令牌或用户名/密码凭据与 OpenList 实例进行身份验证。
        身份验证成功后，使用授权令牌更新会话头。
        
        异常：
            ValueError: 当未提供令牌且缺少用户名或密码时抛出。
            Exception: 登录请求失败或返回错误时抛出。
        """
        if self.token:
            self.session.headers.update({"Authorization": self.token})
            self.print("[INFO] 使用提供的令牌。")
            return

        if not self.username or not self.password:
            raise ValueError("config.json 中缺少用户名/密码")

        self.print(f"[INFO] 正在登录到 {self.openlist_url}...")
        url = f"{self.openlist_url}/api/auth/login"
        payload = {"username": self.username, "password": self.password}
        try:
            resp = self.session.post(url, json=payload, timeout=self.timeout)
            try:
                data = resp.json()
            except ValueError:
                # 非 JSON 响应（空正文或 HTML 错误），提供有用的信息
                raise Exception(f"登录失败：非 JSON 响应（状态 {resp.status_code}）：{resp.text!r}")

            if data.get("code") == 200:
                self.token = data["data"]["token"]
                self.session.headers.update({"Authorization": self.token})
                self.print("[INFO] 登录成功。")
            else:
                raise Exception(f"登录失败：{data}")
        except Exception as e:
            raise Exception(f"[ERROR] 登录请求失败：{e}")

    def print(self, msg):
        """
        打印消息到标准输出，处理编码错误。
        
        Args:
            msg (str): 要打印的消息
        """
        with self._print_lock:
            try:
                print(msg, flush=True)
            except UnicodeEncodeError:
                print(msg.encode("utf-8", errors="replace").decode("utf-8"), flush=True)

    def list_dir(self, path):
        """
        递归列出目录中的文件。
        
        Args:
            path (str): 要列出的目录路径
            
        Returns:
            list: 包含文件名字典的列表，每个字典包含名称、路径和大小
        """
        files = []
        page = 1
        total_in_dir = 0
        self.print(f"[DEBUG] 📂 正在列出：{path}")

        while True:
            url = f"{self.openlist_url}/api/fs/list"
            payload = {
                "path": path,
                "password": "",
                "page": page,
                "per_page": self.page_size
            }
            self.print(f"[DEBUG] 📥 正在请求 '{path}' 的第 {page} 页...")
            try:
                resp = self.session.post(url, json=payload, timeout=self.timeout)
            except requests.Timeout:
                self.print(f"[ERROR] ⏱️ '{path}' 的第 {page} 页超时")
                break
            except Exception as e:
                self.print(f"[ERROR] ❌ 第 {page} 页异常：{e}")
                break

            if resp.status_code != 200:
                self.print(f"[ERROR] 🚫 '{path}' 第 {page} 页 HTTP {resp.status_code}")
                break

            try:
                data = resp.json()
            except ValueError:
                self.print(f"[ERROR] 🚫 '{path}' 第 {page} 页响应中的 JSON 无效：{resp.text!r}")
                break

            if data.get("code") != 200:
                self.print(f"[ERROR] 🚫 API 错误：{data}")
                break

            content = data["data"]["content"]
            if not content:
                break

            current_count = len(content)
            total_in_dir += current_count
            self.print(f"[DEBUG] ✅ 第 {page} 页：{current_count} 个项目（目录总计：{total_in_dir}）")

            for item in content:
                full_path = f"{path.rstrip('/')}/{item['name']}"
                if item["is_dir"]:
                    self.print(f"[DEBUG] 📁 进入：{full_path}")
                    files.extend(self.list_dir(full_path))
                else:
                    files.append({
                        "name": item["name"],
                        "path": full_path,
                        "size": item.get("size", 0)
                    })

            if current_count < self.page_size:
                break
            page += 1

        self.print(f"[DEBUG] 📦 '{path}' 完成：{len(files)} 个文件")
        return files

    def get_file_size(self, remote_path):
        """
        获取远程文件的大小。
        
        Args:
            remote_path (str): 远程文件的路径
            
        Returns:
            int or None: 文件大小（字节），如果失败则返回 None
        """
        url = f"{self.openlist_url}/api/fs/get"
        payload = {"path": remote_path, "password": ""}
        try:
            resp = self.session.post(url, json=payload, timeout=self.timeout)
            if resp.status_code == 200:
                try:
                    data = resp.json()
                except ValueError:
                    self.print(f"[WARN] 获取 {remote_path} 大小时收到非 JSON 响应：{resp.text!r}")
                    return None
                if data.get("code") == 200:
                    return data["data"].get("size", 0)
        except Exception as e:
            self.print(f"[WARN] 获取 {remote_path} 大小失败：{e}")
        return None

    def download_file(self, remote_path, local_path):
        """Download with per-file speed, percent and ETA; never expose partial final files."""
        os.makedirs(os.path.dirname(os.path.abspath(local_path)), exist_ok=True)
        expected_size = self.get_file_size(remote_path)
        if self.skip_existing and os.path.isfile(local_path) and expected_size is not None:
            if os.path.getsize(local_path) == expected_size:
                self.print("[SKIP] ✅ 已存在：{}".format(local_path))
                return True

        url = "{}/api/fs/get".format(self.openlist_url)
        payload = {"path": remote_path, "password": ""}
        try:
            response = self.session.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            result = response.json()
            raw_url = result.get("data", {}).get("raw_url") if result.get("code") == 200 else None
        except (requests.RequestException, ValueError, AttributeError) as exc:
            self.print("[WARN] 获取直链失败，尝试流模式：{}".format(exc))
            raw_url = None

        if raw_url:
            self.print("[DOWNLOAD] 🔗 使用 raw_url：{}".format(remote_path))
            self.print("[DEBUG] raw_url 域名：{}".format(urlparse(raw_url).hostname or "未知"))
            try:
                return self._download_stream(raw_url, local_path, expected_size)
            except (requests.RequestException, OSError, ValueError) as exc:
                self.print("[WARN] 直链下载失败，尝试流模式：{}".format(exc))

        return self._download_via_stream(remote_path, local_path, expected_size)

    def _download_stream(self, url, local_path, expected_size=None, method="get", payload=None, authenticated=False):
        """Stream into a .part file and promote only after full size validation."""
        part_path = local_path + ".part"
        # A previous partial download is discarded: this code does NOT yet support
        # HTTP Range resume. Avoid claiming resumability without validating 206.
        client = self.session if authenticated else requests
        with client.request(method, url, json=payload, stream=True, timeout=self.timeout) as response:
            # Never log the full URL: signed download URLs may contain secrets.
            response_url = getattr(response, "url", None) or url
            final_domain = urlparse(response_url).hostname or "未知"
            redirect_domains = [urlparse(hop.url).hostname or "未知" for hop in getattr(response, "history", [])]
            if redirect_domains:
                self.print("[DEBUG] 下载跳转域名：{}".format(" -> ".join(redirect_domains + [final_domain])))
            else:
                self.print("[DEBUG] 实际下载域名：{}".format(final_domain))
            response.raise_for_status()
            response_size = response.headers.get("Content-Length")
            response_size = int(response_size) if response_size and response_size.isdigit() else None
            if expected_size is not None and response_size is not None and response_size != expected_size:
                raise ValueError("文件大小不一致：远端={} 响应={}".format(expected_size, response_size))
            total = expected_size if expected_size is not None else response_size
            progress = TransferProgress(local_path, total, self.print)
            try:
                with open(part_path, "wb") as output:
                    for chunk in response.iter_content(chunk_size=65536):
                        if chunk:
                            output.write(chunk)
                            progress.update(len(chunk))
                if total is not None and progress.downloaded != total:
                    raise ValueError("文件下载不完整：期望 {}，实际 {}".format(total, progress.downloaded))
                os.replace(part_path, local_path)
                progress.finish()
                self.print("[OK] ✅ 已保存：{}".format(local_path))
                return True
            except Exception:
                # Preserve .part for inspection; never treat it as a finished file.
                raise

    def _download_via_stream(self, remote_path, local_path, expected_size=None):
        """Fallback to OpenList's stream API with the same progress reporter."""
        try:
            return self._download_stream(
                "{}/api/fs/stream".format(self.openlist_url),
                local_path, expected_size, method="post",
                payload={"path": remote_path, "password": ""}, authenticated=True,
            )
        except (requests.RequestException, OSError, ValueError) as exc:
            self.print("[ERROR] ❌ 下载失败 {}：{}".format(remote_path, exc))
            return False

    def save_filelist(self, filelist, path="filelist.json"):
        """
        将文件列表保存到 JSON 文件。
        
        Args:
            filelist (list): 要保存的文件字典列表
            path (str): 保存文件列表的路径。默认为 "filelist.json"。
        """
        with open(path, "w", encoding="utf-8") as f:
            json.dump(filelist, f, ensure_ascii=False, indent=2)
        self.print(f"[INFO] 📝 文件列表已保存到 {path}")

    def load_filelist(self, path="filelist.json"):
        """
        从 JSON 文件加载文件列表。
        
        Args:
            path (str): 加载文件列表的路径。默认为 "filelist.json"。
            
        Returns:
            list or None: 文件字典列表，如果文件不存在则返回 None
        """
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def upload_file(self, local_path, remote_path):
        """
        上传本地文件到 OpenList 服务器。
        
        Args:
            local_path (str): 本地文件路径
            remote_path (str): 远程目标路径
        """
        if not os.path.exists(local_path):
            self.print(f"[ERROR] 本地文件不存在: {local_path}")
            return False

        # 创建目录（如果尚不存在）
        dir_path = '/'.join(remote_path.split('/')[:-1])
        if dir_path:
            self.create_directory(dir_path)

        # 使用 PUT 方法上传文件，模拟浏览器请求
        try:
            # 获取文件的最后修改时间
            import time
            last_modified = str(int(os.path.getmtime(local_path) * 1000))
            
            # 对路径进行URL编码，先UTF-8编码再URL编码
            encoded_path = requests.utils.quote(remote_path.encode('utf-8'))
            
            headers = {
                "Authorization": self.token,
                "File-Path": encoded_path,
                "Last-Modified": last_modified,
                "Overwrite": "false",
            }
            
            #self.print(f"[DEBUG] 正在使用 PUT 方法上传文件: {local_path} -> {remote_path}")
            upload_url = f"{self.openlist_url}/api/fs/put"
            
            with open(local_path, 'rb') as f:
                upload_resp = requests.put(upload_url, data=f, headers=headers, timeout=self.timeout)
                
                #self.print(f"[DEBUG] 上传响应状态: {upload_resp.status_code}")
                #self.print(f"[DEBUG] 上传响应头部: {dict(upload_resp.headers)}")
                
                # 尝试解析 JSON 响应
                try:
                    response_data = upload_resp.json()
                    self.print(f"[DEBUG] 上传响应: {response_data}")
                    if upload_resp.status_code in [200, 201, 204]:
                        if response_data.get("code") == 200:
                            self.print(f"[OK] ✅ 已上传: {local_path} -> {remote_path}")
                            return True
                        else:
                            # 显示具体的文件名和错误信息
                            self.print(f"[ERROR] ❌ 上传失败 {os.path.basename(remote_path)}: {response_data}")
                            return False
                    else:
                        self.print(f"[ERROR] ❌ 上传失败，HTTP状态码: {upload_resp.status_code}")
                        return False
                except ValueError:
                    response_text = upload_resp.text[:1000] if upload_resp.text else "Empty response"
                    self.print(f"[ERROR] ❌ 上传失败，非 JSON 响应 ({upload_resp.status_code}): {response_text}")
                    return False
                    
        except Exception as e:
            self.print(f"[ERROR] ❌ 上传异常 {os.path.basename(remote_path)}: {e}")
            return False

    def create_directory(self, path):
        """
        在 OpenList 服务器上创建目录。
        
        Args:
            path (str): 要创建的远程目录路径
        """
        # 使用直接的requests而不是session，确保使用正确的认证方式
        headers = {
            "Authorization": self.token,  # 使用原始token而不是Bearer格式
            "Content-Type": "application/json",
            "User-Agent": "openlist-downloader/1.0"
        }
            
        url = f"{self.openlist_url}/api/fs/mkdir"
        payload = {
            "path": path,
            "password": ""
        }
        
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
            
            # 安全地解析 JSON
            data = None
            try:
                data = resp.json()
            except ValueError:
                response_preview = resp.text[:500] if resp.text else "Empty response"
                self.print(f"[ERROR] 创建目录失败，非 JSON 响应（状态 {resp.status_code}）：{response_preview!r}")
                return False
            
            if resp.status_code == 200 and data.get("code") == 200:
                self.print(f"[INFO] 创建目录成功: {path}")
                return True
            elif data and "already exists" in data.get("message", ""):
                # 目录已存在，这不是错误
                return True
            elif resp.status_code == 401:
                self.print(f"[ERROR] 认证失败: 令牌无效或已过期")
                return False
            else:
                self.print(f"[ERROR] 创建目录失败: {data}")
                return False
        except Exception as e:
            self.print(f"[ERROR] 创建目录异常: {e}")
            return False

    def list_local_files(self, local_path):
        """
        列出本地目录中的所有文件。
        
        Args:
            local_path (str): 本地目录路径
            
        Returns:
            list: 文件路径列表
        """
        files = []
        for root, _, filenames in os.walk(local_path):
            for filename in filenames:
                full_path = os.path.join(root, filename)
                rel_path = os.path.relpath(full_path, local_path)
                files.append((full_path, rel_path))
        return files

    def run(self, list_only=False, download_only=False, upload_only=False, workers=10):
        """
        运行下载器进程。
        
        协调文件列出和下载的主要方法。
        
        Args:
            list_only (bool): 如果为 True，则仅列出文件并保存到 filelist.json
            download_only (bool): 如果为 True，则跳过列目录并从现有的 filelist.json 下载
            upload_only (bool): 如果为 True，则只上传文件
            workers (int): 并发下载线程数。默认为 10。
        """
        self.login()

        if upload_only:
            # 处理上传任务
            local_upload_path = self.upload_config.get("local_path")
            remote_upload_path = self.upload_config.get("remote_upload_path")
            
            if not local_upload_path or not remote_upload_path:
                raise ValueError("上传模式需要在配置文件中指定 local_path 和 remote_upload_path")
                
            if not os.path.exists(local_upload_path):
                raise FileNotFoundError(f"本地上传目录不存在: {local_upload_path}")
                
            self.print(f"[INFO] 📤 开始上传文件从 {local_upload_path} 到 {remote_upload_path}")
            local_files = self.list_local_files(local_upload_path)
            
            if not local_files:
                self.print("[WARN] ⚠️ 未找到要上传的文件。")
                return
                
            self.print(f"[INFO] 📋 总共找到 {len(local_files)} 个文件")
            
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = []
                for local_file, rel_path in local_files:
                    remote_file = os.path.join(remote_upload_path, rel_path).replace("\\", "/")
                    futures.append(executor.submit(self.upload_file, local_file, remote_file))
                    
                completed = 0
                total = len(futures)
                for _ in as_completed(futures):
                    completed += 1
                    if completed % 10 == 0 or completed == total:
                        self.print(f"[PROGRESS] 📤 {completed}/{total}")
                        
            self.print("[INFO] 🎉 所有上传完成！")
            return

        if download_only:
            self.print("[INFO] 📥 使用现有的 filelist.json")
            all_files = self.load_filelist()
            if not all_files:
                raise FileNotFoundError("未找到 filelist.json。请先不带 --download-only 参数运行。")
        else:
            self.print(f"[INFO] 🚀 正在列出目录：{self.remote_path}")
            all_files = self.list_dir(self.remote_path)
            self.save_filelist(all_files)
            if list_only:
                self.print("[INFO] 📋 仅列出模式。正在退出。")
                return

        if not all_files:
            self.print("[WARN] ⚠️ 未找到文件。")
            return

        self.print(f"[INFO] 📋 总文件数：{len(all_files)}")
        self.print(f"[INFO] ⚙️ 使用 {workers} 个下载线程")

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = []
            for file_info in all_files:
                local_file = os.path.join(
                    self.local_save_dir,
                    os.path.relpath(file_info["path"], start="/")
                )
                futures.append(executor.submit(self.download_file, file_info["path"], local_file))

            completed = 0
            failed = 0
            total = len(futures)
            for future in as_completed(futures):
                completed += 1
                try:
                    if not future.result():
                        failed += 1
                except Exception as exc:
                    failed += 1
                    self.print(f"[ERROR] 下载任务异常：{exc}")
                if completed % 20 == 0 or completed == total:
                    self.print(f"[PROGRESS] 📥 {completed}/{total}（失败 {failed}）")

        self.print(f"[INFO] 下载结束：成功/跳过 {total - failed}，失败 {failed}")