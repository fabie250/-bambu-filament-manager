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
```
🚀 一、服务端部署指南（基于 1Panel 容器编排）
本系统服务端推荐使用 1Panel 服务器面板 的 Docker Compose 编排 进行一键部署：

1. 部署 MySQL 数据库
打开 1Panel ➔ 【应用商店】 ➔ 安装 MySQL。

创建数据库（数据库名：filament_db），并记下创建好的数据库用户名与密码。

2. 准备源码目录
在 1Panel 的 【文件】 管理器中，将本项目的 backend 和 frontend 文件夹上传至服务器同一个目录下（例如 /opt/bambu-filament-manager）：

```text
/opt/bambu-filament-manager/
├── backend/            # 存放后端 main.py 与 requirements.txt
└── frontend/           # 存放前端 index.html
```
3. 创建 Docker Compose 编排
打开 1Panel ➔ 【容器】 ➔ 【编排】 ➔ 点击 【创建编排】。

路径选择刚才上传源码的目录 /opt/bambu-filament-manager。

将以下编排配置复制粘贴进去（请修改为您自己的数据库密码与 JWT 密钥）：

```text
services:
  filament-api:
    image: python:3.11-slim
    container_name: filament-api
    restart: always
    working_dir: /app
    volumes:
      - ./backend:/app       # 挂载 backend 目录
      - ./frontend:/frontend # 挂载 frontend 目录
    deploy:
      resources:
        limits:
          memory: 300M      # 限制最大内存，防止爆内存
    command: >
      bash -c "pip install --no-cache-dir -r requirements.txt -i [https://pypi.tuna.tsinghua.edu.cn/simple](https://pypi.tuna.tsinghua.edu.cn/simple) 
      && uvicorn main:app --host 0.0.0.0 --port 8000"
    environment:
      - DB_HOST=172.17.0.1  # Docker 默认网关 IP，可直接连接宿主机/1Panel 数据库
      - DB_PORT=3306
      - DB_USER=你的数据库用户名
      - DB_PASS=你的数据库密码
      - DB_NAME=filament_db
      - JWT_SECRET=你的自定义JWT随机密钥
    ports:
      - "8000:8000"         # 映射 8000 端口给反向代理使用
```

点击 【确定】，1Panel 会自动拉取镜像并启动服务。

4. 配置反向代理与域名
在 1Panel ➔ 【网站】 ➔ 【创建网站】 ➔ 选择 【反向代理】。

填入你的域名，代理目标地址指向 http://127.0.0.1:8000。

浏览器访问你的域名，即可直接打开并使用耗材管理系统！

💻 二、客户端配置与 BambuStudio 设置教程
1. 获取 API Key 与新建耗材
注册与登录：
打开你的管理系统网页端，首先注册并登录账号。
<img width="865" height="388" alt="image" src="https://github.com/user-attachments/assets/b9e3424d-2006-4e61-8da3-14726ee65bbb" />

生成 API Key：
登录成功后，在后台首页点击 【生成/重置我的脚本 API Key】 按钮，复制生成的 API Key 备用。
<img width="865" height="590" alt="image" src="https://github.com/user-attachments/assets/14f50b5e-5969-42cd-9979-18f52d5f7eed" />

新增耗材档案：
在“手动新增耗材档案”区域，填入品牌、材质、颜色及初始重量（默认 1000g）并保存。在下面的“我的耗材台账”中可随时查看或调整耗材剩余克重。
<img width="865" height="233" alt="image" src="https://github.com/user-attachments/assets/738846ae-2e15-413b-aeb3-4ba09353ce04" />

2. 客户端获取与配置文件生成
下载客户端程序：
前往本仓库右侧的 Releases 页面下载打包好的 bambu_post_process.exe 客户端程序（或直接下载预编译版本）。

首次运行生成配置：
双击运行一次 bambu_post_process.exe。运行后稍等片刻，程序会在同级目录下自动生成 config.json 与 log.txt 文件。
<img width="865" height="147" alt="image" src="https://github.com/user-attachments/assets/4d5b29df-7f59-453b-a13a-2c477a53ee14" />

修改 API Key：
右键点击 config.json ➔ 选择 【用记事本打开】，将其中的 api_key 替换为你刚才在网页端复制的专属 API Key 并保存。
<img width="653" height="161" alt="image" src="https://github.com/user-attachments/assets/655a90dc-069b-4a79-aa33-1f892bb032cc" />

3. 在 BambuStudio 中绑定后处理脚本
获取程序绝对路径：
找到下载好的 bambu_post_process.exe，按住键盘 Shift 键右键点击文件，选择 【复制文件地址】（或右键菜单中的复制文件路径）。
<img width="714" height="734" alt="image" src="https://github.com/user-attachments/assets/be69b827-5201-41f1-b66c-9504c22ff049" />

填入 BambuStudio 后处理脚本：
打开 BambuStudio ➔ 切换到左侧 【工艺】 标签页 ➔ 选择 【其他】 ➔ 滚动到最底部的 【后处理脚本】 框内，直接粘贴刚复制的文件地址（保持带双引号格式）。
<img width="865" height="447" alt="image" src="https://github.com/user-attachments/assets/d878d9d7-f2ee-40c1-a093-8778b0d44a2a" />

另存为用户预设：
点击工艺右上角的 【保存预设】（小磁盘图标），起一个名字（例如 0.20mm Standard @BBL P2S 后处理），点击确认。
<img width="865" height="498" alt="image" src="https://github.com/user-attachments/assets/06308bc9-3158-4a1a-bf03-ee5755870c48" />

方便日常切换：
以后在打印时，只需要在工艺下拉菜单中直接选择这个带有后处理的预设，每次完成切片并导出/打印时，就会自动弹出多色扣减窗口上报克重！

🔮 路线规划 (Roadmap)
[x] Web 台账与多租户 API Key 隔离

[x] 多色切片 G-code 自动解析与槽位记忆

[x] 历史明细自定义退还克重与快捷补扣

[ ] Windows 专属桌面客户端：后续将推出带系统托盘、本地多色看板、耗材刻度快速校准与一键管理功能独立 GUI 桌面程序，敬请期待！

📄 开源许可
本项目基于 MIT License 协议开源。欢迎 Fork、Star 和 Issue 提交改进建议！
