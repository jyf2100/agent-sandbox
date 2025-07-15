# 本地化沙箱Dockerfile
# 基于Ubuntu 22.04构建完整的开发环境

FROM ubuntu:22.04

# 设置环境变量
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Shanghai
ENV DISPLAY=:99
ENV RESOLUTION=1024x768x24
ENV VNC_PASSWORD=vncpassword
ENV WORKSPACE_PATH=/workspace
ENV PYTHONUNBUFFERED=1
ENV CHROME_PERSISTENT_SESSION=true
ENV ANONYMIZED_TELEMETRY=false

# 设置时区
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 更新包管理器并安装基础工具
RUN apt-get update && apt-get install -y \
    # 基础系统工具
    wget \
    curl \
    git \
    vim \
    nano \
    htop \
    tree \
    unzip \
    zip \
    tar \
    gzip \
    supervisor \
    netcat \
    net-tools \
    iputils-ping \
    telnet \
    ssh \
    rsync \
    # 开发工具
    build-essential \
    cmake \
    pkg-config \
    # Python相关
    python3 \
    python3-pip \
    python3-dev \
    python3-venv \
    # Node.js相关
    nodejs \
    npm \
    # 图形界面相关
    xvfb \
    x11vnc \
    fluxbox \
    xterm \
    tigervnc-standalone-server \
    # 浏览器相关
    chromium-browser \
    firefox \
    # 文本处理工具
    jq \
    xmlstarlet \
    # 图像处理
    imagemagick \
    # OCR工具
    tesseract-ocr \
    tesseract-ocr-chi-sim \
    tesseract-ocr-eng \
    # 字体
    fonts-liberation \
    fonts-dejavu-core \
    fonts-noto-cjk \
    # 清理缓存
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 安装noVNC
RUN mkdir -p /opt/novnc/utils/websockify \
    && wget -qO- https://github.com/novnc/noVNC/archive/v1.3.0.tar.gz | tar xz --strip 1 -C /opt/novnc \
    && wget -qO- https://github.com/novnc/websockify/archive/v0.10.0.tar.gz | tar xz --strip 1 -C /opt/novnc/utils/websockify \
    && ln -s /opt/novnc/vnc.html /opt/novnc/index.html

# 安装Python依赖
RUN pip3 install --no-cache-dir \
    fastapi==0.104.1 \
    uvicorn[standard]==0.24.0 \
    pyautogui==0.9.54 \
    pillow==10.1.0 \
    pydantic==2.5.0 \
    pytesseract==0.3.10 \
    playwright==1.40.0 \
    selenium==4.15.2 \
    beautifulsoup4==4.12.2 \
    requests==2.31.0 \
    aiofiles==23.2.1 \
    python-multipart==0.0.6

# 安装Playwright浏览器
RUN playwright install chromium \
    && playwright install-deps chromium

# 安装Node.js工具
RUN npm install -g \
    @cloudflare/wrangler \
    typescript \
    ts-node \
    nodemon \
    pm2

# 创建工作目录
RUN mkdir -p /workspace \
    && mkdir -p /opt/suna \
    && mkdir -p /var/log/supervisor \
    && mkdir -p /root/.vnc

# 设置VNC密码
RUN mkdir -p /root/.vnc \
    && echo "$VNC_PASSWORD" | vncpasswd -f > /root/.vnc/passwd \
    && chmod 600 /root/.vnc/passwd

# 复制配置文件
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY server.py /opt/suna/server.py
COPY browser_api.py /opt/suna/browser_api.py
COPY startup.sh /opt/suna/startup.sh
COPY vnc_setup.sh /opt/suna/vnc_setup.sh

# 设置执行权限
RUN chmod +x /opt/suna/startup.sh \
    && chmod +x /opt/suna/vnc_setup.sh

# 创建启动脚本
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
# 确保工作目录存在\n\
mkdir -p /workspace\n\
chmod 755 /workspace\n\
\n\
# 设置显示分辨率\n\
if [ ! -z "$RESOLUTION_WIDTH" ] && [ ! -z "$RESOLUTION_HEIGHT" ]; then\n\
    export RESOLUTION="${RESOLUTION_WIDTH}x${RESOLUTION_HEIGHT}x24"\n\
fi\n\
\n\
# 启动Xvfb\n\
Xvfb :99 -screen 0 $RESOLUTION -ac +extension GLX +render -noreset &\n\
XVFB_PID=$!\n\
\n\
# 等待X服务器启动\n\
sleep 2\n\
\n\
# 设置VNC密码\n\
if [ ! -z "$VNC_PASSWORD" ]; then\n\
    mkdir -p /root/.vnc\n\
    echo "$VNC_PASSWORD" | vncpasswd -f > /root/.vnc/passwd\n\
    chmod 600 /root/.vnc/passwd\n\
fi\n\
\n\
# 启动窗口管理器\n\
fluxbox &\n\
\n\
# 启动VNC服务器\n\
x11vnc -forever -usepw -create -rfbauth /root/.vnc/passwd -rfbport 5901 -display :99 &\n\
VNC_PID=$!\n\
\n\
# 启动noVNC\n\
/opt/novnc/utils/novnc_proxy --vnc localhost:5901 --listen 6080 &\n\
NOVNC_PID=$!\n\
\n\
# 启动文件服务器\n\
cd /opt/suna && python3 server.py &\n\
SERVER_PID=$!\n\
\n\
# 启动浏览器API\n\
cd /opt/suna && python3 browser_api.py &\n\
BROWSER_API_PID=$!\n\
\n\
# 等待所有服务启动\n\
sleep 5\n\
\n\
echo "All services started successfully"\n\
echo "VNC: localhost:5901"\n\
echo "noVNC: http://localhost:6080"\n\
echo "File Server: http://localhost:8080"\n\
echo "Browser API: http://localhost:7788"\n\
\n\
# 保持容器运行\n\
wait' > /opt/suna/start_all.sh \
    && chmod +x /opt/suna/start_all.sh

# 设置工作目录
WORKDIR /workspace

# 暴露端口
EXPOSE 5901 6080 7788 8080

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD nc -z localhost 5901 && nc -z localhost 6080 && nc -z localhost 8080 || exit 1

# 启动命令
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]