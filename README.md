# 拓竹 3D 打印耗材管理系统 (Bambu Lab Filament Manager)

一个专为拓竹（Bambu Lab）3D 打印用户打造的**开源轻量级耗材库存管理与多色自动扣减系统**。

支持多账号隔离、网页端耗材台账、多色切片 (AMS Slot) 自动解析与绑定，以及灵活的炒面补扣与克重撤销功能。

---

✨ 核心亮点
🌐 Web 网页台账：随时查看多款耗材的剩余重量、材质、价格与扣减历史流水。

🎨 多色切片自动解析：切片完成导出时，自动弹出交互窗口，匹配每个切片槽位对应的耗材。

🔑 API Key 隔离鉴权：支持多账号注册，每个账号生成专属脚本 API Key，数据独立隔离。

☁️ 无缝兼容拓竹云服务：无需开启打印机的仅局域网模式，完全不影响拓竹 APP 云端控制与官方切片功能，即便打印机未开机也能随时扣减台账。

🍜 炒面与失误补扣：可在历史明细弹窗中一键补扣炒面损失，或撤销误扣并自定义退还克重。

📦 免重新编译配置：Windows 客户端通过同级目录下的 config.json 动态读取地址，更换域名/密钥无需重新打包。

---
## 🛠️ 项目架构

```text
├── backend/            # FastAPI 服务端 (部署于服务器 / 1Panel)
├── frontend/           # HTML/CSS/JS 网页前端 (自适应域名请求)
└── client/             # Windows 客户端源码与打包文件
```
🚀 一、服务端部署指南（基于 1Panel 容器编排 或 Windows服务端）
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

如果你是在纯局域网环境下使用，不打算绑定外网域名，在 1Panel（或 Nginx/OpenResty）创建反向代理网站时：

1、域名/主域名框：直接填写你服务器/NAS 的局域网 IP（例如 192.168.1.100，或者带端口如 192.168.1.100:8000）。

