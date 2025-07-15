#!/bin/bash
# Suna本地沙箱部署脚本

set -e

# 脚本配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_NAME="local-suna-sandbox"
IMAGE_TAG="latest"
NETWORK_NAME="suna-sandbox-network"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 显示帮助信息
show_help() {
    cat << EOF
Suna本地沙箱部署脚本

用法: $0 [命令] [选项]

命令:
  build                构建沙箱镜像
  start PROJECT_ID     启动指定项目的沙箱
  stop PROJECT_ID      停止指定项目的沙箱
  restart PROJECT_ID   重启指定项目的沙箱
  remove PROJECT_ID    删除指定项目的沙箱
  list                 列出所有沙箱
  logs PROJECT_ID      查看沙箱日志
  exec PROJECT_ID      进入沙箱容器
  status PROJECT_ID    查看沙箱状态
  cleanup              清理未使用的资源
  help                 显示此帮助信息

选项:
  --vnc-password PWD   设置VNC密码 (默认: vncpassword)
  --resolution RES     设置分辨率 (默认: 1024x768x24)
  --cpu-limit NUM      设置CPU限制 (默认: 2)
  --memory-limit SIZE  设置内存限制 (默认: 4G)
  --force              强制执行操作
  --no-build           跳过镜像构建

示例:
  $0 build
  $0 start my-project --vnc-password mypass
  $0 stop my-project
  $0 list
  $0 cleanup

EOF
}

# 检查依赖
check_dependencies() {
    log_info "检查依赖..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker未安装或不在PATH中"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose未安装或不在PATH中"
        exit 1
    fi
    
    # 检查Docker是否运行
    if ! docker info &> /dev/null; then
        log_error "Docker守护进程未运行"
        exit 1
    fi
    
    log_success "依赖检查通过"
}

# 构建镜像
build_image() {
    log_info "构建沙箱镜像..."
    
    cd "$SCRIPT_DIR"
    
    # 检查Dockerfile是否存在
    if [ ! -f "Dockerfile" ]; then
        log_error "Dockerfile不存在"
        exit 1
    fi
    
    # 构建镜像
    docker build -t "${IMAGE_NAME}:${IMAGE_TAG}" .
    
    log_success "镜像构建完成: ${IMAGE_NAME}:${IMAGE_TAG}"
}

# 创建网络
ensure_network() {
    if ! docker network ls | grep -q "$NETWORK_NAME"; then
        log_info "创建Docker网络: $NETWORK_NAME"
        docker network create "$NETWORK_NAME" --driver bridge
    fi
}

# 启动沙箱
start_sandbox() {
    local project_id="$1"
    
    if [ -z "$project_id" ]; then
        log_error "请指定项目ID"
        exit 1
    fi
    
    log_info "启动沙箱: $project_id"
    
    # 检查容器是否已存在
    if docker ps -a --format '{{.Names}}' | grep -q "^suna-sandbox-${project_id}$"; then
        if docker ps --format '{{.Names}}' | grep -q "^suna-sandbox-${project_id}$"; then
            log_warning "沙箱已在运行: $project_id"
            return 0
        else
            log_info "启动现有容器: $project_id"
            docker start "suna-sandbox-${project_id}"
            log_success "沙箱启动成功: $project_id"
            return 0
        fi
    fi
    
    # 确保网络存在
    ensure_network
    
    # 分配端口
    local vnc_port=$(find_free_port 15901 16000)
    local novnc_port=$(find_free_port 16080 16179)
    local browser_api_port=$(find_free_port 17788 17887)
    local file_server_port=$(find_free_port 18080 18179)
    
    log_info "分配端口: VNC=$vnc_port, noVNC=$novnc_port, Browser API=$browser_api_port, File Server=$file_server_port"
    
    # 设置环境变量
    export PROJECT_ID="$project_id"
    export VNC_PORT="$vnc_port"
    export NOVNC_PORT="$novnc_port"
    export BROWSER_API_PORT="$browser_api_port"
    export FILE_SERVER_PORT="$file_server_port"
    export VNC_PASSWORD="${VNC_PASSWORD:-vncpassword}"
    export RESOLUTION="${RESOLUTION:-1024x768x24}"
    export CPU_LIMIT="${CPU_LIMIT:-2}"
    export MEMORY_LIMIT="${MEMORY_LIMIT:-4G}"
    
    # 解析分辨率
    if [[ $RESOLUTION =~ ^([0-9]+)x([0-9]+)x([0-9]+)$ ]]; then
        export RESOLUTION_WIDTH=${BASH_REMATCH[1]}
        export RESOLUTION_HEIGHT=${BASH_REMATCH[2]}
    fi
    
    cd "$SCRIPT_DIR"
    
    # 启动容器
    docker-compose up -d
    
    # 等待服务启动
    log_info "等待服务启动..."
    sleep 10
    
    # 检查健康状态
    local max_attempts=30
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if docker exec "suna-sandbox-${project_id}" nc -z localhost 5901 2>/dev/null && \
           docker exec "suna-sandbox-${project_id}" nc -z localhost 6080 2>/dev/null && \
           docker exec "suna-sandbox-${project_id}" nc -z localhost 8080 2>/dev/null; then
            break
        fi
        
        attempt=$((attempt + 1))
        log_info "等待服务启动... ($attempt/$max_attempts)"
        sleep 2
    done
    
    if [ $attempt -eq $max_attempts ]; then
        log_warning "服务可能未完全启动，请检查日志"
    fi
    
    log_success "沙箱启动成功: $project_id"
    
    # 显示访问信息
    echo
    echo "=== 沙箱访问信息 ==="
    echo "项目ID: $project_id"
    echo "VNC: vnc://localhost:$vnc_port (密码: $VNC_PASSWORD)"
    echo "noVNC: http://localhost:$novnc_port"
    echo "文件服务器: http://localhost:$file_server_port"
    echo "浏览器API: http://localhost:$browser_api_port"
    echo "==================="
}

