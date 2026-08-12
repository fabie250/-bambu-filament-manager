```markdown
# 拓竹 3D 打印耗材管理系统 (Bambu Lab Filament Manager)
> 专为 Bambu‑Lab 拓竹打印机用户打造的开源轻量级耗材库存、多色打印自动扣减工具

支持多账号数据隔离、网页耗材台账、AMS多色切片自动解析、打印损耗补扣、误操作克重撤销等全套功能。

## ✨ 核心亮点
- 🌐 **Web网页耗材台账**：随时查看耗材剩余重量、材质、采购价格、完整扣减流水记录
- 🎨 **AMS多色切片自动解析**：切片发送打印之后弹窗，自动识别槽位并绑定对应耗材
- 🔑 **独立API‑Key账号隔离**：多用户注册，每人专属密钥，所有耗材数据互相独立
- ☁️ **兼容拓竹官方云端**：不需要修改打印机局域网设置，不干扰Bambu‑APP远程操控，打印机关机依旧能够执行台账扣减
- 🍜 **打印失误损耗管理**：打印失败、炒面损耗一键补扣；误扣耗材支持自定义克重回退
- 📦 **免编译更新配置**：Windows客户端读取同级`config.json`，更换服务器地址、密钥无需重新打包程序

## 🛠️ 项目目录架构
```
├── backend/            # FastAPI后端服务，适用于服务器1Panel部署
├── frontend/           # HTML+JS网页前端，自动适配服务器域名
└── client/              # Windows桌面客户端源码与编译包
```

## 🚀 服务端部署教程
提供 **Linux服务器部署**、**Windows本地独立服务端** 两套方案，可以按需选用

### 方案一：Linux 1Panel Docker‑Compose 部署
#### 1. 安装MySQL数据库
1Panel 应用商店安装 MySQL，新建数据库名称 `filament_db`，保存好数据库账号、密码。

#### 2. 上传项目源码
通过1Panel文件管理器上传 `backend`、`frontend` 文件夹，示例路径：
```
/opt/bambu-filament-manager/
├── backend/
└── frontend/
```

#### 3. 创建容器编排配置
1Panel → 容器 → 编排 → 创建编排，工作目录选定上面的项目文件夹，粘贴下面配置，修改数据库账号密码、JWT密钥
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
      - JWT_SECRET=自定义随机密钥
    ports:
      - "8000:8000"
```
保存编排后容器将会自动启动后端服务

#### 4. Nginx反向代理设置
1. 外网域名：新建网站‑反向代理，目标地址 `http://127.0.0.1:8000`
2. 局域网内网使用：网站地址填写本机局域网IP，代理目标不变
> 路由器设置设备静态DHCP，防止服务器IP变动造成服务无法访问

---

### 方案二：Windows本地独立服务端部署
#### 1. 启动本地服务端
1. 将服务端压缩包解压至固定目录，示例 `D:\BambuServer`
2. 双击 `bambu_server.exe` 启动程序
3. 选择监听模式
```
[1] 局域网共享模式：同一WiFi手机、其他电脑均可访问（默认）
[2] 本机独占模式：仅当前电脑可以打开网页后台
```

#### 2. 创建账号并且获取API‑Key
1. 浏览器访问 `http://127.0.0.1:8000`
2. 注册账号密码并且登录后台
3. 在首页密钥板块，生成以 `sk_` 开头的专属API密钥并保存

#### 3. Windows客户端参数配置
打开「拓竹耗材台账助手」→ 服务设置，填写接口地址
```
扣减上报地址：http://127.0.0.1:8000/api/ingest/script-report
耗材台账地址：http://127.0.0.1:8000/api/ingest/script-filaments
```
粘贴你的API‑Key，测试连通之后保存配置即可

#### 4. 数据库备份与迁移
- 数据库文件：程序同级目录 `filament_db.db`
- 备份：定期复制该文件
- 迁移电脑：直接拷贝exe程序+数据库文件到新设备运行

## 💻 Windows客户端完整使用教程
### 1. Web网页端前期准备
1. 注册登录管理后台


2. 获取你的API‑Key


3. 创建耗材档案，录入耗材品牌、颜色、初始重量


### 2. v2.7‑Beta 无感监听模式（强烈推荐）
> **无需修改Bambu‑Studio切片预设、不需要配置后处理脚本**
1. 在项目 Releases 下载最新 `BambuFilamentStudio_v2.7_beta.exe`
2. 进入客户端服务设置，录入服务器地址和密钥；密钥自动保存在Windows凭据管理器加密存储

3. 开启「切片打印自动监听」


> 之后你直接发送3mf文件打印，助手弹窗自动唤起，完整保留切片所有工艺参数

<details>
<summary>📌 旧版本 v2.4及以下 后处理脚本配置（备用、现已废弃）</summary>

⚠️ v2.7以上版本无需阅读该部分

1. 获取客户端exe完整路径


2. Bambu‑Studio → 工艺 → 其他 → 最底部后处理脚本，粘贴带引号的程序路径


3. 保存工艺预设，后续打印选用该预设即可触发耗材扣减

</details>

## 🔮 开发规划 (Roadmap)
- [x] 多租户网页台账、独立API‑Key隔离
- [x] AMS多色切片解析、槽位耗材记忆
- [x] 打印记录损耗补扣、自定义克重撤销
- [x] GUI Windows桌面客户端、系统凭据加密密钥
- [x] 文件无感监听，无需切片软件配置后处理脚本

## 📄 开源协议
本项目基于 MIT License 协议开源。
欢迎 Star、Fork，有功能建议提交 Issue！
```
