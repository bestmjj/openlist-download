#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import requests
from urllib.parse import quote
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
        self.session.headers.update({"Content-Type": "application/json"})
        self.token = None

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
        try:
            print(msg)
        except UnicodeEncodeError:
            print(msg.encode("utf-8", errors="replace").decode("utf-8"))

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
        """
        从 OpenList 下载文件到本地存储。
        
        首先尝试使用原始 URL 下载，如果失败则回退到流方法。
        如果启用了 skip_existing 且文件大小匹配，则跳过现有文件。
        
        Args:
            remote_path (str): 远程文件的路径
            local_path (str): 保存文件的本地路径
        """
        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        if self.skip_existing and os.path.exists(local_path):
            local_size = os.path.getsize(local_path)
            if local_size > 0:
                remote_size = self.get_file_size(remote_path)
                if remote_size is not None and local_size == remote_size:
                    self.print(f"[SKIP] ✅ 已存在：{local_path}")
                    return

        # 首先尝试 raw_url
        url = f"{self.openlist_url}/api/fs/get"
        payload = {"path": remote_path, "password": ""}
        try:
            resp = self.session.post(url, json=payload, timeout=self.timeout)
            # 安全地解析 JSON
            data = None
            try:
                data = resp.json()
            except ValueError:
                data = None

            if resp.status_code != 200 or not data or data.get("code") != 200:
                # 如果响应不可用，则回退到流
                self._download_via_stream(remote_path, local_path)
                return

            raw_url = data["data"].get("raw_url")
            if not raw_url:
                self._download_via_stream(remote_path, local_path)
                return

            self.print(f"[DOWNLOAD] 🔗 使用 raw_url：{remote_path}")
            with requests.get(raw_url, stream=True, timeout=self.timeout) as r:
                if r.status_code != 200:
                    self.print(f"[ERROR] ❌ raw_url 失败（{r.status_code}）")
                    return
                with open(local_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=65536):
                        f.write(chunk)
            self.print(f"[OK] ✅ 已保存：{local_path}")

        except Exception as e:
            self.print(f"[ERROR] ❌ 下载失败：{e}")

    def _download_via_stream(self, remote_path, local_path):
        """
        使用流 API 下载文件。
        
        当直接下载失败时使用的私有回退方法。
        
        Args:
            remote_path (str): 远程文件的路径
            local_path (str): 保存文件的本地路径
        """
        url = f"{self.openlist_url}/api/fs/stream"
        payload = {"path": remote_path, "password": ""}
        try:
            resp = self.session.post(url, json=payload, stream=True, timeout=self.timeout)
            if resp.status_code == 200:
                with open(local_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=65536):
                        f.write(chunk)
                self.print(f"[OK] ✅ 通过流已保存：{local_path}")
            else:
                self.print(f"[ERROR] ❌ 流失败（{resp.status_code}）")
        except Exception as e:
            self.print(f"[ERROR] ❌ 流异常：{e}")

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

    def run(self, list_only=False, download_only=False, workers=10):
        """
        运行下载器进程。
        
        协调文件列出和下载的主要方法。
        
        Args:
            list_only (bool): 如果为 True，则仅列出文件并保存到 filelist.json
            download_only (bool): 如果为 True，则跳过列目录并从现有的 filelist.json 下载
            workers (int): 并发下载线程数。默认为 10。
        """
        self.login()

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
            total = len(futures)
            for _ in as_completed(futures):
                completed += 1
                if completed % 20 == 0 or completed == total:
                    self.print(f"[PROGRESS] 📥 {completed}/{total}")

        self.print("[INFO] 🎉 所有下载完成！")