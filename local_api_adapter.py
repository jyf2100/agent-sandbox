#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地API适配器
提供与原Daytona SDK兼容的接口，实现无缝替换
"""

import asyncio
import json
import logging
import os
import aiohttp
from typing import Dict, List, Optional, Any
from datetime import datetime
try:
    from .local_sandbox_manager import LocalSandboxManager, SandboxConfig, get_sandbox_manager
except ImportError:
    from local_sandbox_manager import LocalSandboxManager, SandboxConfig, get_sandbox_manager

logger = logging.getLogger(__name__)

class LocalWorkspace:
    """本地工作空间类，模拟Daytona Workspace"""
    
    def __init__(self, project_id: str, sandbox_info: Dict[str, Any]):
        self.id = project_id
        self.name = f"workspace-{project_id}"
        self.project_id = project_id
        self.status = sandbox_info.get('status', 'unknown')
        self.created_at = sandbox_info.get('created_at')
        self.urls = sandbox_info.get('urls', {})
        self.ports = sandbox_info.get('ports', {})
        self._sandbox_info = sandbox_info
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'id': self.id,
            'name': self.name,
            'project_id': self.project_id,
            'status': self.status,
            'created_at': self.created_at,
            'urls': self.urls,
            'ports': self.ports
        }

class LocalApiAdapter:
    """本地API适配器，提供与Daytona SDK兼容的接口"""
    
    def __init__(self):
        self.sandbox_manager = get_sandbox_manager()
        self._workspaces_cache = {}
    
    async def create_workspace(self, project_id: str, **kwargs) -> LocalWorkspace:
        """
        创建工作空间
        
        Args:
            project_id: 项目ID
            **kwargs: 其他配置参数
            
        Returns:
            LocalWorkspace实例
        """
        config = SandboxConfig(
            project_id=project_id,
            vnc_password=kwargs.get('vnc_password', 'vncpassword'),
            resolution=kwargs.get('resolution', '1024x768x24'),
            cpu_limit=kwargs.get('cpu_limit', 2),
            memory_limit=kwargs.get('memory_limit', '4g'),
            auto_stop_hours=kwargs.get('auto_stop_hours', 24)
        )
        
        try:
            container_id = await self.sandbox_manager.create_sandbox(config)
            sandbox_info = await self.sandbox_manager.get_sandbox(project_id)
            
            workspace = LocalWorkspace(project_id, sandbox_info)
            self._workspaces_cache[project_id] = workspace
            
            logger.info(f"Created workspace for project {project_id}")
            return workspace
            
        except Exception as e:
            logger.error(f"Failed to create workspace for project {project_id}: {e}")
            raise
    
    async def get_workspace(self, project_id: str) -> Optional[LocalWorkspace]:
        """
        获取工作空间
        
        Args:
            project_id: 项目ID
            
        Returns:
            LocalWorkspace实例或None
        """
        try:
            sandbox_info = await self.sandbox_manager.get_sandbox(project_id)
            workspace = LocalWorkspace(project_id, sandbox_info)
            self._workspaces_cache[project_id] = workspace
            return workspace
        except ValueError:
            return None
        except Exception as e:
            logger.error(f"Failed to get workspace for project {project_id}: {e}")
            return None
    
    async def start_workspace(self, project_id: str) -> bool:
        """
        启动工作空间
        
        Args:
            project_id: 项目ID
            
        Returns:
            是否成功启动
        """
        try:
            await self.sandbox_manager.start_sandbox(project_id)
            
            # 更新缓存
            if project_id in self._workspaces_cache:
                sandbox_info = await self.sandbox_manager.get_sandbox(project_id)
                self._workspaces_cache[project_id] = LocalWorkspace(project_id, sandbox_info)
            
            logger.info(f"Started workspace for project {project_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to start workspace for project {project_id}: {e}")
            return False
    
    async def stop_workspace(self, project_id: str) -> bool:
        """
        停止工作空间
        
        Args:
            project_id: 项目ID
            
        Returns:
            是否成功停止
        """
        try:
            await self.sandbox_manager.stop_sandbox(project_id)
            
            # 更新缓存
            if project_id in self._workspaces_cache:
                sandbox_info = await self.sandbox_manager.get_sandbox(project_id)
                self._workspaces_cache[project_id] = LocalWorkspace(project_id, sandbox_info)
            
            logger.info(f"Stopped workspace for project {project_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to stop workspace for project {project_id}: {e}")
            return False
    
    async def delete_workspace(self, project_id: str) -> bool:
        """
        删除工作空间
        
        Args:
            project_id: 项目ID
            
        Returns:
            是否成功删除
        """
        try:
            await self.sandbox_manager.delete_sandbox(project_id)
            
            # 从缓存中移除
            if project_id in self._workspaces_cache:
                del self._workspaces_cache[project_id]
            
            logger.info(f"Deleted workspace for project {project_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete workspace for project {project_id}: {e}")
            return False
    
    async def list_workspaces(self) -> List[LocalWorkspace]:
        """
        列出所有工作空间
        
        Returns:
            工作空间列表
        """
        try:
            sandboxes = await self.sandbox_manager.list_sandboxes()
            workspaces = []
            
            for project_id, sandbox_info in sandboxes.items():
                workspace = LocalWorkspace(project_id, sandbox_info)
                self._workspaces_cache[project_id] = workspace
                workspaces.append(workspace)
            
            return workspaces
        except Exception as e:
            logger.error(f"Failed to list workspaces: {e}")
            return []
    
    async def get_or_create_workspace(self, project_id: str, **kwargs) -> LocalWorkspace:
        """
        获取或创建工作空间
        
        Args:
            project_id: 项目ID
            **kwargs: 创建参数
            
        Returns:
            LocalWorkspace实例
        """
        workspace = await self.get_workspace(project_id)
        if workspace is None:
            workspace = await self.create_workspace(project_id, **kwargs)
        
        # 确保工作空间正在运行
        if workspace.status != 'running':
            await self.start_workspace(project_id)
            # 重新获取状态
            workspace = await self.get_workspace(project_id)
        
        return workspace
    
    async def execute_command(self, project_id: str, command: str, workdir: str = "/workspace") -> Dict[str, Any]:
        """
        在工作空间中执行命令
        
        Args:
            project_id: 项目ID
            command: 要执行的命令
            workdir: 工作目录
            
        Returns:
            执行结果
        """
        try:
            sandbox_info = await self.sandbox_manager.get_sandbox(project_id)
            container = self.sandbox_manager.containers[project_id]['container']
            
            # 确保容器正在运行
            container.reload()
            if container.status != 'running':
                logger.warning(f"Container {container.id} is not running, status: {container.status}")
                return {
                    'exit_code': -1,
                    'stdout': '',
                    'stderr': f'Container is not running (status: {container.status})',
                    'success': False
                }
            
            # 在容器中执行命令
            result = container.exec_run(
                command,
                workdir=workdir,
                stdout=True,
                stderr=True,
                stream=False,
                environment={'DISPLAY': ':99', 'PYTHONUNBUFFERED': '1'}
            )
            
            stdout = result.output.decode('utf-8', errors='ignore') if result.output else ''
            
            return {
                'exit_code': result.exit_code,
                'stdout': stdout,
                'stderr': '',
                'success': result.exit_code == 0
            }
            
        except Exception as e:
            logger.error(f"Failed to execute command in workspace {project_id}: {e}")
            return {
                'exit_code': -1,
                'stdout': '',
                'stderr': str(e),
                'success': False
            }
    
    async def upload_file(self, project_id: str, local_path: str, remote_path: str) -> bool:
        """
        上传文件到工作空间
        
        Args:
            project_id: 项目ID
            local_path: 本地文件路径
            remote_path: 远程文件路径
            
        Returns:
            是否成功上传
        """
        try:
            sandbox_info = await self.sandbox_manager.get_sandbox(project_id)
            container = self.sandbox_manager.containers[project_id]['container']
            
            # 读取本地文件
            with open(local_path, 'rb') as f:
                file_data = f.read()
            
            # 创建tar文件并上传
            import tarfile
            import io
            
            tar_buffer = io.BytesIO()
            with tarfile.open(fileobj=tar_buffer, mode='w') as tar:
                tarinfo = tarfile.TarInfo(name=os.path.basename(remote_path))
                tarinfo.size = len(file_data)
                tar.addfile(tarinfo, io.BytesIO(file_data))
            
            tar_buffer.seek(0)
            
            # 上传到容器
            remote_dir = os.path.dirname(remote_path)
            container.put_archive(remote_dir, tar_buffer.getvalue())
            
            logger.info(f"Uploaded file {local_path} to {remote_path} in workspace {project_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to upload file to workspace {project_id}: {e}")
            return False
    
    async def download_file(self, project_id: str, remote_path: str, local_path: str) -> bool:
        """
        从工作空间下载文件
        
        Args:
            project_id: 项目ID
            remote_path: 远程文件路径
            local_path: 本地文件路径
            
        Returns:
            是否成功下载
        """
        try:
            sandbox_info = await self.sandbox_manager.get_sandbox(project_id)
            container = self.sandbox_manager.containers[project_id]['container']
            
            # 从容器下载文件
            import tarfile
            import io
            
            archive_data, _ = container.get_archive(remote_path)
            
            # 解析tar数据
            archive_bytes = b''.join(archive_data)
            tar_buffer = io.BytesIO(archive_bytes)
            
            with tarfile.open(fileobj=tar_buffer, mode='r') as tar:
                member = tar.getmembers()[0]
                file_data = tar.extractfile(member).read()
            
            # 写入本地文件
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, 'wb') as f:
                f.write(file_data)
            
            logger.info(f"Downloaded file {remote_path} from workspace {project_id} to {local_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to download file from workspace {project_id}: {e}")
            return False
    
    async def list_files(self, project_id: str, path: str = "/workspace") -> List[Dict[str, Any]]:
        """
        列出工作空间中的文件
        
        Args:
            project_id: 项目ID
            path: 目录路径
            
        Returns:
            文件列表
        """
        try:
            # 首先确保目录存在
            mkdir_result = await self.execute_command(
                project_id,
                f"mkdir -p {path}",
                workdir="/"
            )
            
            # 列出文件和目录
            result = await self.execute_command(
                project_id,
                f"ls -la {path}",
                workdir="/"
            )
            
            if not result['success']:
                logger.warning(f"Failed to list files in {path}: {result['stderr']}")
                return []
            
            files = []
            lines = result['stdout'].strip().split('\n')
            
            for line in lines:
                line = line.strip()
                if not line or line.startswith('total'):
                    continue
                    
                parts = line.split()
                if len(parts) >= 9:
                    permissions = parts[0]
                    size = parts[4]
                    modified = ' '.join(parts[5:8])
                    filename = ' '.join(parts[8:])
                    
                    # 跳过 . 和 .. 目录
                    if filename in ['.', '..']:
                        continue
                    
                    file_type = 'directory' if permissions.startswith('d') else 'file'
                    full_path = os.path.join(path, filename) if path != '/' else f'/{filename}'
                    
                    files.append({
                        'name': filename,
                        'path': full_path,
                        'size': size,
                        'modified': modified,
                        'permissions': permissions,
                        'type': file_type
                    })
            
            logger.info(f"Listed {len(files)} files/directories in {path}")
            return files
            
        except Exception as e:
            logger.error(f"Failed to list files in workspace {project_id}: {e}")
            return []
    
    async def create_directory(self, project_id: str, path: str) -> bool:
        """
        在工作空间中创建目录
        
        Args:
            project_id: 项目ID
            path: 目录路径
            
        Returns:
            是否成功创建
        """
        try:
            result = await self.execute_command(
                project_id,
                f"mkdir -p {path}",
                workdir="/"
            )
            
            return result['success']
            
        except Exception as e:
            logger.error(f"Failed to create directory in workspace {project_id}: {e}")
            return False
    
    async def get_workspace_info(self, project_id: str) -> Dict[str, Any]:
        """
        获取工作空间详细信息
        
        Args:
            project_id: 项目ID
            
        Returns:
            工作空间信息
        """
        try:
            sandbox_info = await self.sandbox_manager.get_sandbox(project_id)
            
            # 获取系统信息
            system_info = await self.execute_command(project_id, "uname -a && df -h /workspace")
            
            return {
                'project_id': project_id,
                'status': sandbox_info.get('status'),
                'created_at': sandbox_info.get('created_at'),
                'urls': sandbox_info.get('urls', {}),
                'ports': sandbox_info.get('ports', {}),
                'system_info': system_info.get('stdout', '') if system_info['success'] else '',
                'container_id': sandbox_info.get('id'),
                'config': sandbox_info.get('config', {})
            }
            
        except Exception as e:
            logger.error(f"Failed to get workspace info for project {project_id}: {e}")
            return {}
    
    async def health_check(self, project_id: str) -> Dict[str, Any]:
        """
        检查工作空间健康状态
        
        Args:
            project_id: 项目ID
            
        Returns:
            健康状态信息
        """
        try:
            workspace = await self.get_workspace(project_id)
            if not workspace:
                return {'healthy': False, 'reason': 'Workspace not found'}
            
            if workspace.status != 'running':
                return {'healthy': False, 'reason': f'Workspace status: {workspace.status}'}
            
            # 检查服务可用性
            services_status = {}
            
            # 检查VNC服务
            vnc_check = await self.execute_command(project_id, "nc -z localhost 5901")
            services_status['vnc'] = vnc_check['success']
            
            # 检查noVNC服务
            novnc_check = await self.execute_command(project_id, "nc -z localhost 6080")
            services_status['novnc'] = novnc_check['success']
            
            # 检查文件服务器
            file_server_check = await self.execute_command(project_id, "nc -z localhost 8080")
            services_status['file_server'] = file_server_check['success']
            
            # 检查浏览器API
            browser_api_check = await self.execute_command(project_id, "nc -z localhost 7788")
            services_status['browser_api'] = browser_api_check['success']
            
            all_healthy = all(services_status.values())
            
            return {
                'healthy': all_healthy,
                'services': services_status,
                'workspace_status': workspace.status,
                'urls': workspace.urls
            }
            
        except Exception as e:
            logger.error(f"Health check failed for workspace {project_id}: {e}")
            return {'healthy': False, 'reason': str(e)}

# 全局适配器实例
_api_adapter = None

def get_api_adapter() -> LocalApiAdapter:
    """获取全局API适配器实例"""
    global _api_adapter
    if _api_adapter is None:
        _api_adapter = LocalApiAdapter()
    return _api_adapter

# 兼容性函数，模拟Daytona SDK的主要接口
async def create_workspace(project_id: str, **kwargs) -> LocalWorkspace:
    """创建工作空间（兼容接口）"""
    adapter = get_api_adapter()
    return await adapter.create_workspace(project_id, **kwargs)

async def get_workspace(project_id: str) -> Optional[LocalWorkspace]:
    """获取工作空间（兼容接口）"""
    adapter = get_api_adapter()
    return await adapter.get_workspace(project_id)

async def start_workspace(project_id: str) -> bool:
    """启动工作空间（兼容接口）"""
    adapter = get_api_adapter()
    return await adapter.start_workspace(project_id)

async def stop_workspace(project_id: str) -> bool:
    """停止工作空间（兼容接口）"""
    adapter = get_api_adapter()
    return await adapter.stop_workspace(project_id)

async def delete_workspace(project_id: str) -> bool:
    """删除工作空间（兼容接口）"""
    adapter = get_api_adapter()
    return await adapter.delete_workspace(project_id)

async def list_workspaces() -> List[LocalWorkspace]:
    """列出工作空间（兼容接口）"""
    adapter = get_api_adapter()
    return await adapter.list_workspaces()

if __name__ == "__main__":
    # 测试代码
    async def test():
        adapter = LocalApiAdapter()
        
        try:
            # 创建工作空间
            workspace = await adapter.create_workspace("test-project-002")
            print(f"Created workspace: {workspace.to_dict()}")
            
            # 执行命令
            result = await adapter.execute_command("test-project-002", "ls -la /workspace")
            print(f"Command result: {result}")
            
            # 健康检查
            health = await adapter.health_check("test-project-002")
            print(f"Health check: {health}")
            
            # 获取工作空间信息
            info = await adapter.get_workspace_info("test-project-002")
            print(f"Workspace info: {json.dumps(info, indent=2, default=str)}")
            
        except Exception as e:
            print(f"Test failed: {e}")
        finally:
            # 清理
            try:
                await adapter.delete_workspace("test-project-002")
                print("Cleaned up test workspace")
            except:
                pass
    
    asyncio.run(test())