# Suna 本地化沙箱方案

## 概述

本项目提供了一个完全本地化的沙箱实现方案，替代原有的 Daytona SDK 依赖，实现了：

- 🐳 **Docker 容器化**：基于 Docker 的隔离环境
- 🖥️ **图形界面支持**：集成 VNC/noVNC 远程桌面
- 🌐 **Web API 接口**：兼容原有 API 的 FastAPI 服务
- 🛠️ **浏览器自动化**：内置 Playwright 浏览器控制
- 📁 **文件管理**：完整的文件操作 API
- 🔧 **工具集成**：支持各种开发和测试工具

## 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                    Suna 本地化沙箱架构                        │
├─────────────────────────────────────────────────────────────┤
│  应用层                                                      │
│  ┌─────────────────┐  ┌─────────────────┐                   │
│  │  local_api.py   │  │ local_sandbox.py │                   │
│  │  (FastAPI接口)   │  │   (沙箱类)       │                   │
│  └─────────────────┘  └─────────────────┘                   │
├─────────────────────────────────────────────────────────────┤
│  适配层                                                      │
│  ┌─────────────────┐  ┌─────────────────┐                   │
│  │local_api_adapter│  │local_tool_base.py│                   │
│  │   (API适配器)    │  │   (工具基类)     │                   │
│  └─────────────────┘  └─────────────────┘                   │
├─────────────────────────────────────────────────────────────┤
│  管理层                                                      │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │         local_sandbox_manager.py                        │ │
│  │            (Docker 容器管理器)                           │ │
│  └─────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│  容器层                                                      │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                Docker 容器                              │ │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐        │ │
│  │  │    Xvfb     │ │    VNC      │ │   noVNC     │        │ │
│  │  │  (虚拟显示)  │ │  (远程桌面)  │ │ (Web界面)   │        │ │
│  │  └─────────────┘ └─────────────┘ └─────────────┘        │ │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐        │ │
│  │  │  File API   │ │ Browser API │ │ Supervisord │        │ │
│  │  │ (文件服务)   │ │ (浏览器控制) │ │ (进程管理)   │        │ │
│  │  └─────────────┘ └─────────────┘ └─────────────┘        │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## 功能特性

### 🔧 核心功能

- **容器管理**：自动创建、启动、停止、删除 Docker 容器
- **端口分配**：动态分配可用端口，避免冲突
- **网络隔离**：每个沙箱独立的网络环境
- **资源限制**：可配置 CPU 和内存限制
- **生命周期管理**：自动清理过期容器

### 🖥️ 图形界面

- **VNC 服务器**：x11vnc 提供远程桌面访问
- **noVNC 客户端**：基于 Web 的 VNC 客户端
- **窗口管理器**：Fluxbox 轻量级桌面环境
- **虚拟显示**：Xvfb 无头显示服务器

### 🌐 Web API

- **文件操作**：创建、读取、更新、删除文件和目录
- **命令执行**：在容器内执行 shell 命令
- **浏览器控制**：Playwright 自动化浏览器操作
- **健康检查**：监控容器和服务状态

### 🛠️ 开发工具

- **编程语言**：Python 3.11, Node.js 18
- **浏览器**：Chromium, Firefox
- **文本处理**：vim, nano, curl, wget
- **图像处理**：ImageMagick, Pillow
- **OCR 识别**：Tesseract

## 快速开始

### 1. 环境要求

- **操作系统**：Linux (推荐 Ubuntu 20.04+)
- **Docker**：20.10+ 版本
- **Docker Compose**：1.29+ 版本
- **Python**：3.8+ 版本
- **内存**：建议 8GB+ 可用内存
- **存储**：建议 20GB+ 可用空间

### 2. 安装依赖

```bash
# 安装 Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# 安装 Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 安装 Python 依赖
pip install docker fastapi uvicorn aiohttp pydantic
```

### 3. 构建沙箱镜像

```bash
# 进入本地沙箱目录
cd /mnt/disk01/workspaces/worksummary/suna/backend/sandbox/local

# 构建 Docker 镜像
./deploy.sh build

# 或者使用 docker-compose
docker-compose build
```

### 4. 启动沙箱

```bash
# 使用部署脚本启动
./deploy.sh start --project-id my-project --vnc-password mypass123

# 或者使用 docker-compose
docker-compose up -d
```

### 5. 访问服务

启动成功后，可以通过以下 URL 访问服务：