# 查找空闲端口
find_free_port() {
    local start_port=$1
    local end_port=$2
    
    for port in $(seq $start_port $end_port); do
        if ! ss -tuln | grep -q ":$port "; then
            echo $port
            return 0
        fi
    done
    
    log_error "无法找到空闲端口 ($start_port-$end_port)"
    exit 1
}

# 停止沙箱
stop_sandbox() {
    local project_id="$1"
    
    if [ -z "$project_id" ]; then
        log_error "请指定项目ID"
        exit 1
    fi
    
    log_info "停止沙箱: $project_id"
    
    if docker ps --format '{{.Names}}' | grep -q "^suna-sandbox-${project_id}$"; then
        docker stop "suna-sandbox-${project_id}"
        log_success "沙箱已停止: $project_id"
    else
        log_warning "沙箱未运行: $project_id"
    fi
}

# 重启沙箱
restart_sandbox() {
    local project_id="$1"
    
    log_info "重启沙箱: $project_id"
    stop_sandbox "$project_id"
    sleep 2
    start_sandbox "$project_id"
}

# 删除沙箱
remove_sandbox() {
    local project_id="$1"
    
    if [ -z "$project_id" ]; then
        log_error "请指定项目ID"
        exit 1
    fi
    
    log_info "删除沙箱: $project_id"
    
    # 停止容器
    if docker ps --format '{{.Names}}' | grep -q "^suna-sandbox-${project_id}$"; then
        docker stop "suna-sandbox-${project_id}"
    fi
    
    # 删除容器
    if docker ps -a --format '{{.Names}}' | grep -q "^suna-sandbox-${project_id}$"; then
        docker rm "suna-sandbox-${project_id}"
    fi
    
    # 删除数据卷
    if docker volume ls --format '{{.Name}}' | grep -q "^suna-workspace-${project_id}$"; then
        if [ "$FORCE" = "true" ]; then
            docker volume rm "suna-workspace-${project_id}"
            log_success "数据卷已删除: suna-workspace-${project_id}"
        else
            log_warning "数据卷未删除: suna-workspace-${project_id} (使用 --force 强制删除)"
        fi
    fi
    
    log_success "沙箱已删除: $project_id"
}

# 列出沙箱
list_sandboxes() {
    log_info "沙箱列表:"
    
    echo
    printf "%-20s %-15s %-10s %-30s\n" "项目ID" "状态" "端口" "创建时间"
    printf "%-20s %-15s %-10s %-30s\n" "--------------------" "---------------" "----------" "------------------------------"
    
    docker ps -a --filter "label=suna.service=sandbox" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}\t{{.CreatedAt}}" | \
    tail -n +2 | while read line; do
        name=$(echo "$line" | awk '{print $1}')
        status=$(echo "$line" | awk '{print $2}')
        ports=$(echo "$line" | awk '{print $3}')
        created=$(echo "$line" | awk '{print $4" "$5" "$6}')
        
        project_id=${name#suna-sandbox-}
        
        printf "%-20s %-15s %-10s %-30s\n" "$project_id" "$status" "$ports" "$created"
    done
    
    echo
}

# 查看日志
show_logs() {
    local project_id="$1"
    
    if [ -z "$project_id" ]; then
        log_error "请指定项目ID"
        exit 1
    fi
    
    log_info "查看沙箱日志: $project_id"
    
    if docker ps -a --format '{{.Names}}' | grep -q "^suna-sandbox-${project_id}$"; then
        docker logs -f "suna-sandbox-${project_id}"
    else
        log_error "沙箱不存在: $project_id"
        exit 1
    fi
}

# 进入容器
exec_container() {
    local project_id="$1"
    
    if [ -z "$project_id" ]; then
        log_error "请指定项目ID"
        exit 1
    fi
    
    log_info "进入沙箱容器: $project_id"
    
    if docker ps --format '{{.Names}}' | grep -q "^suna-sandbox-${project_id}$"; then
        docker exec -it "suna-sandbox-${project_id}" /bin/bash
    else
        log_error "沙箱未运行: $project_id"
        exit 1
    fi
}

