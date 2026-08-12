# 拓竹 3D 打印耗材管理系统

> **Bambu Lab Filament Manager**  
> 面向拓竹（Bambu Lab）3D 打印机用户的轻量级耗材库存与打印自动扣减系统。

支持 **多账号数据隔离、Web 耗材台账、AMS 多色打印自动解析、打印损耗补扣、误扣克重撤销** 等功能。

---

## ✨ 功能亮点

| 功能 | 说明 |
|---|---|
| 🌐 Web 耗材台账 | 查看耗材剩余重量、材质、颜色、采购价格及完整扣减流水 |
| 🎨 AMS 多色自动解析 | 发送切片文件打印后，自动识别 AMS 槽位并绑定对应耗材 |
| 🔑 API-Key 数据隔离 | 多用户独立注册，每个账号使用专属 API-Key，数据互不影响 |
| ☁️ 兼容拓竹官方云端 | 无需修改打印机局域网设置，不影响 Bambu App 远程操控 |
| 🍜 打印损耗管理 | 打印失败、炒面等情况支持一键补扣耗材 |
| ↩️ 误扣撤销 | 支持自定义克重回退，方便修正误操作 |
| 📡 无感监听 | v2.7 Beta 起无需配置 Bambu Studio 后处理脚本 |
| 🔐 本地密钥保护 | Windows 客户端密钥使用系统凭据管理器加密保存 |
| ⚙️ 配置免编译修改 | Windows 客户端支持通过同级 `config.json` 修改服务地址等配置 |

---

## 🏗️ 项目结构

```text
bambu-filament-manager/
├── backend/              # FastAPI 后端服务
├── frontend/             # HTML + JavaScript 网页前端
└── client/               # Windows 桌面客户端源码及编译包
```

---

# 🚀 服务端部署

项目提供两种部署方式：

- **方案一：Linux + 1Panel + Docker Compose**
- **方案二：Windows 本地独立服务端**

根据自己的使用场景选择即可。

---

## 方案一：Linux + 1Panel Docker Compose

### 1. 安装 MySQL

在 **1Panel → 应用商店** 安装 MySQL。

创建数据库：

```text
数据库名称：filament_db
```

请记录以下信息，后续 Docker Compose 会使用：

- 数据库用户名
- 数据库密码
- 数据库名称

---

### 2. 上传项目源码

通过 1Panel 文件管理器上传 `backend` 和 `frontend` 文件夹。

推荐目录：

```text
/opt/bambu-filament-manager/
├── backend/
└── frontend/
```

---

### 3. 创建 Docker Compose 编排

进入：

```text
1Panel
└── 容器
    └── 编排
        └── 创建编排
```

工作目录选择：

```text
/opt/bambu-filament-manager/
```

然后粘贴以下配置。

> ⚠️ **请先修改数据库用户名、数据库密码和 JWT 密钥，再启动容器。**

```yaml
services:
  filament-api:
    image: python:3.11-slim
    container_name: filament-api
    restart: always
    working_dir: /app
    volumes:
      - ./backend:/app
      - ./frontend:/frontend
    deploy:
      resources:
        limits:
          memory: 300M
    command: >
      bash -c "pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
      && uvicorn main:app --host 0.0.0.0 --port 8000"
    environment:
      - DB_HOST=172.17.0.1
      - DB_PORT=3306
      - DB_USER=你的数据库用户名
      - DB_PASS=你的数据库密码
      - DB_NAME=filament_db
      - JWT_SECRET=请替换为随机长密钥
    ports:
      - "8000:8000"
```

保存并启动编排。

启动成功后，后端 API 默认监听：

```text
http://服务器IP:8000
```

---

### 4. 配置 Nginx 反向代理

#### 外网域名

在 1Panel 中：

```text
网站 → 创建网站 → 反向代理
```

代理目标：

```text
http://127.0.0.1:8000
```

#### 局域网访问

如果只在家庭/工作室局域网使用，可以将网站地址绑定到服务器局域网 IP。

例如：

```text
http://192.168.1.100
```

代理目标仍然使用：

```text
http://127.0.0.1:8000
```

> 💡 建议在路由器中为服务器设置 **静态 DHCP 租约**，避免服务器 IP 变化导致客户端无法连接。

---

# 🪟 方案二：Windows 本地独立服务端

适合不想部署 Linux 服务器、只需要在一台 Windows 电脑上运行服务的用户。

## 1. 启动服务端

将服务端压缩包解压到固定目录，例如：

```text
D:\BambuServer
```

双击：

```text
bambu_server.exe
```

启动后选择监听模式：

```text
[1] 局域网共享模式
    同一 Wi-Fi 下的手机、电脑等设备均可访问

[2] 本机独占模式
    仅当前电脑可以访问网页后台
```

推荐普通用户选择：

```text
[1] 局域网共享模式
```

---

## 2. 创建账号并获取 API-Key

浏览器打开：