- **noVNC Web 界面**：http://localhost:6080
- **文件服务 API**：http://localhost:7788
- **浏览器控制 API**：http://localhost:8080
- **VNC 直连**：localhost:5901

## 使用示例

### Python API 使用

```python
import asyncio
from local_sandbox import LocalSandbox
from local_tool_base import ExampleLocalTool

async def example_usage():
    # 创建沙箱
    sandbox = LocalSandbox("my-project")
    await sandbox.get_or_start_sandbox(
        vnc_password="mypass123",
        resolution="1920x1080x24"
    )
    
    # 执行命令
    result = await sandbox.execute_command("ls -la /workspace")
    print(f"Command output: {result['stdout']}")
    
    # 文件操作
    await sandbox.create_directory("/workspace/test")
    
    # 使用工具
    tool = ExampleLocalTool("my-project")
    tool_result = await tool.execute_tool("echo 'Hello World!'")
    print(f"Tool result: {tool_result}")
    
    # 清理
    await sandbox.delete()

# 运行示例
asyncio.run(example_usage())
```

### REST API 使用

```bash
# 创建沙箱
curl -X POST "http://localhost:8000/sandbox/create" \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "my-project",
    "vnc_password": "mypass123",
    "resolution": "1920x1080x24"
  }'

# 列出文件
curl "http://localhost:8000/sandbox/my-project/files?path=/workspace"

# 创建文件
curl -X POST "http://localhost:8000/sandbox/my-project/files" \
  -H "Content-Type: application/json" \
  -d '{
    "path": "/workspace/hello.txt",
    "content": "Hello World!",
    "is_directory": false
  }'

# 执行命令
curl -X POST "http://localhost:8000/sandbox/my-project/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "command": "cat /workspace/hello.txt",
    "workdir": "/workspace"
  }'
```

## 配置说明

### 沙箱配置

```python
from local_sandbox_manager import SandboxConfig

config = SandboxConfig(
    project_id="my-project",           # 项目ID（必需）
    vnc_password="secure123",          # VNC密码
    resolution="1920x1080x24",         # 显示分辨率
    cpu_limit="2",                     # CPU限制
    memory_limit="4g",                 # 内存限制
    timezone="Asia/Shanghai",          # 时区设置
    ttl_hours=24                       # 生存时间（小时）
)
```

### 环境变量

```bash
# Docker 相关
DOCKER_HOST=unix:///var/run/docker.sock
DOCKER_NETWORK=suna-sandbox-network

# 沙箱配置
SANDBOX_IMAGE=suna-sandbox:latest
SANDBOX_BASE_PORT=5900
SANDBOX_PORT_RANGE=100

# 服务配置
FILE_SERVER_PORT=7788
BROWSER_API_PORT=8080
VNC_PORT=5901
NOVNC_PORT=6080

# 安全配置
WORKSPACE_PATH=/workspace
ALLOWED_EXTENSIONS=.txt,.py,.js,.html,.css,.json,.md
```

## 部署脚本

### deploy.sh 使用

```bash
# 构建镜像
./deploy.sh build

# 启动沙箱
./deploy.sh start --project-id my-project

# 停止沙箱
./deploy.sh stop my-project

# 重启沙箱
./deploy.sh restart my-project

# 删除沙箱
./deploy.sh remove my-project

# 列出所有沙箱
./deploy.sh list

# 查看日志
./deploy.sh logs my-project

# 进入容器
./deploy.sh exec my-project bash

# 检查状态
./deploy.sh status my-project

# 清理资源
./deploy.sh cleanup
```

### 高级选项

```bash
# 自定义配置启动
./deploy.sh start \
  --project-id my-project \
  --vnc-password secure123 \
  --resolution 1920x1080x24 \
  --cpu-limit 4 \
  --memory-limit 8g \
  --timezone Asia/Shanghai

# 强制操作
./deploy.sh remove my-project --force
./deploy.sh cleanup --force
```

## 测试验证

### 运行测试套件

```bash
# 运行完整测试
python test_deployment.py

# 查看测试报告
cat test_report_*.json
```

### 手动测试

```bash
# 测试 Docker 环境
docker --version
docker-compose --version

# 测试镜像构建
docker build -t suna-sandbox:test .

# 测试容器启动
docker run -d --name test-sandbox suna-sandbox:test

# 测试服务连接
curl http://localhost:6080  # noVNC
curl http://localhost:7788/health  # 文件服务
curl http://localhost:8080/health  # 浏览器API

# 清理测试
docker stop test-sandbox
docker rm test-sandbox
```

