"""
OpenList 下载器 - 一个从 OpenList 下载文件的工具。

该包提供与 OpenList 实例进行身份验证的功能，
从远程目录递归列出文件，并支持多线程和可恢复下载的方式将文件下载到本地目录。

类：
    OpenListDownloader: 从 OpenList 下载文件的主类
    
示例：
    >>> from openlist_downloader import OpenListDownloader
    >>> downloader = OpenListDownloader("config.json")
    >>> downloader.run()
"""

__version__ = "1.0.0"
__author__ = "Unknown"

from .downloader import OpenListDownloader

__all__ = ["OpenListDownloader"]