```text
http://127.0.0.1:8000
```

然后：

1. 注册账号
2. 登录管理后台
3. 打开 API-Key / 密钥管理区域
4. 创建专属 API-Key
5. 保存以 `sk_` 开头的密钥

> ⚠️ API-Key 相当于客户端访问服务器的身份凭证，请勿公开发布到 GitHub、论坛或截图中。

---

## 3. 配置 Windows 客户端

打开：

```text
拓竹耗材台账助手
```

进入：

```text
服务设置
```

填写接口地址：

```text
扣减上报地址：
http://127.0.0.1:8000/api/ingest/script-report

耗材台账地址：
http://127.0.0.1:8000/api/ingest/script-filaments
```

然后：

1. 粘贴 API-Key
2. 点击测试连接
3. 测试成功后保存配置

---

## 4. 数据库备份与迁移

Windows 本地模式的数据库文件：

```text
filament_db.db
```

建议定期备份。

### 备份

直接复制：

```text
filament_db.db
```

到其他安全位置即可。

### 更换电脑

将以下内容复制到新电脑：

```text
bambu_server.exe
filament_db.db
```

然后重新启动服务端。

> 💡 建议在迁移前先关闭服务端，避免数据库正在写入时直接复制文件。

---

# 💻 Windows 客户端使用教程

## 第一步：准备 Web 管理后台

首次使用建议按照以下顺序操作：

```text
注册账号
   ↓
登录管理后台
   ↓
获取 API-Key
   ↓
创建耗材档案
   ↓
录入品牌 / 材质 / 颜色 / 初始重量
   ↓
配置 Windows 客户端
   ↓
开启自动监听
```
<img width="1668" height="784" alt="image" src="https://github.com/user-attachments/assets/bf71ffcb-91a8-4e6e-9a23-830adb80abeb" />

---

## 第二步：创建耗材档案

在 Web 管理后台创建耗材。

建议至少填写：

- 品牌
- 材质
- 颜色
- 初始重量
- 采购价格（如有）

例如：

```text
品牌：Bambu Lab
材质：PLA
颜色：白色
初始重量：1000g
```
<img width="1668" height="784" alt="image" src="https://github.com/user-attachments/assets/207d2582-7c43-403d-ae02-3cdadcfc3fce" />

---

# ⭐ v2.7 Beta：无感监听模式

> **强烈推荐使用此方式。**

v2.7 Beta 起：

- ✅ 不需要修改 Bambu Studio 切片预设
- ✅ 不需要配置后处理脚本
- ✅ 不需要在 Bambu Studio 中额外添加程序
- ✅ 发送 3MF 文件后自动监听
- ✅ 自动弹出耗材绑定界面
- ✅ 保留原有切片工艺参数

---

## 1. 下载客户端

在项目 GitHub Releases 中下载：

```text
BambuFilamentStudio_v2.7_beta.exe
```

---

## 2. 配置服务器

打开客户端：

```text
服务设置
```

填写：

```text
服务器地址
API-Key
```

然后测试连接。
<img width="845" height="673" alt="image" src="https://github.com/user-attachments/assets/b274138b-0454-4ac2-a1bd-810ebaf97693" />

客户端会将密钥安全保存到 Windows 凭据管理器中。

---

## 3. 开启自动监听

打开：

```text
切片打印自动监听
```
<img width="865" height="838" alt="image" src="https://github.com/user-attachments/assets/5641d21b-e853-412f-9856-27a39a566a7e" />

启用后即可正常使用 Bambu Studio。

基本工作流程：

```text
Bambu Studio
     │
     ▼
切片并发送打印
     │
     ▼
Windows 客户端自动监听
     │
     ▼
解析 3MF / AMS 信息
     │
     ▼
弹出耗材绑定
     │
     ▼
确认打印
     │
     ▼
自动上报耗材扣减
```

---

# 📦 旧版本 v2.4 及以下：后处理脚本

> ⚠️ **此方法已经废弃，仅供旧版本用户参考。**
>
> **v2.7 Beta 及以上版本不需要配置后处理脚本。**

<details>
<summary>点击展开旧版配置方法</summary>

### 1. 获取客户端完整路径

找到客户端：

```text
BambuFilamentStudio.exe
```

复制完整路径。

例如：

```text
D:\BambuFilamentManager\BambuFilamentStudio.exe
```

### 2. 配置 Bambu Studio

打开：

```text
Bambu Studio
→ 工艺
→ 其他
→ 后处理脚本
```

粘贴客户端程序完整路径。

如果路径中包含空格，请使用引号：

```text
"D:\Bambu Filament Manager\BambuFilamentStudio.exe"
```

### 3. 保存工艺预设

保存当前工艺预设。

之后使用该预设切片并发送打印，即可触发耗材扣减流程。

</details>

---

# 🧵 AMS 多色打印

系统支持 AMS 多色打印场景。

基本流程：

