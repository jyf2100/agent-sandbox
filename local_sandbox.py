#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地化沙箱实现
替代原有的Daytona SDK依赖，使用本地Docker容器管理
"""

import asyncio
import logging
import os
from typing import Dict, Optional, Any
from datetime import datetime

try:
    from .local_api_adapter import LocalApiAdapter, LocalWorkspace, get_api_adapter
    from .local_sandbox_manager import SandboxConfig
except ImportError:
    from local_api_adapter import LocalApiAdapter, LocalWorkspace, get_api_adapter
    from local_sandbox_manager import SandboxConfig

logger = logging.getLogger(__name__)

class LocalSandbox:
    """本地沙箱类，替代原有的Daytona Sandbox"""
    
    def __init__(self, project_id: str):
        """
        初始化本地沙箱
        
        Args:
            project_id: 项目ID
        """
        self.project_id = project_id
        self.api_adapter = get_api_adapter()
        self._workspace: Optional[LocalWorkspace] = None
        self._session_started = False
    
    async def get_or_start_sandbox(self, **kwargs) -> 'LocalSandbox':
        """
        获取或启动沙箱
        
        Args:
            **kwargs: 沙箱配置参数
            
        Returns:
            LocalSandbox实例
        """
        try:
            # 尝试获取现有工作空间
            self._workspace = await self.api_adapter.get_workspace(self.project_id)
            
            if self._workspace is None:
                # 创建新的工作空间
                logger.info(f"Creating new workspace for project {self.project_id}")
                self._workspace = await self.api_adapter.create_workspace(
                    self.project_id,
                    **kwargs
                )
            else:
                # 确保工作空间正在运行
                if self._workspace.status != 'running':
                    logger.info(f"Starting existing workspace for project {self.project_id}")
                    await self.api_adapter.start_workspace(self.project_id)
                    # 重新获取状态
                    self._workspace = await self.api_adapter.get_workspace(self.project_id)
            
            logger.info(f"Sandbox ready for project {self.project_id}")
            return self
            
        except Exception as e:
            logger.error(f"Failed to get or start sandbox for project {self.project_id}: {e}")
            raise
    
    async def start_supervisord_session(self) -> bool:
        """
        启动supervisord会话（兼容接口）
        
        在本地沙箱中，supervisord已在容器启动时自动运行
        这里只是检查其状态
        
        Returns:
            bool: 是否成功启动
        """
        try:
            if self._session_started:
                return True
            
            # 检查工作空间是否可用
            if not self._workspace:
                await self.get_or_start_sandbox()
            
            # 等待一段时间让supervisord完全启动
            await asyncio.sleep(2)
            
            # 检查supervisord进程是否运行
            result = await self.api_adapter.execute_command(
                self.project_id,
                "ps aux | grep supervisord | grep -v grep",
                workdir="/"
            )
            
            if result['success'] and 'supervisord' in result['stdout']:
                logger.info(f"Supervisord process found for project {self.project_id}")
                
                # 再检查supervisorctl状态
                status_result = await self.api_adapter.execute_command(
                    self.project_id,
                    "supervisorctl status",
                    workdir="/"
                )
                
                if status_result['success'] or 'RUNNING' in status_result['stdout']:
                    self._session_started = True
                    logger.info(f"Supervisord is running for project {self.project_id}")
                    return True
                else:
                    logger.warning(f"Supervisorctl status check failed: {status_result['stdout']}")
                    # 即使supervisorctl失败，如果进程存在也认为成功
                    self._session_started = True
                    return True
            else:
                logger.warning(f"Supervisord process not found for project {self.project_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to check supervisord status for project {self.project_id}: {e}")
            return False
    
    async def execute_command(self, command: str, workdir: str = "/workspace") -> Dict[str, Any]:
        """
        在沙箱中执行命令
        
        Args:
            command: 要执行的命令
            workdir: 工作目录
            
        Returns:
            执行结果
        """
        try:
            if not self._workspace:
                await self.get_or_start_sandbox()
            
            return await self.api_adapter.execute_command(
                self.project_id,
                command,
                workdir
            )
            
        except Exception as e:
            logger.error(f"Failed to execute command in sandbox {self.project_id}: {e}")
            return {
                'exit_code': -1,
                'stdout': '',
                'stderr': str(e),
                'success': False
            }
    
    async def upload_file(self, local_path: str, remote_path: str) -> bool:
        """
        上传文件到沙箱
        
        Args:
            local_path: 本地文件路径
            remote_path: 远程文件路径
            
        Returns:
            是否成功上传
        """
        try:
            if not self._workspace:
                await self.get_or_start_sandbox()
            
            return await self.api_adapter.upload_file(
                self.project_id,
                local_path,
                remote_path
            )
            
        except Exception as e:
            logger.error(f"Failed to upload file to sandbox {self.project_id}: {e}")
            return False
    
    async def download_file(self, remote_path: str, local_path: str) -> bool:
        """
        从沙箱下载文件
        
        Args:
            remote_path: 远程文件路径
            local_path: 本地文件路径
            
        Returns:
            是否成功下载
        """
        try:
            if not self._workspace:
                await self.get_or_start_sandbox()
            
            return await self.api_adapter.download_file(
                self.project_id,
                remote_path,
                local_path
            )
            
        except Exception as e:
            logger.error(f"Failed to download file from sandbox {self.project_id}: {e}")
            return False
    
    async def list_files(self, path: str = "/workspace") -> list:
        """
        列出沙箱中的文件
        
        Args:
            path: 目录路径
            
        Returns:
            文件列表
        """
        try:
            if not self._workspace:
                await self.get_or_start_sandbox()
            
            return await self.api_adapter.list_files(self.project_id, path)
            
        except Exception as e:
            logger.error(f"Failed to list files in sandbox {self.project_id}: {e}")
            return []
    
    async def create_directory(self, path: str) -> bool:
        """
        在沙箱中创建目录
        
        Args:
            path: 目录路径
            
        Returns:
            是否成功创建
        """
        try:
            if not self._workspace:
                await self.get_or_start_sandbox()
            
            return await self.api_adapter.create_directory(self.project_id, path)
            
        except Exception as e:
            logger.error(f"Failed to create directory in sandbox {self.project_id}: {e}")
            return False
    
    async def get_workspace_info(self) -> Dict[str, Any]:
        """
        获取工作空间信息
        
        Returns:
            工作空间信息
        """
        try:
            if not self._workspace:
                await self.get_or_start_sandbox()
            
            return await self.api_adapter.get_workspace_info(self.project_id)
            
        except Exception as e:
            logger.error(f"Failed to get workspace info for sandbox {self.project_id}: {e}")
            return {}
    
    async def health_check(self) -> Dict[str, Any]:
        """
        检查沙箱健康状态
        
        Returns:
            健康状态信息
        """
        try:
            if not self._workspace:
                return {'healthy': False, 'reason': 'Workspace not initialized'}
            
            return await self.api_adapter.health_check(self.project_id)
            
        except Exception as e:
            logger.error(f"Health check failed for sandbox {self.project_id}: {e}")
            return {'healthy': False, 'reason': str(e)}
    
    async def stop(self) -> bool:
        """
        停止沙箱
        
        Returns:
            是否成功停止
        """
        try:
            result = await self.api_adapter.stop_workspace(self.project_id)
            if result:
                self._session_started = False
                logger.info(f"Sandbox stopped for project {self.project_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to stop sandbox {self.project_id}: {e}")
            return False
    
    async def delete(self) -> bool:
        """
        删除沙箱
        
        Returns:
            是否成功删除
        """
        try:
            result = await self.api_adapter.delete_workspace(self.project_id)
            if result:
                self._workspace = None
                self._session_started = False
                logger.info(f"Sandbox deleted for project {self.project_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to delete sandbox {self.project_id}: {e}")
            return False
    
    @property
    def workspace(self) -> Optional[LocalWorkspace]:
        """获取工作空间对象"""
        return self._workspace
    
    @property
    def is_running(self) -> bool:
        """检查沙箱是否正在运行"""
        return self._workspace is not None and self._workspace.status == 'running'
    
    @property
    def urls(self) -> Dict[str, str]:
        """获取服务访问URL"""
        if self._workspace:
            return self._workspace.urls
        return {}
    
    def __str__(self) -> str:
        return f"LocalSandbox(project_id={self.project_id}, running={self.is_running})"
    
    def __repr__(self) -> str:
        return self.__str__()

# 兼容性函数
async def get_or_start_sandbox(project_id: str, **kwargs) -> LocalSandbox:
    """
    获取或启动沙箱（兼容接口）
    
    Args:
        project_id: 项目ID
        **kwargs: 沙箱配置参数
        
    Returns:
        LocalSandbox实例
    """
    sandbox = LocalSandbox(project_id)
    return await sandbox.get_or_start_sandbox(**kwargs)

async def create_sandbox(project_id: str, **kwargs) -> LocalSandbox:
    """
    创建沙箱（兼容接口）
    
    Args:
        project_id: 项目ID
        **kwargs: 沙箱配置参数
        
    Returns:
        LocalSandbox实例
    """
    return await get_or_start_sandbox(project_id, **kwargs)

async def list_sandboxes() -> Dict[str, LocalSandbox]:
    """
    列出所有沙箱（兼容接口）
    
    Returns:
        沙箱字典
    """
    try:
        adapter = get_api_adapter()
        workspaces = await adapter.list_workspaces()
        
        sandboxes = {}
        for workspace in workspaces:
            sandbox = LocalSandbox(workspace.project_id)
            sandbox._workspace = workspace
            sandboxes[workspace.project_id] = sandbox
        
        return sandboxes
        
    except Exception as e:
        logger.error(f"Failed to list sandboxes: {e}")
        return {}

if __name__ == "__main__":
    # 测试代码
    async def test():
        sandbox = LocalSandbox("test-project-003")
        
        try:
            # 启动沙箱
            await sandbox.get_or_start_sandbox(
                vnc_password="testpass",
                resolution="1280x720x24"
            )
            
            print(f"Sandbox: {sandbox}")
            print(f"URLs: {sandbox.urls}")
            
            # 启动supervisord会话
            session_ok = await sandbox.start_supervisord_session()
            print(f"Supervisord session: {session_ok}")
            
            # 执行命令
            result = await sandbox.execute_command("ls -la /workspace")
            print(f"Command result: {result}")
            
            # 健康检查
            health = await sandbox.health_check()
            print(f"Health check: {health}")
            
            # 获取工作空间信息
            info = await sandbox.get_workspace_info()
            print(f"Workspace info: {info}")
            
        except Exception as e:
            print(f"Test failed: {e}")
        finally:
            # 清理
            try:
                await sandbox.delete()
                print("Cleaned up test sandbox")
            except:
                pass
    
    asyncio.run(test())