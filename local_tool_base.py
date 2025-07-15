#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地化沙箱工具基类
替代原有的SandboxToolsBase，使用本地Docker容器管理
"""

import asyncio
import logging
import os
import re
from abc import ABC, abstractmethod
from typing import Dict, Optional, Any, List
from pathlib import Path

try:
    from .local_sandbox import LocalSandbox, get_or_start_sandbox
except ImportError:
    from local_sandbox import LocalSandbox, get_or_start_sandbox

logger = logging.getLogger(__name__)

class LocalSandboxToolsBase(ABC):
    """本地沙箱工具基类"""
    
    def __init__(self, project_id: str):
        """
        初始化工具基类
        
        Args:
            project_id: 项目ID
        """
        self.project_id = project_id
        self._sandbox: Optional[LocalSandbox] = None
        self._initialized = False
    
    async def get_or_start_sandbox(self, **kwargs) -> LocalSandbox:
        """
        获取或启动沙箱
        
        Args:
            **kwargs: 沙箱配置参数
            
        Returns:
            LocalSandbox实例
        """
        try:
            if self._sandbox is None or not self._sandbox.is_running:
                logger.info(f"Initializing sandbox for project {self.project_id}")
                self._sandbox = await get_or_start_sandbox(self.project_id, **kwargs)
                
                # 确保supervisord会话启动
                session_ok = await self._sandbox.start_supervisord_session()
                if not session_ok:
                    logger.warning(f"Supervisord session may not be ready for project {self.project_id}")
                
                self._initialized = True
                logger.info(f"Sandbox initialized for project {self.project_id}")
            
            return self._sandbox
            
        except Exception as e:
            logger.error(f"Failed to get or start sandbox for project {self.project_id}: {e}")
            raise
    
    def clean_path(self, path: str) -> str:
        """
        清理路径，确保安全性
        
        Args:
            path: 原始路径
            
        Returns:
            清理后的路径
        """
        if not path:
            return "/workspace"
        
        # 移除危险字符
        path = re.sub(r'[<>:"|?*]', '', path)
        
        # 规范化路径
        path = os.path.normpath(path)
        
        # 确保路径在工作空间内
        if not path.startswith('/workspace'):
            if path.startswith('/'):
                path = '/workspace' + path
            else:
                path = '/workspace/' + path
        
        # 移除多余的斜杠
        path = re.sub(r'/+', '/', path)
        
        return path
    
    def validate_path(self, path: str) -> bool:
        """
        验证路径是否安全
        
        Args:
            path: 要验证的路径
            
        Returns:
            是否安全
        """
        if not path:
            return False
        
        # 检查路径遍历攻击
        if '..' in path or path.startswith('~'):
            return False
        
        # 检查是否在允许的工作空间内
        normalized_path = os.path.normpath(path)
        if not normalized_path.startswith('/workspace'):
            return False
        
        return True
    
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
            sandbox = await self.get_or_start_sandbox()
            
            # 清理工作目录路径
            workdir = self.clean_path(workdir)
            
            return await sandbox.execute_command(command, workdir)
            
        except Exception as e:
            logger.error(f"Failed to execute command '{command}' in {self.project_id}: {e}")
            return {
                'exit_code': -1,
                'stdout': '',
                'stderr': str(e),
                'success': False
            }
    
    async def read_file(self, file_path: str) -> Optional[str]:
        """
        读取文件内容
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件内容或None
        """
        try:
            file_path = self.clean_path(file_path)
            
            if not self.validate_path(file_path):
                logger.error(f"Invalid file path: {file_path}")
                return None
            
            # 首先检查文件是否存在
            exists_result = await self.execute_command(f"test -f '{file_path}'")
            if not exists_result['success']:
                logger.warning(f"File does not exist: {file_path}")
                return None
            
            # 读取文件内容
            result = await self.execute_command(f"cat '{file_path}'")
            
            if result['success']:
                return result['stdout']
            else:
                logger.error(f"Failed to read file {file_path}: {result.get('stderr', 'Unknown error')}")
                return None
                
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return None
    
    async def write_file(self, file_path: str, content: str) -> bool:
        """
        写入文件内容
        
        Args:
            file_path: 文件路径
            content: 文件内容
            
        Returns:
            是否成功写入
        """
        try:
            file_path = self.clean_path(file_path)
            
            if not self.validate_path(file_path):
                logger.error(f"Invalid file path: {file_path}")
                return False
            
            # 确保目录存在
            dir_path = os.path.dirname(file_path)
            await self.execute_command(f"mkdir -p '{dir_path}'")
            
            # 转义内容中的单引号
            escaped_content = content.replace("'", "'\"'\"'")
            
            result = await self.execute_command(
                f"echo '{escaped_content}' > '{file_path}'"
            )
            
            return result['success']
            
        except Exception as e:
            logger.error(f"Error writing file {file_path}: {e}")
            return False
    
    async def list_files(self, directory: str = "/workspace") -> List[Dict[str, Any]]:
        """
        列出目录中的文件
        
        Args:
            directory: 目录路径
            
        Returns:
            文件列表
        """
        try:
            directory = self.clean_path(directory)
            
            if not self.validate_path(directory):
                logger.error(f"Invalid directory path: {directory}")
                return []
            
            sandbox = await self.get_or_start_sandbox()
            return await sandbox.list_files(directory)
            
        except Exception as e:
            logger.error(f"Error listing files in {directory}: {e}")
            return []
    
    async def create_directory(self, directory: str) -> bool:
        """
        创建目录
        
        Args:
            directory: 目录路径
            
        Returns:
            是否成功创建
        """
        try:
            directory = self.clean_path(directory)
            
            if not self.validate_path(directory):
                logger.error(f"Invalid directory path: {directory}")
                return False
            
            sandbox = await self.get_or_start_sandbox()
            return await sandbox.create_directory(directory)
            
        except Exception as e:
            logger.error(f"Error creating directory {directory}: {e}")
            return False
    
    async def file_exists(self, file_path: str) -> bool:
        """
        检查文件是否存在
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件是否存在
        """
        try:
            file_path = self.clean_path(file_path)
            
            if not self.validate_path(file_path):
                return False
            
            result = await self.execute_command(f"test -f '{file_path}'")
            return result['exit_code'] == 0
            
        except Exception as e:
            logger.error(f"Error checking file existence {file_path}: {e}")
            return False
    
    async def directory_exists(self, directory: str) -> bool:
        """
        检查目录是否存在
        
        Args:
            directory: 目录路径
            
        Returns:
            目录是否存在
        """
        try:
            directory = self.clean_path(directory)
            
            if not self.validate_path(directory):
                return False
            
            result = await self.execute_command(f"test -d '{directory}'")
            return result['exit_code'] == 0
            
        except Exception as e:
            logger.error(f"Error checking directory existence {directory}: {e}")
            return False
    
    async def delete_file(self, file_path: str) -> bool:
        """
        删除文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            是否成功删除
        """
        try:
            file_path = self.clean_path(file_path)
            
            if not self.validate_path(file_path):
                logger.error(f"Invalid file path: {file_path}")
                return False
            
            result = await self.execute_command(f"rm -f '{file_path}'")
            return result['success']
            
        except Exception as e:
            logger.error(f"Error deleting file {file_path}: {e}")
            return False
    
    async def delete_directory(self, directory: str) -> bool:
        """
        删除目录
        
        Args:
            directory: 目录路径
            
        Returns:
            是否成功删除
        """
        try:
            directory = self.clean_path(directory)
            
            if not self.validate_path(directory):
                logger.error(f"Invalid directory path: {directory}")
                return False
            
            # 防止删除工作空间根目录
            if directory == '/workspace':
                logger.error("Cannot delete workspace root directory")
                return False
            
            result = await self.execute_command(f"rm -rf '{directory}'")
            return result['success']
            
        except Exception as e:
            logger.error(f"Error deleting directory {directory}: {e}")
            return False
    
    async def get_file_info(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        获取文件信息
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件信息字典或None
        """
        try:
            file_path = self.clean_path(file_path)
            
            if not self.validate_path(file_path):
                return None
            
            result = await self.execute_command(
                f"stat -c '%n|%s|%Y|%A|%U|%G' '{file_path}' 2>/dev/null || echo 'NOT_FOUND'"
            )
            
            if result['success'] and result['stdout'].strip() != 'NOT_FOUND':
                parts = result['stdout'].strip().split('|')
                if len(parts) >= 6:
                    return {
                        'name': os.path.basename(parts[0]),
                        'path': parts[0],
                        'size': int(parts[1]),
                        'modified_time': int(parts[2]),
                        'permissions': parts[3],
                        'owner': parts[4],
                        'group': parts[5],
                        'is_file': True,
                        'is_directory': False
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting file info for {file_path}: {e}")
            return None
    
    async def health_check(self) -> Dict[str, Any]:
        """
        检查工具和沙箱的健康状态
        
        Returns:
            健康状态信息
        """
        try:
            if not self._sandbox:
                return {
                    'healthy': False,
                    'reason': 'Sandbox not initialized',
                    'tool_class': self.__class__.__name__,
                    'project_id': self.project_id
                }
            
            sandbox_health = await self._sandbox.health_check()
            
            return {
                'healthy': sandbox_health.get('healthy', False),
                'reason': sandbox_health.get('reason', 'Unknown'),
                'tool_class': self.__class__.__name__,
                'project_id': self.project_id,
                'sandbox_info': sandbox_health
            }
            
        except Exception as e:
            return {
                'healthy': False,
                'reason': str(e),
                'tool_class': self.__class__.__name__,
                'project_id': self.project_id
            }
    
    async def cleanup(self) -> bool:
        """
        清理资源
        
        Returns:
            是否成功清理
        """
        try:
            if self._sandbox:
                # 可选择停止或删除沙箱
                # await self._sandbox.stop()
                # await self._sandbox.delete()
                pass
            
            self._sandbox = None
            self._initialized = False
            
            logger.info(f"Cleaned up resources for project {self.project_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error during cleanup for project {self.project_id}: {e}")
            return False
    
    @property
    def sandbox(self) -> Optional[LocalSandbox]:
        """获取沙箱实例"""
        return self._sandbox
    
    @property
    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._initialized and self._sandbox is not None
    
    @property
    def workspace_urls(self) -> Dict[str, str]:
        """获取工作空间访问URL"""
        if self._sandbox:
            return self._sandbox.urls
        return {}
    
    @abstractmethod
    async def execute_tool(self, *args, **kwargs) -> Any:
        """
        执行具体的工具功能（子类需要实现）
        
        Args:
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            工具执行结果
        """
        pass
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__}(project_id={self.project_id}, initialized={self.is_initialized})"
    
    def __repr__(self) -> str:
        return self.__str__()

