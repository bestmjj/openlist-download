# OpenList 下载器

一个从 OpenList 下载文件的工具 - OpenList 是一个支持多种存储提供商的文件列表程序。

## 功能特点

- 递归列出 OpenList 中的文件
- 支持多线程下载文件
- 支持断点续传（跳过已存在的文件）
- 可配置连接和下载行为选项

## 配置说明

在工作目录中创建一个 `config.json` 文件，结构如下：

```json
{
  "openlist_url": "http://your-openlist-instance.com",
  "username": "your_username",
  "password": "your_password",
  "remote_path": "/path/to/remote/directory",
  "local_save_dir": "./downloads",
  "page_size": 200,
  "timeout": 30,
  "skip_existing": true
}
```

### 配置选项

| 选项 | 描述 | 默认值 |
|------|------|--------|
| `openlist_url` | OpenList 实例的 URL | 必填 |
| `username` | OpenList 用户名 | 必填 |
| `password` | OpenList 密码 | 必填 |
| `remote_path` | 要下载的远程路径 | 必填 |
| `local_save_dir` | 保存文件的本地目录 | 必填 |
| `page_size` | 每次请求获取的项目数 | 200 |
| `timeout` | 请求超时时间（秒） | 30 |
| `skip_existing` | 跳过本地已存在的文件 | true |

## 使用方法

安装并配置完成后，可以运行下载器：

```bash
# python3 src/openlist_downloader/main.py  --help
usage: main.py [-h] [--list-only] [--download-only] [--workers WORKERS] [--config CONFIG]

### 命令行选项
options:
  -h, --help         show this help message and exit
  --list-only        仅列出并保存 filelist.json
  --download-only    跳过列目录，使用 filelist.json
  --workers WORKERS  并发下载线程数(默认: 10)
  --config CONFIG    配置文件路径 (默认: config.json)

```

示例：
```bash
# 仅列出文件
# python3 src/openlist_downloader/main.py --list-only
[INFO] 正在登录到 https://alist....
[INFO] 登录成功。
[INFO] 🚀 正在列出目录：/cloud189/流媒体/音乐/陈冠希
[DEBUG] 📂 正在列出：/cloud189/流媒体/音乐/陈冠希
[DEBUG] 📥 正在请求 '/cloud189/流媒体/音乐/陈冠希' 的第 1 页...
[DEBUG] ✅ 第 1 页：1 个项目（目录总计：1）
[DEBUG] 📁 进入：/cloud189/流媒体/音乐/陈冠希/陈冠希 - Peace And Love
[DEBUG] 📂 正在列出：/cloud189/流媒体/音乐/陈冠希/陈冠希 - Peace And Love
[DEBUG] 📥 正在请求 '/cloud189/流媒体/音乐/陈冠希/陈冠希 - Peace And Love' 的第 1 页...
[DEBUG] ✅ 第 1 页：10 个项目（目录总计：10）
[DEBUG] 📦 '/cloud189/流媒体/音乐/陈冠希/陈冠希 - Peace And Love' 完成：10 个文件
[DEBUG] 📦 '/cloud189/流媒体/音乐/陈冠希' 完成：10 个文件
[INFO] 📝 文件列表已保存到 filelist.json
[INFO] 📋 仅列出模式。正在退出。
# grep name filelist.json  | wc -l
10
# 下载文件
# python3 src/openlist_downloader/main.py --download-only
[INFO] 正在登录到 https://alist...
[INFO] 登录成功。
[INFO] 📥 使用现有的 filelist.json
[INFO] 📋 总文件数：10
[INFO] ⚙️ 使用 10 个下载线程
[DOWNLOAD] 🔗 使用 raw_url：/cloud189/流媒体/音乐/陈冠希/陈冠希 - Peace And Love/cover.jpg
[DOWNLOAD] 🔗 使用 raw_url：/cloud189/流媒体/音乐/陈冠希/陈冠希 - Peace And Love/陈冠希 - 能见度.flac
[DOWNLOAD] 🔗 使用 raw_url：/cloud189/流媒体/音乐/陈冠希/陈冠希 - Peace And Love/陈冠希 - 破坏王.flac
[DOWNLOAD] 🔗 使用 raw_url：/cloud189/流媒体/音乐/陈冠希/陈冠希 - Peace And Love/陈冠希Twins - 三个人的舞会.flac
[DOWNLOAD] 🔗 使用 raw_url：/cloud189/流媒体/音乐/陈冠希/陈冠希 - Peace And Love/陈冠希 - 生化恋.flac
[DOWNLOAD] 🔗 使用 raw_url：/cloud189/流媒体/音乐/陈冠希/陈冠希 - Peace And Love/陈冠希 - 坏孩子的天空.flac
[DOWNLOAD] 🔗 使用 raw_url：/cloud189/流媒体/音乐/陈冠希/陈冠希 - Peace And Love/陈冠希 - 越来越爱你.flac
[DOWNLOAD] 🔗 使用 raw_url：/cloud189/流媒体/音乐/陈冠希/陈冠希 - Peace And Love/陈冠希 - 恋人勿近.flac
[DOWNLOAD] 🔗 使用 raw_url：/cloud189/流媒体/音乐/陈冠希/陈冠希 - Peace And Love/陈冠希 - 寒冬.flac
[DOWNLOAD] 🔗 使用 raw_url：/cloud189/流媒体/音乐/陈冠希/陈冠希 - Peace And Love/陈冠希 - 分手武器.flac
[OK] ✅ 已保存：./downloads/cloud189/流媒体/音乐/陈冠希/陈冠希 - Peace And Love/cover.jpg
[OK] ✅ 已保存：./downloads/cloud189/流媒体/音乐/陈冠希/陈冠希 - Peace And Love/陈冠希 - 破坏王.flac
[OK] ✅ 已保存：./downloads/cloud189/流媒体/音乐/陈冠希/陈冠希 - Peace And Love/陈冠希 - 越来越爱你.flac
[OK] ✅ 已保存：./downloads/cloud189/流媒体/音乐/陈冠希/陈冠希 - Peace And Love/陈冠希 - 坏孩子的天空.flac
[OK] ✅ 已保存：./downloads/cloud189/流媒体/音乐/陈冠希/陈冠希 - Peace And Love/陈冠希 - 生化恋.flac
[OK] ✅ 已保存：./downloads/cloud189/流媒体/音乐/陈冠希/陈冠希 - Peace And Love/陈冠希Twins - 三个人的舞会.flac
[OK] ✅ 已保存：./downloads/cloud189/流媒体/音乐/陈冠希/陈冠希 - Peace And Love/陈冠希 - 分手武器.flac
[OK] ✅ 已保存：./downloads/cloud189/流媒体/音乐/陈冠希/陈冠希 - Peace And Love/陈冠希 - 恋人勿近.flac
[OK] ✅ 已保存：./downloads/cloud189/流媒体/音乐/陈冠希/陈冠希 - Peace And Love/陈冠希 - 寒冬.flac
[OK] ✅ 已保存：./downloads/cloud189/流媒体/音乐/陈冠希/陈冠希 - Peace And Love/陈冠希 - 能见度.flac
[PROGRESS] 📥 10/10
[INFO] 🎉 所有下载完成！

```

## 工作原理

1. 与 OpenList 实例进行身份验证
2. 从指定的远程路径递归列出所有文件
3. 将文件列表保存到 `filelist.json`（除非使用 `--download-only`）
4. 按照与远程相同的结构将文件下载到本地目录
5. 通过检查文件大小支持断点续传下载

## 环境要求

- Python 3.6+
- requests 库

## 许可证

MIT