2、代理目标地址：依然填 [http://127.0.0.1:8000](http://127.0.0.1:8000)（因为 1Panel 和你的 FastAPI 容器运行在同一台机器上）。

注意！最好在路由器进行DHCP静态分配或者使用静态IP 防止IP变化

🚀 拓竹 3D 打印耗材资产管理系统 - Windows 本地服务端部署教程本教程适用于已拿到 bambu_server.exe 压缩包的终局用户。系统为免安装绿色版，无须配置任何数据库或 Python 环境，双击即可开箱即用。  📁 一、 启动服务端解压程序：将收到的压缩包解压到一个固定的本地文件夹（例如 D:\BambuServer）。运行服务端：双击运行 bambu_server.exe。选择网络监听模式：首次运行时，控制台会提示如下界面：Plaintext=================================================================
      拓竹 3D 打印耗材资产管理系统 - 本地独立服务端 v2.0
=================================================================
📁 数据库保存路径: D:\BambuServer\filament_db.db
-----------------------------------------------------------------
请选择网络监听模式：
  [1] 局域网共享模式 (绑定 0.0.0.0，同 WiFi 下的手机/其他电脑可访问)
  [2] 本地独占安全模式 (绑定 127.0.0.1，仅供本机使用)
-----------------------------------------------------------------
请输入选项 (1 或 2，默认 1):
按键盘【回车】（默认模式 1）：开启局域网共享模式，同一 WiFi 下的手机、平板或其他电脑也可以访问。  输入 2 后按回车：开启独占安全模式，仅允许当前电脑本机访问。

🔑 二、 初始化账号与获取 API Key打开控制台：用浏览器访问 http://127.0.0.1:8000。  注册账号：在登录页面输入自定义的用户名和密码，点击 【注册新账号】。  登录系统：注册成功后，点击 【登录系统】。  生成 API Key：登录成功后，在顶部面板找到 🔑 后处理脚本 API 密钥 区域，点击 【生成/重置我的脚本 API Key】。  保存密钥：页面会弹出一串以 sk_ 开头的密钥（如 sk_a1b2c3d4...），复制并保存这串密钥。 

🔗 三、 配置切片与台账客户端助手打开电脑上的“拓竹耗材台账助手”客户端，进入设置页面，按以下规范填写：扣减上报地址：Plaintexthttp://127.0.0.1:8000/api/ingest/script-report
耗材台账地址：Plaintexthttp://127.0.0.1:8000/api/ingest/script-filaments
脚本 API 密钥：
粘贴刚才在网页端生成的 sk_xxxxxxxx... 密钥。  填写完毕后，点击 【测试服务器连接】，提示连接成功后点击 【保存设置】 即可！

💾 四、 数据备份与迁移指南服务端运行后，会在 bambu_server.exe 同级目录下自动生成一个名为 filament_db.db 的数据库文件。数据备份：定期复制保存 filament_db.db 文件即可完成全局资产台账与日志备份。无损迁移：若需要更换电脑，只需把 bambu_server.exe 和 filament_db.db 一起移动到新电脑上直接运行，所有耗材数据与账号信息将完全保留。

💻 二、 客户端配置与使用教程

### 1. Web 网页端准备与 API Key 获取
* **注册与登录**：打开管理系统网页端，注册并登录你的个人账号。
  <img width="865" height="388" alt="image" src="https://github.com/user-attachments/assets/b9e3424d-2006-4e61-8da3-14726ee65bbb" />
* **生成 API Key**：登录成功后，在后台首页点击 **【生成/重置我的脚本 API Key】** 按钮，复制生成的 API Key 备用。
  <img width="865" height="590" alt="image" src="https://github.com/user-attachments/assets/14f50b5e-5969-42cd-9979-18f52d5f7eed" />
* **新增耗材档案**：在“手动新增耗材档案”区域，填入品牌、材质、颜色及初始重量（默认 1000g）并保存。在“我的耗材台账”中可随时查看或调整耗材剩余克重。
  <img width="865" height="233" alt="image" src="https://github.com/user-attachments/assets/738846ae-2e15-413b-aeb3-4ba09353ce04" />

---

### 2. 客户端配置（v2.7 Beta 无感模式推荐）
1. **下载客户端**：前往仓库右侧的 **Releases** 页面下载最新版本的客户端程序（如 `BambuFilamentStudio_v2.7_beta.exe`）。
2. **安全存储密钥**：打开客户端切换至 **【服务设置】**，填入你的服务地址与 API Key 并点击保存。API Key 将被自动写入 **Windows 凭据管理器（Vault）** 进行硬件级加密保护。
   <img width="867" height="830" alt="image" src="https://github.com/user-attachments/assets/68dec9c7-121b-4f12-9e4d-7f13977b0f59" />
3. **开启自动监听**：确认设置中的 **“切片打印自动监听”** 处于开启状态。
<img width="878" height="837" alt="image" src="https://github.com/user-attachments/assets/e4a05a92-88b6-4e10-be71-0b56a134f429" />

> ✨ **v2.7+ 核心优势**：在切片软件（Bambu Studio / OrcaSlicer）中无需进行任何“后处理脚本”配置，直接打开任意 `.3mf` 模型并点击 **【打印单盘 / 发送】**，助手弹窗就会自动跳转唤醒，且 **100% 完好保留原作者的所有特殊工艺参数**！

---

<details>
<summary><b>点击展开：老版本（v2.4beta 及以下）手动配置 BambuStudio 后处理脚本教程（已废弃/备用）</b></summary>

<br>

> ⚠️ **注意**：使用 v2.7 Beta 及以上版本的用户请忽略此折叠教程。

#### 1. 复制程序绝对路径
在客户端【服务设置】页面中点击 **[一键复制路径]**，或选中客户端 `.exe` 程序按住键盘 `Shift` 键右键点击选择 **【复制文件地址】**。
<img width="714" height="734" alt="image" src="https://github.com/user-attachments/assets/be69b827-5201-41f1-b66c-9504c22ff049" />

#### 2. 填入 BambuStudio 后处理脚本
打开 BambuStudio ➔ 切换到左侧 **【工艺】** 标签页 ➔ 选择 **【其他】** ➔ 滚动到最底部的 **【后处理脚本】** 框内，直接粘贴刚复制的文件地址（保持带双引号格式）。
<img width="865" height="447" alt="image" src="https://github.com/user-attachments/assets/d878d9d7-f2ee-40c1-a093-8778b0d44a2a" />

#### 3. 另存为用户预设
点击工艺右上角的 **【保存预设】**（小磁盘图标），起一个名字（例如 `0.20mm Standard @BBL P2S 后处理`），点击确认。
<img width="865" height="498" alt="image" src="https://github.com/user-attachments/assets/06308bc9-3158-4a1a-bf03-ee5755870c48" />

#### 4. 日常使用
打印时只需在工艺下拉菜单中选择这个带有后处理的预设，每次完成切片并导出/打印时，就会自动弹出多色扣减窗口上报克重。

---
</details>

---

🔮 路线规划 (Roadmap)
- [x] Web 台账与多租户 API Key 隔离
- [x] 多色切片 G-code 自动解析与槽位记忆
- [x] 历史明细自定义退还克重与快捷补扣
- [x] Windows 专属桌面客户端（GUI 现代化界面、Windows 凭据库硬件加密存 Key、历史记录撤销与手动增减）
- [x] 无感文件监听与后处理自动匹配（无需覆盖修改任何切片工艺参数，直接点击【打印】即可自动唤醒）
📄 开源许可
本项目基于 MIT License 协议开源。欢迎 Fork、Star 和 Issue 提交改进建议！