# 查看状态
show_status() {
    local project_id="$1"
    
    if [ -z "$project_id" ]; then
        log_error "请指定项目ID"
        exit 1
    fi
    
    log_info "沙箱状态: $project_id"
    
    if docker ps -a --format '{{.Names}}' | grep -q "^suna-sandbox-${project_id}$"; then
        echo
        docker inspect "suna-sandbox-${project_id}" --format '
容器状态: {{.State.Status}}
启动时间: {{.State.StartedAt}}
重启次数: {{.RestartCount}}
端口映射: {{range $p, $conf := .NetworkSettings.Ports}}{{$p}} -> {{(index $conf 0).HostPort}} {{end}}
数据卷: {{range .Mounts}}{{.Source}} -> {{.Destination}} {{end}}
'
        
        # 检查服务状态
        if docker ps --format '{{.Names}}' | grep -q "^suna-sandbox-${project_id}$"; then
            echo "服务状态:"
            docker exec "suna-sandbox-${project_id}" bash -c '
                echo "  VNC: $(nc -z localhost 5901 && echo "运行中" || echo "未运行")"
                echo "  noVNC: $(nc -z localhost 6080 && echo "运行中" || echo "未运行")"
                echo "  文件服务器: $(nc -z localhost 8080 && echo "运行中" || echo "未运行")"
                echo "  浏览器API: $(nc -z localhost 7788 && echo "运行中" || echo "未运行")"
            ' 2>/dev/null || echo "  无法检查服务状态"
        fi
    else
        log_error "沙箱不存在: $project_id"
        exit 1
    fi
}

# 清理资源
cleanup() {
    log_info "清理未使用的资源..."
    
    # 清理停止的容器
    local stopped_containers=$(docker ps -a --filter "label=suna.service=sandbox" --filter "status=exited" --format "{{.Names}}")
    if [ -n "$stopped_containers" ]; then
        echo "$stopped_containers" | xargs docker rm
        log_success "已清理停止的容器"
    fi
    
    # 清理未使用的镜像
    docker image prune -f --filter "label=suna.service=sandbox"
    
    # 清理未使用的数据卷
    if [ "$FORCE" = "true" ]; then
        docker volume prune -f --filter "label=suna.workspace=true"
        log_success "已清理未使用的数据卷"
    else
        log_warning "跳过数据卷清理 (使用 --force 强制清理)"
    fi
    
    log_success "资源清理完成"
}

# 解析命令行参数
COMMAND=""
PROJECT_ID=""
VNC_PASSWORD="vncpassword"
RESOLUTION="1024x768x24"
CPU_LIMIT="2"
MEMORY_LIMIT="4G"
FORCE="false"
NO_BUILD="false"

while [[ $# -gt 0 ]]; do
    case $1 in
        build|start|stop|restart|remove|list|logs|exec|status|cleanup|help)
            COMMAND="$1"
            shift
            ;;
        --vnc-password)
            VNC_PASSWORD="$2"
            shift 2
            ;;
        --resolution)
            RESOLUTION="$2"
            shift 2
            ;;
        --cpu-limit)
            CPU_LIMIT="$2"
            shift 2
            ;;
        --memory-limit)
            MEMORY_LIMIT="$2"
            shift 2
            ;;
        --force)
            FORCE="true"
            shift
            ;;
        --no-build)
            NO_BUILD="true"
            shift
            ;;
        -*)
            log_error "未知选项: $1"
            show_help
            exit 1
            ;;
        *)
            if [ -z "$PROJECT_ID" ]; then
                PROJECT_ID="$1"
            else
                log_error "多余的参数: $1"
                show_help
                exit 1
            fi
            shift
            ;;
    esac
done

# 主逻辑
case "$COMMAND" in
    build)
        check_dependencies
        build_image
        ;;
    start)
        check_dependencies
        if [ "$NO_BUILD" != "true" ]; then
            build_image
        fi
        start_sandbox "$PROJECT_ID"
        ;;
    stop)
        check_dependencies
        stop_sandbox "$PROJECT_ID"
        ;;
    restart)
        check_dependencies
        restart_sandbox "$PROJECT_ID"
        ;;
    remove)
        check_dependencies
        remove_sandbox "$PROJECT_ID"
        ;;
    list)
        check_dependencies
        list_sandboxes
        ;;
    logs)
        check_dependencies
        show_logs "$PROJECT_ID"
        ;;
    exec)
        check_dependencies
        exec_container "$PROJECT_ID"
        ;;
    status)
        check_dependencies
        show_status "$PROJECT_ID"
        ;;
    cleanup)
        check_dependencies
        cleanup
        ;;
    help|"")
        show_help
        ;;
    *)
        log_error "未知命令: $COMMAND"
        show_help
        exit 1
        ;;
esac