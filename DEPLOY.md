# 服务器部署指南（情况二：同事通过链接直接访问）

将本项目部署到公司内网服务器或云服务器后，同事在浏览器打开你分享的链接即可使用，无需安装任何环境。

---

## 一、服务器要求

- **系统**：Linux（如 Ubuntu 20.04+、CentOS 7+）
- **Python**：3.8 及以上
- **网络**：同事能访问该服务器的 IP 或域名（同一内网或公网）

---

## 二、部署步骤

### 1. 上传代码到服务器

在服务器上克隆或上传本项目，例如：

```bash
cd /opt   # 或你希望的目录
git clone <你的仓库地址> conversation-analysis-tool
cd conversation-analysis-tool
```

若没有 git，可用 scp、SFTP 等方式把项目文件夹上传到服务器。

### 2. 创建虚拟环境并安装依赖（推荐）

```bash
python3 -m venv venv
source venv/bin/activate   # Linux/macOS
# Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### 3. 可选：配置 .env

仅使用「差额定率累进计算」页面可不配置。若需使用对话分析、Gemini 等功能：

```bash
cp .env.example .env
# 编辑 .env，填入 GEMINI_API_KEY 等
```

### 4. 用 Gunicorn 启动服务（生产推荐）

在项目根目录执行：

```bash
# 若已创建虚拟环境，先 source venv/bin/activate
gunicorn -w 4 -b 0.0.0.0:5001 --timeout 120 app:app
```

- `-w 4`：4 个 worker，可按 CPU 核数调整
- `-b 0.0.0.0:5001`：监听 5001 端口，允许外网/内网访问
- `app:app`：模块名 `app`，变量名 `app`（Flask 实例）

同事访问：`http://服务器IP:5001/progressive-rate`（差额定率页）或 `http://服务器IP:5001`（首页）。

### 5. 后台常驻：使用 systemd（推荐）

避免关闭终端后进程退出，可用 systemd 托管。

创建服务文件：

```bash
sudo nano /etc/systemd/system/conversation-tool.service
```

写入（请把 `WorkingDirectory` 和 `ExecStart` 中的路径改成你项目的实际路径）：

```ini
[Unit]
Description=Conversation Analysis Tool (Flask)
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/conversation-analysis-tool
Environment="PATH=/opt/conversation-analysis-tool/venv/bin"
ExecStart=/opt/conversation-analysis-tool/venv/bin/gunicorn -w 4 -b 127.0.0.1:5001 --timeout 120 app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

说明：

- `User/Group` 可改为你用来运行服务的用户（如 `root` 或 `deploy`）
- `WorkingDirectory`、`Environment`、`ExecStart` 中的路径需与项目及 venv 位置一致
- 若直接用 `0.0.0.0:5001`，则无需 Nginx 也可被内网访问；若为 `127.0.0.1:5001`，则需下面 Nginx 反代

启用并启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable conversation-tool
sudo systemctl start conversation-tool
sudo systemctl status conversation-tool
```

之后重启服务器也会自动启动该服务。

---

## 三、可选：用 Nginx 做反向代理（适合有域名或 80 端口）

若希望用 80/443 端口或域名访问（如 `http://tool.company.com/progressive-rate`），可在同一台机子上安装 Nginx，把请求转发给 Gunicorn。

### 1. 安装 Nginx

```bash
# Ubuntu/Debian
sudo apt update && sudo apt install nginx -y

# CentOS
sudo yum install nginx -y
```

### 2. 配置站点

新建配置（以 Ubuntu 为例）：

```bash
sudo nano /etc/nginx/sites-available/conversation-tool
```

示例内容（按需改 `server_name` 和 `proxy_pass`）：

```nginx
server {
    listen 80;
    server_name tool.company.com;   # 改为你的域名或服务器 IP

    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 120s;
        proxy_read_timeout 120s;
    }
}
```

启用并重载 Nginx：

```bash
sudo ln -s /etc/nginx/sites-available/conversation-tool /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

此时 systemd 里 Gunicorn 应绑定 `127.0.0.1:5001`（如上示例），由 Nginx 对外提供 80 端口。

同事访问：`http://tool.company.com/progressive-rate` 或 `http://服务器IP/progressive-rate`。

### 3. 可选：HTTPS（Let’s Encrypt）

若域名已解析到该服务器，可安装 certbot 申请证书：

```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d tool.company.com
```

之后可改为访问：`https://tool.company.com/progressive-rate`。

---

## 四、分享给同事的链接

部署完成后，把下面任一链接发给同事即可（替换为你的实际地址）：

- 仅 Gunicorn、无 Nginx：`http://服务器IP:5001/progressive-rate`
- 有 Nginx 或域名：`http://域名或IP/progressive-rate`（或 `https://...`）

同事用自己电脑浏览器打开即可，无需安装 Python 或任何前置准备。

---

## 五、常见问题

| 问题 | 处理 |
|------|------|
| 同事打不开链接 | 检查服务器防火墙是否放行 5001 或 80 端口；内网部署需保证同事与服务器在同一网络。 |
| 502 Bad Gateway | Gunicorn 未启动或未监听 127.0.0.1:5001；用 `systemctl status conversation-tool` 和 `curl http://127.0.0.1:5001` 排查。 |
| 修改代码后不生效 | 执行 `sudo systemctl restart conversation-tool` 重启服务。 |
