#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地沙箱管理器
替代Daytona SDK，提供完全本地化的容器管理功能
"""

import asyncio
import docker
import json
import logging
import os
import random
import time
from typing import Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

@dataclass
class SandboxConfig:
    """沙箱配置类"""
    project_id: str
    vnc_password: str = "vncpassword"
    resolution: str = "1024x768x24"
    cpu_limit: int = 2
    memory_limit: str = "4g"
    disk_limit: str = "10g"
    auto_stop_hours: int = 24
    
class PortManager:
    """端口管理器，负责分配和回收端口"""
    
    def __init__(self):
        self.allocated_ports = set()
        self.port_ranges = {
            'vnc': (15901, 16000),
            'novnc': (16080, 16179), 
            'browser_api': (17788, 17887),
            'file_server': (18080, 18179)
        }
    
    def allocate_ports(self, project_id: str) -> Dict[str, int]:
        """为项目分配端口"""
        ports = {}
        
        for service, (start, end) in self.port_ranges.items():
            for port in range(start, end + 1):
                if port not in self.allocated_ports:
                    self.allocated_ports.add(port)
                    ports[service] = port
                    break
            else:
                raise RuntimeError(f"No available ports for service {service}")
        
        logger.info(f"Allocated ports for project {project_id}: {ports}")
        return ports
    
    def release_ports(self, ports: Dict[str, int]):
        """释放端口"""
        for port in ports.values():
            self.allocated_ports.discard(port)
        logger.info(f"Released ports: {list(ports.values())}")

class LocalSandboxManager:
    """本地沙箱管理器"""
    
    def __init__(self, docker_host: str = "unix:///var/run/docker.sock"):
        """
        初始化本地沙箱管理器
        
        Args:
            docker_host: Docker守护进程地址
        """
        try:
            self.docker = docker.from_env() if docker_host == 'unix://var/run/docker.sock' else docker.DockerClient(base_url=docker_host)
            # 测试连接
            self.docker.ping()
            logger.info(f"Connected to Docker at {docker_host}")
        except Exception as e:
            logger.error(f"Failed to initialize Docker client: {e}")
            raise
        
        self.containers = {}  # project_id -> container info
        self.port_manager = PortManager()
        self.base_image = "local-suna-sandbox:latest"
        self.network_name = "suna-sandbox-network"
        
        # 确保网络存在
        self._ensure_network()
    
    def _ensure_network(self):
        """确保沙箱网络存在"""
        try:
            self.docker.networks.get(self.network_name)
            logger.info(f"Network {self.network_name} already exists")
        except docker.errors.NotFound:
            self.docker.networks.create(
                self.network_name,
                driver="bridge",
                options={"com.docker.network.bridge.name": "suna-br0"}
            )
            logger.info(f"Created network {self.network_name}")
    
    async def create_sandbox(self, config: SandboxConfig) -> str:
        """
        创建新的沙箱容器
        
        Args:
            config: 沙箱配置
            
        Returns:
            容器ID
        """
        project_id = config.project_id
        container_name = f"suna-sandbox-{project_id}"
        
        # 检查是否已存在
        if project_id in self.containers:
            raise ValueError(f"Sandbox for project {project_id} already exists")
        
        # 分配端口
        ports = self.port_manager.allocate_ports(project_id)
        
        try:
            # 创建数据卷
            volume_name = f"suna-workspace-{project_id}"
            try:
                self.docker.volumes.get(volume_name)
            except docker.errors.NotFound:
                self.docker.volumes.create(volume_name)
                logger.info(f"Created volume {volume_name}")
            
            # 容器配置
            container_config = {
                'image': self.base_image,
                'name': container_name,
                'ports': {
                    '5901/tcp': ports['vnc'],
                    '6080/tcp': ports['novnc'],
                    '7788/tcp': ports['browser_api'],
                    '8080/tcp': ports['file_server'],
                },
                'environment': {
                    'VNC_PASSWORD': config.vnc_password,
                    'RESOLUTION': config.resolution,
                    'RESOLUTION_WIDTH': config.resolution.split('x')[0],
                    'RESOLUTION_HEIGHT': config.resolution.split('x')[1],
                    'WORKSPACE_PATH': '/workspace',
                    'DISPLAY': ':99',
                    'PYTHONUNBUFFERED': '1',
                    'CHROME_PERSISTENT_SESSION': 'true',
                    'ANONYMIZED_TELEMETRY': 'false',
                },
                'volumes': {
                    volume_name: {'bind': '/workspace', 'mode': 'rw'}
                },
                'shm_size': '2g',
                'cap_add': ['SYS_ADMIN'],
                'security_opt': ['seccomp=unconfined'],
                'restart_policy': {'Name': 'unless-stopped'},
                'network': self.network_name,
                'mem_limit': config.memory_limit,
                'cpu_count': config.cpu_limit,
                'labels': {
                    'suna.project_id': project_id,
                    'suna.created_at': datetime.now().isoformat(),
                    'suna.auto_stop_at': (datetime.now() + timedelta(hours=config.auto_stop_hours)).isoformat()
                }
            }
            
            # 创建并启动容器
            container = self.docker.containers.run(**container_config, detach=True)
            logger.info(f"Created container {container.id} for project {project_id}")
            
            # 等待服务启动
            await self._wait_for_services(container)
            
            # 保存容器信息
            self.containers[project_id] = {
                'container': container,
                'ports': ports,
                'config': config,
                'created_at': datetime.now(),
                'volume_name': volume_name
            }
            
            logger.info(f"Sandbox created successfully for project {project_id}")
            return container.id
            
        except Exception as e:
            # 清理资源
            self.port_manager.release_ports(ports)
            logger.error(f"Failed to create sandbox for project {project_id}: {e}")
            raise
    
    async def get_sandbox(self, project_id: str) -> Dict[str, Any]:
        """
        获取沙箱信息
        
        Args:
            project_id: 项目ID
            
        Returns:
            沙箱信息字典
        """
        if project_id in self.containers:
            container_info = self.containers[project_id]
            container = container_info['container']
            container.reload()
            
            return {
                'id': container.id,
                'name': container.name,
                'status': container.status,
                'ports': self._format_ports(container_info['ports']),
                'created_at': container_info['created_at'].isoformat(),
                'config': container_info['config'].__dict__,
                'urls': self._generate_service_urls(container_info['ports'])
            }
        
        # 尝试从Docker中查找现有容器
        try:
            container = self.docker.containers.get(f"suna-sandbox-{project_id}")
            
            # 从标签中恢复信息
            labels = container.labels
            if labels.get('suna.project_id') == project_id:
                # 重建容器信息
                ports = self._extract_ports_from_container(container)
                config = SandboxConfig(project_id=project_id)  # 使用默认配置
                
                self.containers[project_id] = {
                    'container': container,
                    'ports': ports,
                    'config': config,
                    'created_at': datetime.fromisoformat(labels.get('suna.created_at', datetime.now().isoformat())),
                    'volume_name': f"suna-workspace-{project_id}"
                }
                
                return await self.get_sandbox(project_id)
        except docker.errors.NotFound:
            pass
        
        raise ValueError(f"Sandbox for project {project_id} not found")
    
    async def start_sandbox(self, project_id: str):
        """
        启动沙箱
        
        Args:
            project_id: 项目ID
        """
        sandbox_info = await self.get_sandbox(project_id)
        container_info = self.containers[project_id]
        container = container_info['container']
        
        if container.status != 'running':
            container.start()
            await self._wait_for_services(container)
            logger.info(f"Started sandbox for project {project_id}")
        else:
            logger.info(f"Sandbox for project {project_id} is already running")
    
    async def stop_sandbox(self, project_id: str):
        """
        停止沙箱
        
        Args:
            project_id: 项目ID
        """
        if project_id in self.containers:
            container = self.containers[project_id]['container']
            container.stop()
            logger.info(f"Stopped sandbox for project {project_id}")
        else:
            raise ValueError(f"Sandbox for project {project_id} not found")
    
    async def delete_sandbox(self, project_id: str):
        """
        删除沙箱
        
        Args:
            project_id: 项目ID
        """
        if project_id in self.containers:
            container_info = self.containers[project_id]
            container = container_info['container']
            
            # 停止并删除容器
            try:
                container.stop()
            except:
                pass
            container.remove(force=True)
            
            # 删除数据卷
            try:
                volume = self.docker.volumes.get(container_info['volume_name'])
                volume.remove()
                logger.info(f"Removed volume {container_info['volume_name']}")
            except docker.errors.NotFound:
                pass
            
            # 释放端口
            self.port_manager.release_ports(container_info['ports'])
            
            # 从缓存中移除
            del self.containers[project_id]
            
            logger.info(f"Deleted sandbox for project {project_id}")
        else:
            raise ValueError(f"Sandbox for project {project_id} not found")
    
    async def list_sandboxes(self) -> Dict[str, Dict[str, Any]]:
        """
        列出所有沙箱
        
        Returns:
            沙箱信息字典
        """
        sandboxes = {}
        
        # 从Docker中查找所有沙箱容器
        containers = self.docker.containers.list(
            all=True,
            filters={'label': 'suna.project_id'}
        )
        
        for container in containers:
            project_id = container.labels.get('suna.project_id')
            if project_id:
                try:
                    sandbox_info = await self.get_sandbox(project_id)
                    sandboxes[project_id] = sandbox_info
                except Exception as e:
                    logger.warning(f"Failed to get info for sandbox {project_id}: {e}")
        
        return sandboxes
    
    async def cleanup_expired_sandboxes(self):
        """
        清理过期的沙箱
        """
        current_time = datetime.now()
        expired_projects = []
        
        containers = self.docker.containers.list(
            all=True,
            filters={'label': 'suna.auto_stop_at'}
        )
        
        for container in containers:
            auto_stop_at_str = container.labels.get('suna.auto_stop_at')
            if auto_stop_at_str:
                try:
                    auto_stop_at = datetime.fromisoformat(auto_stop_at_str)
                    if current_time > auto_stop_at:
                        project_id = container.labels.get('suna.project_id')
                        if project_id:
                            expired_projects.append(project_id)
                except ValueError:
                    logger.warning(f"Invalid auto_stop_at format: {auto_stop_at_str}")
        
        for project_id in expired_projects:
            try:
                await self.delete_sandbox(project_id)
                logger.info(f"Cleaned up expired sandbox for project {project_id}")
            except Exception as e:
                logger.error(f"Failed to cleanup sandbox {project_id}: {e}")
    
    def _format_ports(self, ports: Dict[str, int]) -> Dict[str, Dict[str, Any]]:
        """格式化端口信息"""
        formatted = {}
        for service, port in ports.items():
            formatted[service] = {
                'internal': {
                    'vnc': 5901,
                    'novnc': 6080,
                    'browser_api': 7788,
                    'file_server': 8080
                }.get(service, 8000),
                'external': port
            }
        return formatted
    
    def _generate_service_urls(self, ports: Dict[str, int]) -> Dict[str, str]:
        """生成服务访问URL"""
        return {
            'vnc': f"vnc://localhost:{ports['vnc']}",
            'novnc': f"http://localhost:{ports['novnc']}",
            'browser_api': f"http://localhost:{ports['browser_api']}",
            'file_server': f"http://localhost:{ports['file_server']}"
        }
    
    def _extract_ports_from_container(self, container) -> Dict[str, int]:
        """从容器中提取端口映射"""
        ports = {}
        port_bindings = container.attrs['NetworkSettings']['Ports']
        
        port_mapping = {
            '5901/tcp': 'vnc',
            '6080/tcp': 'novnc',
            '7788/tcp': 'browser_api',
            '8080/tcp': 'file_server'
        }
        
        for internal_port, bindings in port_bindings.items():
            if bindings and internal_port in port_mapping:
                external_port = int(bindings[0]['HostPort'])
                service_name = port_mapping[internal_port]
                ports[service_name] = external_port
        
        return ports
    
    async def _wait_for_services(self, container, timeout: int = 120):
        """
        等待容器内服务启动完成
        
        Args:
            container: Docker容器对象
            timeout: 超时时间（秒）
        """
        start_time = time.time()
        
        logger.info(f"Waiting for services to start in container {container.id[:12]}...")
        
        # 首先等待supervisord启动
        supervisord_ready = False
        while time.time() - start_time < 30:  # 30秒等待supervisord
            try:
                result = container.exec_run("pgrep supervisord", workdir="/")
                if result.exit_code == 0:
                    logger.info("Supervisord is running")
                    supervisord_ready = True
                    break
            except Exception as e:
                logger.debug(f"Supervisord check failed: {e}")
            await asyncio.sleep(2)
        
        if not supervisord_ready:
            logger.warning("Supervisord may not be running properly")
        
        # 等待各个服务启动
        services_to_check = {
            'vnc': 5901,
            'novnc': 6080,
            'file_server': 8080,
            'browser_api': 7788
        }
        
        services_ready = {}
        
        while time.time() - start_time < timeout:
            all_ready = True
            
            for service, port in services_to_check.items():
                if service not in services_ready:
                    try:
                        # 检查端口是否可用
                        result = container.exec_run(f"nc -z localhost {port}", workdir="/")
                        if result.exit_code == 0:
                            logger.info(f"{service} service is ready on port {port}")
                            services_ready[service] = True
                        else:
                            all_ready = False
                    except Exception as e:
                        logger.debug(f"{service} service check failed: {e}")
                        all_ready = False
            
            if all_ready:
                logger.info("All services are ready")
                break
                
            await asyncio.sleep(3)
        else:
            ready_services = list(services_ready.keys())
            missing_services = [s for s in services_to_check.keys() if s not in ready_services]
            logger.warning(f"Timeout waiting for services. Ready: {ready_services}, Missing: {missing_services}")
        
        # 额外等待确保服务稳定
        await asyncio.sleep(5)
        logger.info("Service startup process completed")

# 全局管理器实例
_sandbox_manager = None

def get_sandbox_manager() -> LocalSandboxManager:
    """获取全局沙箱管理器实例"""
    global _sandbox_manager
    if _sandbox_manager is None:
        _sandbox_manager = LocalSandboxManager()
    return _sandbox_manager

# 异步清理任务
async def start_cleanup_task():
    """启动定期清理任务"""
    manager = get_sandbox_manager()
    
    while True:
        try:
            await manager.cleanup_expired_sandboxes()
        except Exception as e:
            logger.error(f"Cleanup task failed: {e}")
        
        # 每小时执行一次清理
        await asyncio.sleep(3600)

if __name__ == "__main__":
    # 测试代码
    async def test():
        manager = LocalSandboxManager()
        
        config = SandboxConfig(
            project_id="test-project-001",
            vnc_password="testpass"
        )
        
        try:
            # 创建沙箱
            container_id = await manager.create_sandbox(config)
            print(f"Created sandbox: {container_id}")
            
            # 获取沙箱信息
            info = await manager.get_sandbox("test-project-001")
            print(f"Sandbox info: {json.dumps(info, indent=2, default=str)}")
            
            # 列出所有沙箱
            sandboxes = await manager.list_sandboxes()
            print(f"All sandboxes: {json.dumps(sandboxes, indent=2, default=str)}")
            
        except Exception as e:
            print(f"Test failed: {e}")
        finally:
            # 清理
            try:
                await manager.delete_sandbox("test-project-001")
                print("Cleaned up test sandbox")
            except:
                pass
    
    asyncio.run(test())