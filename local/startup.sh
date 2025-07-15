#!/bin/bash
# Suna沙箱启动脚本

set -e

echo "Starting Suna Sandbox..."

# 设置环境变量
export DISPLAY=${DISPLAY:-:99}
export RESOLUTION=${RESOLUTION:-1024x768x24}
export VNC_PASSWORD=${VNC_PASSWORD:-vncpassword}
export WORKSPACE_PATH=${WORKSPACE_PATH:-/workspace}

# 解析分辨率
if [[ $RESOLUTION =~ ^([0-9]+)x([0-9]+)x([0-9]+)$ ]]; then
    export RESOLUTION_WIDTH=${BASH_REMATCH[1]}
    export RESOLUTION_HEIGHT=${BASH_REMATCH[2]}
    export RESOLUTION_DEPTH=${BASH_REMATCH[3]}
else
    echo "Invalid resolution format: $RESOLUTION"
    export RESOLUTION_WIDTH=1024
    export RESOLUTION_HEIGHT=768
    export RESOLUTION_DEPTH=24
    export RESOLUTION="${RESOLUTION_WIDTH}x${RESOLUTION_HEIGHT}x${RESOLUTION_DEPTH}"
fi

echo "Display: $DISPLAY"
echo "Resolution: $RESOLUTION"
echo "Workspace: $WORKSPACE_PATH"

# 确保工作目录存在
mkdir -p "$WORKSPACE_PATH"
chmod 755 "$WORKSPACE_PATH"

# 确保VNC目录存在
mkdir -p /root/.vnc

# 设置VNC密码
echo "Setting up VNC password..."
echo "$VNC_PASSWORD" | vncpasswd -f > /root/.vnc/passwd
chmod 600 /root/.vnc/passwd

# 启动Xvfb
echo "Starting Xvfb..."
Xvfb $DISPLAY -screen 0 $RESOLUTION -ac +extension GLX +render -noreset &
XVFB_PID=$!

# 等待X服务器启动
echo "Waiting for X server to start..."
sleep 3

# 检查X服务器是否启动成功
if ! xdpyinfo -display $DISPLAY >/dev/null 2>&1; then
    echo "Failed to start X server"
    exit 1
fi

echo "X server started successfully"

# 启动窗口管理器
echo "Starting window manager..."
fluxbox &
WM_PID=$!

# 启动VNC服务器
echo "Starting VNC server..."
x11vnc -forever -usepw -create -rfbauth /root/.vnc/passwd -rfbport 5901 -display $DISPLAY -shared &
VNC_PID=$!

# 等待VNC服务器启动
echo "Waiting for VNC server to start..."
sleep 2

# 检查VNC服务器是否启动成功
if ! nc -z localhost 5901; then
    echo "Failed to start VNC server"
    exit 1
fi

echo "VNC server started successfully"

# 启动noVNC
echo "Starting noVNC..."
/opt/novnc/utils/novnc_proxy --vnc localhost:5901 --listen 6080 &
NOVNC_PID=$!

# 等待noVNC启动
echo "Waiting for noVNC to start..."
sleep 2

# 检查noVNC是否启动成功
if ! nc -z localhost 6080; then
    echo "Failed to start noVNC"
    exit 1
fi

echo "noVNC started successfully"

# 启动文件服务器
echo "Starting file server..."
cd /opt/suna
python3 server.py &
FILE_SERVER_PID=$!

# 等待文件服务器启动
echo "Waiting for file server to start..."
sleep 3

# 检查文件服务器是否启动成功
if ! nc -z localhost 8080; then
    echo "Failed to start file server"
    exit 1
fi

echo "File server started successfully"

# 启动浏览器API
echo "Starting browser API..."
cd /opt/suna
python3 browser_api.py &
BROWSER_API_PID=$!

# 等待浏览器API启动
echo "Waiting for browser API to start..."
sleep 5

# 检查浏览器API是否启动成功
if ! nc -z localhost 7788; then
    echo "Warning: Browser API may not have started properly"
fi

echo "Browser API started"

# 显示服务状态
echo "=== Suna Sandbox Services ==="
echo "VNC Server: localhost:5901 (password: $VNC_PASSWORD)"
echo "noVNC Web: http://localhost:6080"
echo "File Server: http://localhost:8080"
echo "Browser API: http://localhost:7788"
echo "Workspace: $WORKSPACE_PATH"
echo "=============================="

# 创建状态文件
cat > /tmp/suna_status.json << EOF
{
    "status": "running",
    "services": {
        "xvfb": {
            "pid": $XVFB_PID,
            "port": null,
            "display": "$DISPLAY"
        },
        "vnc": {
            "pid": $VNC_PID,
            "port": 5901,
            "password": "$VNC_PASSWORD"
        },
        "novnc": {
            "pid": $NOVNC_PID,
            "port": 6080,
            "url": "http://localhost:6080"
        },
        "file_server": {
            "pid": $FILE_SERVER_PID,
            "port": 8080,
            "url": "http://localhost:8080"
        },
        "browser_api": {
            "pid": $BROWSER_API_PID,
            "port": 7788,
            "url": "http://localhost:7788"
        }
    },
    "workspace": "$WORKSPACE_PATH",
    "resolution": "$RESOLUTION",
    "started_at": "$(date -Iseconds)"
}
EOF

echo "Suna Sandbox started successfully!"
echo "Status file: /tmp/suna_status.json"

# 保持脚本运行
echo "Keeping services alive..."
while true; do
    # 检查关键服务是否还在运行
    if ! kill -0 $XVFB_PID 2>/dev/null; then
        echo "Xvfb process died, restarting..."
        Xvfb $DISPLAY -screen 0 $RESOLUTION -ac +extension GLX +render -noreset &
        XVFB_PID=$!
    fi
    
    if ! kill -0 $VNC_PID 2>/dev/null; then
        echo "VNC server died, restarting..."
        x11vnc -forever -usepw -create -rfbauth /root/.vnc/passwd -rfbport 5901 -display $DISPLAY -shared &
        VNC_PID=$!
    fi
    
    if ! kill -0 $NOVNC_PID 2>/dev/null; then
        echo "noVNC died, restarting..."
        /opt/novnc/utils/novnc_proxy --vnc localhost:5901 --listen 6080 &
        NOVNC_PID=$!
    fi
    
    if ! kill -0 $FILE_SERVER_PID 2>/dev/null; then
        echo "File server died, restarting..."
        cd /opt/suna && python3 server.py &
        FILE_SERVER_PID=$!
    fi
    
    if ! kill -0 $BROWSER_API_PID 2>/dev/null; then
        echo "Browser API died, restarting..."
        cd /opt/suna && python3 browser_api.py &
        BROWSER_API_PID=$!
    fi
    
    sleep 30
done