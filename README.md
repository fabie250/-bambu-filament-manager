```markdown
# 拓竹 3D 打印耗材与打印机管理系统 (Bambu Lab Filament Manager)

一个专为拓竹（Bambu Lab）3D 打印用户打造的**开源轻量级耗材库存管理与多色自动扣减系统**。

支持多账号隔离、网页端耗材台账、多色切片 (AMS Slot) 自动解析与绑定，以及灵活的炒面补扣与克重撤销功能。

---

## ✨ 核心亮点

- 🌐 **Web 网页台账**：随时查看多款耗材的剩余重量、材质、价格与扣减历史流水。
- 🎨 **多色切片自动解析**：切片完成导出时，自动弹出交互窗口，匹配每个切片槽位对应的耗材。
- 🔑 **API Key 隔离鉴权**：支持多账号注册，每个账号生成专属脚本 API Key，数据独立隔离。
- 🍜 **炒面与失误补扣**：可在历史明细弹窗中一键补扣炒面损失，或撤销误扣并自定义退还克重。
- 📦 **免重新编译配置**：Windows 客户端通过同级目录下的 `config.json` 动态读取地址，更换域名/密钥无需重新打包。

---

## 🛠️ 项目架构

```text
├── backend/            # FastAPI 服务端 (部署于服务器 / 1Panel)
├── frontend/           # HTML/CSS/JS 网页前端 (自适应域名请求)
└── client/             # Windows 客户端源码与打包文件
🚀 一、服务端部署指南（基于 1Panel）
本系统服务端推荐使用 1Panel 服务器面板 进行快速容器化部署：

1. 部署 MySQL 数据库
打开 1Panel ➔ 【应用商店】 ➔ 安装 MySQL。

创建一个数据库（例如数据库名：filament_db），并记下数据库用户名与密码。

2. 部署 FastAPI 后端
在 1Panel ➔ 【容器】 ➔ 创建容器 / 运行环境。

配置以下环境变量（可在 1Panel 环境变量设置中添加）：

DB_USER：数据库用户名

DB_PASS：数据库密码

DB_HOST：数据库 IP（通常为 172.17.0.1 或容器网桥 IP）

DB_PORT：3306

DB_NAME：filament_db

JWT_SECRET：任意自定义的随机加密字符串

容器映射端口：例如将容器内部的 8000 端口映射到宿主机的 8000。

3. 配置反向代理与域名
在 1Panel ➔ 【网站】 ➔ 【创建网站】 / 【反向代理】。

填入你的域名（建议使用标准 80 或 443 端口，例如 [http://your-domain.com](http://your-domain.com)），反向代理地址指向 [http://172.17.0.1:8000](http://172.17.0.1:8000)。

浏览器访问你的域名，即可直接打开登录和台账后台界面！

💻 二、Windows 客户端获取与使用教程
1. 下载预编译客户端 .exe
你无需在本地安装 Python 环境，直接前往本仓库右侧的 Releases 页面，下载最新的 Bambu_Post_Process_v1.0.zip 压缩包并解压即可得到 bambu_post_process.exe。

(如果你想自行编译源码，可以在 client 目录下运行 python -m PyInstaller --noconsole --onefile bambu_post_process.py)

2. ⚠️ 首次运行与配置文件生成（非常重要！）
由于程序支持动态读取配置文件，首次使用时请按照以下顺序操作：

首次运行：
双击运行一次 bambu_post_process.exe（或在 Bambu Studio 中绑定路径后触发一次切片导出）。
程序在首次运行后，会在 .exe 的同级目录下自动生成一个 config.json 文件。

修改配置文件 config.json：
用记事本打开同级目录下的 config.json，修改为你自己的服务器地址与专属 API Key：

JSON
{
  "server_url": "http://你的域名/api/ingest/script-report",
  "filaments_url": "http://你的域名/api/ingest/script-filaments",
  "api_key": "你的专属APIKey (从网页后台获取)",
  "filament_id": 1
}
🔑 如何获取 API Key：登录网页后台 ➔ 点击【生成/重置我的脚本 API Key】➔ 复制以 sk_ 开头的字符串填入此处。

3. 在 Bambu Studio（拓竹切片软件）中绑定
打开 Bambu Studio ➔ 进入 【工艺】 ➔ 【其他】 ➔ 【后处理脚本】。

输入你的 .exe 文件绝对路径（路径两侧用英文双引号包裹），例如：

Plaintext
"C:\Tools\bambu_post_process.exe"
保存预设。以后每次在 Bambu Studio 中完成切片并导出/打印时，都会自动弹出耗材绑定窗口并上报扣减！

🔮 路线规划 (Roadmap)
[x] Web 台账与多租户 API Key 隔离

[x] 多色切片 G-code 自动解析与槽位记忆

[x] 历史明细自定义退还克重与快捷补扣

[ ] Windows 专属桌面客户端：后续将推出带系统托盘、本地多色看板、耗材刻度快速校准与一键管理功能独立 GUI 桌面程序，敬请期待！

📄 开源许可
本项目基于 MIT License 协议开源。欢迎 Fork、Star 和 Issue 提交改进建议！