# 示例工具类
class ExampleLocalTool(LocalSandboxToolsBase):
    """示例本地工具类"""
    
    async def execute_tool(self, command: str = "echo 'Hello from local sandbox!'") -> Dict[str, Any]:
        """
        执行示例工具
        
        Args:
            command: 要执行的命令
            
        Returns:
            执行结果
        """
        try:
            # 确保沙箱已启动
            await self.get_or_start_sandbox()
            
            # 执行命令
            result = await self.execute_command(command)
            
            return {
                'success': result['success'],
                'output': result['stdout'],
                'error': result['stderr'],
                'tool': self.__class__.__name__
            }
            
        except Exception as e:
            logger.error(f"Example tool execution failed: {e}")
            return {
                'success': False,
                'output': '',
                'error': str(e),
                'tool': self.__class__.__name__
            }

if __name__ == "__main__":
    # 测试代码
    async def test():
        tool = ExampleLocalTool("test-project-004")
        
        try:
            # 测试工具执行
            result = await tool.execute_tool("ls -la /workspace")
            print(f"Tool result: {result}")
            
            # 测试文件操作
            write_ok = await tool.write_file("/workspace/test.txt", "Hello Local Sandbox!")
            print(f"Write file: {write_ok}")
            
            if write_ok:
                content = await tool.read_file("/workspace/test.txt")
                print(f"Read file: {content}")
            
            # 测试目录操作
            files = await tool.list_files("/workspace")
            print(f"Files: {files}")
            
            # 健康检查
            health = await tool.health_check()
            print(f"Health: {health}")
            
        except Exception as e:
            print(f"Test failed: {e}")
        finally:
            # 清理
            await tool.cleanup()
            print("Test completed")
    
    asyncio.run(test())