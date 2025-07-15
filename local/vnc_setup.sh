#!/bin/bash
# VNC设置脚本

set -e

echo "Setting up VNC..."

# 获取环境变量
VNC_PASSWORD=${VNC_PASSWORD:-vncpassword}
DISPLAY=${DISPLAY:-:99}
RESOLUTION=${RESOLUTION:-1024x768x24}

echo "VNC Password: [HIDDEN]"
echo "Display: $DISPLAY"
echo "Resolution: $RESOLUTION"

# 确保VNC目录存在
mkdir -p /root/.vnc

# 设置VNC密码
echo "$VNC_PASSWORD" | vncpasswd -f > /root/.vnc/passwd
chmod 600 /root/.vnc/passwd

# 创建VNC启动脚本
cat > /root/.vnc/xstartup << 'EOF'
#!/bin/bash

# 设置环境
export DISPLAY=:99
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8

# 启动窗口管理器
fluxbox &

# 设置背景色
xsetroot -solid grey

# 启动终端（可选）
# xterm &

EOF

chmod +x /root/.vnc/xstartup

# 创建VNC配置文件
cat > /root/.vnc/config << EOF
# VNC配置文件
session=fluxbox
geometry=${RESOLUTION%x*}
depth=${RESOLUTION##*x}
desktopname=Suna-Sandbox
EOF

echo "VNC setup completed successfully"

# 测试VNC密码文件
if [ -f /root/.vnc/passwd ]; then
    echo "VNC password file created successfully"
else
    echo "Error: Failed to create VNC password file"
    exit 1
fi

# 显示VNC配置信息
echo "=== VNC Configuration ==="
echo "Password file: /root/.vnc/passwd"
echo "Startup script: /root/.vnc/xstartup"
echo "Config file: /root/.vnc/config"
echo "Display: $DISPLAY"
echo "Resolution: $RESOLUTION"
echo "========================="