## 故障排除

### 常见问题

#### 1. Docker 权限问题

```bash
# 添加用户到 docker 组
sudo usermod -aG docker $USER
# 重新登录或执行
newgrp docker
```

#### 2. 端口冲突

```bash
# 检查端口占用
sudo netstat -tlnp | grep :6080
# 或使用 ss
ss -tlnp | grep :6080

# 修改 docker-compose.yml 中的端口映射
```

#### 3. 内存不足

```bash
# 检查内存使用
free -h
docker stats

# 调整容器内存限制
docker run --memory=2g suna-sandbox:latest
```

#### 4. VNC 连接失败

```bash
# 检查 VNC 服务状态
docker exec container_name supervisorctl status

# 重启 VNC 服务
docker exec container_name supervisorctl restart x11vnc
```

#### 5. 文件权限问题

```bash
# 检查工作空间权限
docker exec container_name ls -la /workspace

# 修复权限
docker exec container_name chown -R 1000:1000 /workspace
```

### 日志调试

```bash
# 查看容器日志
docker logs container_name

# 查看特定服务日志
docker exec container_name tail -f /var/log/supervisor/supervisord.log
docker exec container_name tail -f /var/log/supervisor/x11vnc.log
docker exec container_name tail -f /var/log/supervisor/novnc.log

# 实时监控
docker exec container_name supervisorctl tail -f x11vnc
```

## 性能优化

### 1. 镜像优化

```dockerfile
# 使用多阶段构建
FROM ubuntu:22.04 as builder
# 构建阶段...

FROM ubuntu:22.04 as runtime
# 运行时阶段...

# 清理缓存
RUN apt-get clean && rm -rf /var/lib/apt/lists/*
```

### 2. 容器资源限制

```yaml
# docker-compose.yml
services:
  suna-sandbox:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G
```

### 3. 存储优化

```bash
# 使用 tmpfs 挂载临时目录
docker run --tmpfs /tmp:rw,noexec,nosuid,size=1g suna-sandbox:latest

# 使用 volume 持久化数据
docker volume create suna-workspace
```

### 4. 网络优化

```bash
# 创建专用网络
docker network create --driver bridge suna-network

# 使用自定义 DNS
docker run --dns 8.8.8.8 suna-sandbox:latest
```

## 安全考虑

### 1. 容器安全

- 使用非 root 用户运行服务
- 限制容器权限和能力
- 定期更新基础镜像
- 扫描镜像漏洞

### 2. 网络安全

- 使用防火墙限制访问
- 配置 TLS/SSL 加密
- 实施访问控制
- 监控网络流量

### 3. 数据安全

- 加密敏感数据
- 定期备份重要数据
- 实施数据访问审计
- 清理临时文件

## 扩展开发

### 添加新工具

```python
from local_tool_base import LocalSandboxToolsBase

class MyCustomTool(LocalSandboxToolsBase):
    async def execute_tool(self, *args, **kwargs):
        # 实现自定义工具逻辑
        await self.get_or_start_sandbox()
        result = await self.execute_command("my-command")
        return result
```

### 添加新 API 端点

```python
from fastapi import APIRouter
from local_api import router

@router.post("/my-endpoint")
async def my_endpoint(project_id: str):
    # 实现自定义 API 逻辑
    return {"message": "success"}
```

### 自定义容器镜像

```dockerfile
FROM suna-sandbox:latest

# 安装额外工具
RUN apt-get update && apt-get install -y my-tool

# 添加自定义配置
COPY my-config.conf /etc/my-tool/

# 设置环境变量
ENV MY_VAR=value
```

## 贡献指南

1. Fork 项目仓库
2. 创建功能分支：`git checkout -b feature/my-feature`
3. 提交更改：`git commit -am 'Add my feature'`
4. 推送分支：`git push origin feature/my-feature`
5. 创建 Pull Request

## 许可证

本项目采用 MIT 许可证，详见 LICENSE 文件。

## 支持

如有问题或建议，请：

1. 查看本文档的故障排除部分
2. 搜索已有的 Issues
3. 创建新的 Issue 描述问题
4. 联系项目维护者

---

**注意**：本方案为 Suna 项目的本地化实现，旨在替代云端 Daytona SDK 依赖，提供完全离线的沙箱环境。在生产环境使用前，请充分测试并根据实际需求调整配置。