```text
多色模型
   ↓
Bambu Studio 切片
   ↓
发送打印
   ↓
客户端解析 3MF
   ↓
识别 AMS 槽位
   ↓
匹配耗材档案
   ↓
确认耗材绑定
   ↓
打印完成后扣减
```

如果某个 AMS 槽位首次使用，按照客户端提示绑定对应耗材即可。

后续系统可以记忆对应关系，减少重复操作。

---

# 🍜 打印失败与损耗补扣

实际打印过程中可能出现：

- 打印失败
- 炒面
- 首层失败
- 测试耗材
- 清理喷嘴
- 其他额外耗材消耗

可以在 Web 台账中进行损耗补扣。

例如：

```text
正常打印：120g
打印失败损耗：35g

最终扣减：
120g + 35g = 155g
```

这样可以让库存重量更加接近实际剩余重量。

---

# ↩️ 误扣耗材撤销

如果发生误操作，可以进行克重回退。

例如：

```text
错误扣减：80g

实际应该扣减：50g

回退：
30g
```

系统最终库存恢复为正确重量。

> 建议每次调整库存时填写明确的操作原因，方便后续查看流水。

---

# 🔐 API-Key 与数据隔离

每个账号拥有独立 API-Key。

数据关系：

```text
用户 A
 ├── API-Key A
 ├── 耗材数据 A
 └── 打印流水 A

用户 B
 ├── API-Key B
 ├── 耗材数据 B
 └── 打印流水 B
```

不同用户之间的数据相互隔离。

### 安全建议

请勿：

- 将真实 API-Key 提交到 GitHub
- 将 API-Key 写入公开截图
- 在 Issue 中直接粘贴 API-Key
- 将生产环境 JWT_SECRET 提交到公开仓库

建议使用：

```text
config.json
环境变量
Windows 凭据管理器
```

保存敏感配置。

---

# ⚙️ 配置文件

Windows 客户端支持读取程序同级目录下：

```text
config.json
```

因此更换服务器地址等配置时，可以直接修改配置文件，而无需重新编译客户端。

示例：

```text
BambuFilamentStudio.exe
config.json
```

> ⚠️ 实际 `config.json` 字段请以当前版本客户端源码 / Release 中提供的配置格式为准，不建议自行添加未知字段。

---

# 🧰 常见问题

## Q1：客户端连接不上服务器怎么办？

按以下顺序检查：

```text
① 服务端是否正常启动
② 浏览器能否打开 Web 后台
③ API-Key 是否正确
④ 客户端服务器地址是否正确
⑤ 服务器端口是否开放
⑥ Windows 防火墙是否拦截
⑦ 局域网设备是否处于同一网络
```

---

## Q2：局域网其他设备无法访问？

确认服务端使用：

```text
局域网共享模式
```

不要使用：

```text
本机独占模式
```

同时检查 Windows 防火墙和服务器端口。

---

## Q3：耗材没有自动扣减？

建议检查：

```text
客户端是否正在运行
        ↓
自动监听是否开启
        ↓
服务器是否在线
        ↓
API-Key 是否有效
        ↓
3MF 是否成功被解析
        ↓
AMS 槽位是否已经绑定耗材
```

---

## Q4：打印失败后怎么办？

正常打印扣减完成后，如果实际产生额外损耗：

```text
Web 后台
→ 打印记录 / 耗材台账
→ 损耗补扣
```

填写实际损耗克重即可。

---

## Q5：误扣了怎么办？

使用：

```text
克重撤销 / 回退
```

输入需要恢复的克重即可。

---

# 🗺️ Roadmap

- [x] 多租户网页耗材台账
- [x] 独立 API-Key 数据隔离
- [x] AMS 多色切片解析
- [x] AMS 槽位耗材记忆
- [x] 打印记录损耗补扣
- [x] 自定义克重撤销
- [x] Windows GUI 客户端
- [x] Windows 凭据管理器加密密钥
- [x] 3MF 文件无感监听
- [x] 无需 Bambu Studio 后处理脚本

---

# 📌 版本建议

| 用户类型 | 推荐方案 |
|---|---|
| 普通家庭用户 | Windows 本地服务端 |
| 多台电脑共享 | Windows 局域网共享模式 |
| 服务器长期运行 | Linux + 1Panel |
| 外网访问 | Linux + Nginx + HTTPS |
| v2.7 及以上 | 无感监听模式 |
| v2.4 及以下 | 后处理脚本（旧方案） |

---

# 📄 开源协议

本项目基于 **MIT License** 开源。

欢迎：

- ⭐ Star
- 🍴 Fork
- 🐛 提交 Issue
- 💡 提交功能建议
- 🔧 提交 Pull Request

---

## ❤️ 支持项目

如果这个项目对你的耗材管理和打印工作流有帮助，欢迎给项目点一个 ⭐ Star。

**感谢使用 Bambu Lab Filament Manager！**
