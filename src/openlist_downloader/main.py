#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
OpenList 下载器应用程序的主入口点。

该模块提供命令行接口，用于处理参数解析和执行下载过程。
"""

import argparse

# 处理直接执行和模块执行两种情况的导入
try:
    # 作为模块运行时
    from .downloader import OpenListDownloader
except ImportError:
    # 直接作为脚本运行时
    from downloader import OpenListDownloader


def main():
    """
    运行 OpenList 下载器的主函数。
    
    解析命令行参数并启动下载过程。
    优雅地处理键盘中断和其他异常。
    """
    parser = argparse.ArgumentParser(description="OpenList 下载器")
    parser.add_argument("--list-only", action="store_true", help="仅列出并保存 filelist.json")
    parser.add_argument("--download-only", action="store_true", help="跳过列目录，使用 filelist.json")
    parser.add_argument("--upload-only", action="store_true", help="仅上传本地文件到远程目录")
    parser.add_argument("--workers", type=int, default=10, help="并发线程数(默认: 10)")
    parser.add_argument("--diagnose-speed", action="store_true", help="测量同一网盘直链的 Python 与 curl 速度（每种方式最多读取 2 MiB）")
    parser.add_argument("--config", default="config.json", help="配置文件路径 (默认: config.json)")
    args = parser.parse_args()

    try:
        downloader = OpenListDownloader(config_path=args.config)
        downloader.run(
            list_only=args.list_only,
            download_only=args.download_only,
            upload_only=args.upload_only,
            workers=args.workers,
            diagnose_speed=args.diagnose_speed
        )
    except KeyboardInterrupt:
        print("\n[INFO] ⏹️ 用户中断。")
    except Exception as e:
        print(f"[FATAL] 💥 {e}")
        raise


if __name__ == "__main__":
    main()