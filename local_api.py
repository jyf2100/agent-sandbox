#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地化沙箱API接口
替代原有的Daytona依赖，提供兼容的FastAPI接口
"""

import asyncio
import logging
import os
import urllib.parse
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from .local_sandbox_manager import LocalSandboxManager, SandboxConfig
from .local_api_adapter import get_api_adapter
from .local_sandbox import LocalSandbox

logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(prefix="/sandbox", tags=["sandbox"])

# 全局沙箱管理器
sandbox_manager = LocalSandboxManager()

# Pydantic模型
class CreateSandboxRequest(BaseModel):
    project_id: str
    vnc_password: Optional[str] = "suna123"
    resolution: Optional[str] = "1280x720x24"
    cpu_limit: Optional[str] = "2"
    memory_limit: Optional[str] = "4g"
    timezone: Optional[str] = "Asia/Shanghai"

class FileCreateRequest(BaseModel):
    path: str
    content: str = ""
    is_directory: bool = False

class FileUpdateRequest(BaseModel):
    content: str

class CommandRequest(BaseModel):
    command: str
    workdir: Optional[str] = "/workspace"

class SandboxResponse(BaseModel):
    project_id: str
    status: str
    container_id: Optional[str] = None
    urls: Dict[str, str] = {}
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class FileInfo(BaseModel):
    name: str
    path: str
    is_directory: bool
    size: Optional[int] = None
    modified_time: Optional[int] = None
    permissions: Optional[str] = None

class CommandResult(BaseModel):
    exit_code: int
    stdout: str
    stderr: str
    success: bool

# 依赖函数
async def get_sandbox_manager() -> LocalSandboxManager:
    """获取沙箱管理器"""
    return sandbox_manager

async def get_project_sandbox(project_id: str) -> LocalSandbox:
    """获取项目沙箱"""
    try:
        adapter = get_api_adapter()
        workspace = await adapter.get_workspace(project_id)
        
        if not workspace:
            raise HTTPException(
                status_code=404,
                detail=f"Sandbox not found for project {project_id}"
            )
        
        sandbox = LocalSandbox(project_id)
        sandbox._workspace = workspace
        return sandbox
        
    except Exception as e:
        logger.error(f"Failed to get sandbox for project {project_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get sandbox: {str(e)}"
        )

def clean_path(path: str) -> str:
    """清理和规范化路径"""
    if not path:
        return "/workspace"
    
    # URL解码
    path = urllib.parse.unquote(path)
    
    # 规范化路径
    path = os.path.normpath(path)
    
    # 确保路径在工作空间内
    if not path.startswith('/workspace'):
        if path.startswith('/'):
            path = '/workspace' + path
        else:
            path = '/workspace/' + path
    
    return path

def validate_path(path: str) -> bool:
    """验证路径安全性"""
    if not path:
        return False
    
    # 检查路径遍历攻击
    if '..' in path or '~' in path:
        return False
    
    # 检查是否在工作空间内
    normalized_path = os.path.normpath(path)
    if not normalized_path.startswith('/workspace'):
        return False
    
    return True

# API端点
@router.post("/create", response_model=SandboxResponse)
async def create_sandbox(
    request: CreateSandboxRequest,
    manager: LocalSandboxManager = Depends(get_sandbox_manager)
):
    """
    创建新的沙箱
    """
    try:
        config = SandboxConfig(
            project_id=request.project_id,
            vnc_password=request.vnc_password,
            resolution=request.resolution,
            cpu_limit=request.cpu_limit,
            memory_limit=request.memory_limit,
            timezone=request.timezone
        )
        
        sandbox_info = await manager.create_sandbox(config)
        
        return SandboxResponse(
            project_id=sandbox_info['project_id'],
            status=sandbox_info['status'],
            container_id=sandbox_info.get('container_id'),
            urls=sandbox_info.get('urls', {}),
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Failed to create sandbox: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create sandbox: {str(e)}"
        )

@router.get("/list", response_model=List[SandboxResponse])
async def list_sandboxes(
    manager: LocalSandboxManager = Depends(get_sandbox_manager)
):
    """
    列出所有沙箱
    """
    try:
        sandboxes = await manager.list_sandboxes()
        
        return [
            SandboxResponse(
                project_id=info['project_id'],
                status=info['status'],
                container_id=info.get('container_id'),
                urls=info.get('urls', {}),
                created_at=info.get('created_at'),
                updated_at=info.get('updated_at')
            )
            for info in sandboxes
        ]
        
    except Exception as e:
        logger.error(f"Failed to list sandboxes: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list sandboxes: {str(e)}"
        )

@router.get("/{project_id}", response_model=SandboxResponse)
async def get_sandbox(
    project_id: str,
    manager: LocalSandboxManager = Depends(get_sandbox_manager)
):
    """
    获取指定项目的沙箱信息
    """
    try:
        sandbox_info = await manager.get_sandbox(project_id)
        
        if not sandbox_info:
            raise HTTPException(
                status_code=404,
                detail=f"Sandbox not found for project {project_id}"
            )
        
        return SandboxResponse(
            project_id=sandbox_info['project_id'],
            status=sandbox_info['status'],
            container_id=sandbox_info.get('container_id'),
            urls=sandbox_info.get('urls', {}),
            created_at=sandbox_info.get('created_at'),
            updated_at=sandbox_info.get('updated_at')
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get sandbox {project_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get sandbox: {str(e)}"
        )

@router.post("/{project_id}/start")
async def start_sandbox(
    project_id: str,
    manager: LocalSandboxManager = Depends(get_sandbox_manager)
):
    """
    启动沙箱
    """
    try:
        success = await manager.start_sandbox(project_id)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to start sandbox for project {project_id}"
            )
        
        return {"message": f"Sandbox started for project {project_id}"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start sandbox {project_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start sandbox: {str(e)}"
        )

@router.post("/{project_id}/stop")
async def stop_sandbox(
    project_id: str,
    manager: LocalSandboxManager = Depends(get_sandbox_manager)
):
    """
    停止沙箱
    """
    try:
        success = await manager.stop_sandbox(project_id)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to stop sandbox for project {project_id}"
            )
        
        return {"message": f"Sandbox stopped for project {project_id}"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stop sandbox {project_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to stop sandbox: {str(e)}"
        )

@router.delete("/{project_id}")
async def delete_sandbox(
    project_id: str,
    manager: LocalSandboxManager = Depends(get_sandbox_manager)
):
    """
    删除沙箱
    """
    try:
        success = await manager.delete_sandbox(project_id)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete sandbox for project {project_id}"
            )
        
        return {"message": f"Sandbox deleted for project {project_id}"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete sandbox {project_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete sandbox: {str(e)}"
        )

@router.post("/{project_id}/execute", response_model=CommandResult)
async def execute_command(
    project_id: str,
    request: CommandRequest,
    sandbox: LocalSandbox = Depends(get_project_sandbox)
):
    """
    在沙箱中执行命令
    """
    try:
        workdir = clean_path(request.workdir)
        
        if not validate_path(workdir):
            raise HTTPException(
                status_code=400,
                detail="Invalid working directory path"
            )
        
        result = await sandbox.execute_command(request.command, workdir)
        
        return CommandResult(
            exit_code=result.get('exit_code', -1),
            stdout=result.get('stdout', ''),
            stderr=result.get('stderr', ''),
            success=result.get('success', False)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to execute command in sandbox {project_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to execute command: {str(e)}"
        )

@router.get("/{project_id}/files", response_model=List[FileInfo])
async def list_files(
    project_id: str,
    path: str = "/workspace",
    sandbox: LocalSandbox = Depends(get_project_sandbox)
):
    """
    列出沙箱中的文件
    """
    try:
        path = clean_path(path)
        
        if not validate_path(path):
            raise HTTPException(
                status_code=400,
                detail="Invalid path"
            )
        
        files = await sandbox.list_files(path)
        
        return [
            FileInfo(
                name=file_info.get('name', ''),
                path=file_info.get('path', ''),
                is_directory=file_info.get('is_directory', False),
                size=file_info.get('size'),
                modified_time=file_info.get('modified_time'),
                permissions=file_info.get('permissions')
            )
            for file_info in files
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list files in sandbox {project_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list files: {str(e)}"
        )

@router.post("/{project_id}/files")
async def create_file(
    project_id: str,
    request: FileCreateRequest,
    sandbox: LocalSandbox = Depends(get_project_sandbox)
):
    """
    在沙箱中创建文件或目录
    """
    try:
        path = clean_path(request.path)
        
        if not validate_path(path):
            raise HTTPException(
                status_code=400,
                detail="Invalid path"
            )
        
        if request.is_directory:
            success = await sandbox.create_directory(path)
            message = "Directory created successfully"
        else:
            # 确保父目录存在
            parent_dir = os.path.dirname(path)
            if parent_dir != path:  # 避免无限递归
                await sandbox.create_directory(parent_dir)
            
            # 创建文件
            result = await sandbox.execute_command(
                f"echo '{request.content.replace(chr(39), chr(39) + chr(34) + chr(39) + chr(34) + chr(39))}' > '{path}'"
            )
            success = result['success']
            message = "File created successfully"
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create {'directory' if request.is_directory else 'file'}"
            )
        
        return {"message": message, "path": path}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create file in sandbox {project_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create file: {str(e)}"
        )

@router.get("/{project_id}/files/content")
async def get_file_content(
    project_id: str,
    path: str,
    sandbox: LocalSandbox = Depends(get_project_sandbox)
):
    """
    获取文件内容
    """
    try:
        path = clean_path(path)
        
        if not validate_path(path):
            raise HTTPException(
                status_code=400,
                detail="Invalid path"
            )
        
        result = await sandbox.execute_command(f"cat '{path}'")
        
        if not result['success']:
            raise HTTPException(
                status_code=404,
                detail="File not found or cannot be read"
            )
        
        return {
            "content": result['stdout'],
            "path": path
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get file content in sandbox {project_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get file content: {str(e)}"
        )

@router.put("/{project_id}/files/content")
async def update_file_content(
    project_id: str,
    path: str,
    request: FileUpdateRequest,
    sandbox: LocalSandbox = Depends(get_project_sandbox)
):
    """
    更新文件内容
    """
    try:
        path = clean_path(path)
        
        if not validate_path(path):
            raise HTTPException(
                status_code=400,
                detail="Invalid path"
            )
        
        # 转义内容中的单引号
        escaped_content = request.content.replace("'", "'\"'\"'")
        
        result = await sandbox.execute_command(
            f"echo '{escaped_content}' > '{path}'"
        )
        
        if not result['success']:
            raise HTTPException(
                status_code=500,
                detail="Failed to update file content"
            )
        
        return {"message": "File updated successfully", "path": path}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update file content in sandbox {project_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update file content: {str(e)}"
        )

@router.delete("/{project_id}/files")
async def delete_file(
    project_id: str,
    path: str,
    sandbox: LocalSandbox = Depends(get_project_sandbox)
):
    """
    删除文件或目录
    """
    try:
        path = clean_path(path)
        
        if not validate_path(path):
            raise HTTPException(
                status_code=400,
                detail="Invalid path"
            )
        
        # 防止删除工作空间根目录
        if path == '/workspace':
            raise HTTPException(
                status_code=400,
                detail="Cannot delete workspace root directory"
            )
        
        result = await sandbox.execute_command(f"rm -rf '{path}'")
        
        if not result['success']:
            raise HTTPException(
                status_code=500,
                detail="Failed to delete file or directory"
            )
        
        return {"message": "File or directory deleted successfully", "path": path}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete file in sandbox {project_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete file: {str(e)}"
        )

@router.post("/{project_id}/upload")
async def upload_file(
    project_id: str,
    file: UploadFile = File(...),
    path: str = Form(...),
    sandbox: LocalSandbox = Depends(get_project_sandbox)
):
    """
    上传文件到沙箱
    """
    try:
        path = clean_path(path)
        
        if not validate_path(path):
            raise HTTPException(
                status_code=400,
                detail="Invalid path"
            )
        
        # 读取文件内容
        content = await file.read()
        
        # 如果路径是目录，使用原文件名
        if path.endswith('/'):
            path = os.path.join(path, file.filename)
        
        # 确保父目录存在
        parent_dir = os.path.dirname(path)
        if parent_dir != path:
            await sandbox.create_directory(parent_dir)
        
        # 写入文件（使用base64编码处理二进制文件）
        import base64
        encoded_content = base64.b64encode(content).decode('utf-8')
        
        result = await sandbox.execute_command(
            f"echo '{encoded_content}' | base64 -d > '{path}'"
        )
        
        if not result['success']:
            raise HTTPException(
                status_code=500,
                detail="Failed to upload file"
            )
        
        return {
            "message": "File uploaded successfully",
            "path": path,
            "filename": file.filename,
            "size": len(content)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload file to sandbox {project_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload file: {str(e)}"
        )

@router.get("/{project_id}/download")
async def download_file(
    project_id: str,
    path: str,
    sandbox: LocalSandbox = Depends(get_project_sandbox)
):
    """
    从沙箱下载文件
    """
    try:
        path = clean_path(path)
        
        if not validate_path(path):
            raise HTTPException(
                status_code=400,
                detail="Invalid path"
            )
        
        # 检查文件是否存在
        check_result = await sandbox.execute_command(f"test -f '{path}'")
        if check_result['exit_code'] != 0:
            raise HTTPException(
                status_code=404,
                detail="File not found"
            )
        
        # 使用base64编码读取文件内容
        result = await sandbox.execute_command(f"base64 '{path}'")
        
        if not result['success']:
            raise HTTPException(
                status_code=500,
                detail="Failed to read file"
            )
        
        # 解码文件内容
        import base64
        try:
            file_content = base64.b64decode(result['stdout'])
        except Exception:
            # 如果base64解码失败，可能是文本文件，直接读取
            text_result = await sandbox.execute_command(f"cat '{path}'")
            if text_result['success']:
                file_content = text_result['stdout'].encode('utf-8')
            else:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to read file content"
                )
        
        filename = os.path.basename(path)
        
        return JSONResponse(
            content={
                "filename": filename,
                "content": base64.b64encode(file_content).decode('utf-8'),
                "size": len(file_content)
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download file from sandbox {project_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to download file: {str(e)}"
        )

@router.get("/{project_id}/health")
async def health_check(
    project_id: str,
    sandbox: LocalSandbox = Depends(get_project_sandbox)
):
    """
    检查沙箱健康状态
    """
    try:
        health_info = await sandbox.health_check()
        return health_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Health check failed for sandbox {project_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Health check failed: {str(e)}"
        )

@router.get("/{project_id}/info")
async def get_workspace_info(
    project_id: str,
    sandbox: LocalSandbox = Depends(get_project_sandbox)
):
    """
    获取工作空间信息
    """
    try:
        info = await sandbox.get_workspace_info()
        return info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get workspace info for sandbox {project_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get workspace info: {str(e)}"
        )

# 清理过期沙箱的后台任务
async def cleanup_expired_sandboxes():
    """清理过期沙箱的后台任务"""
    while True:
        try:
            await sandbox_manager.cleanup_expired_sandboxes()
            await asyncio.sleep(300)  # 每5分钟清理一次
        except Exception as e:
            logger.error(f"Error during sandbox cleanup: {e}")
            await asyncio.sleep(60)  # 出错时等待1分钟再重试

# 启动清理任务
asyncio.create_task(cleanup_expired_sandboxes())

if __name__ == "__main__":
    # 测试代码
    import uvicorn
    from fastapi import FastAPI
    
    app = FastAPI(title="Local Sandbox API", version="1.0.0")
    app.include_router(router)
    
    uvicorn.run(app, host="0.0.0.0", port=8000)