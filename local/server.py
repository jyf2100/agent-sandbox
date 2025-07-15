#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地沙箱文件服务器
提供文件操作API接口
"""

import os
import shutil
import mimetypes
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# 配置
WORKSPACE_PATH = os.environ.get('WORKSPACE_PATH', '/workspace')
SERVER_PORT = int(os.environ.get('FILE_SERVER_PORT', '8080'))

# 确保工作目录存在
os.makedirs(WORKSPACE_PATH, exist_ok=True)

app = FastAPI(
    title="Suna Sandbox File Server",
    description="本地沙箱文件操作API",
    version="1.0.0"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 数据模型
class FileInfo(BaseModel):
    name: str
    path: str
    size: int
    type: str  # 'file' or 'directory'
    modified: str
    permissions: str
    mime_type: Optional[str] = None

class CreateFileRequest(BaseModel):
    path: str
    content: str = ""
    encoding: str = "utf-8"

class CreateDirectoryRequest(BaseModel):
    path: str

class MoveRequest(BaseModel):
    source: str
    destination: str

class CopyRequest(BaseModel):
    source: str
    destination: str

# 工具函数
def get_safe_path(path: str) -> str:
    """获取安全的文件路径，防止路径遍历攻击"""
    # 移除开头的斜杠
    if path.startswith('/'):
        path = path[1:]
    
    # 构建完整路径
    full_path = os.path.join(WORKSPACE_PATH, path)
    
    # 规范化路径
    normalized_path = os.path.normpath(full_path)
    
    # 确保路径在工作目录内
    if not normalized_path.startswith(WORKSPACE_PATH):
        raise HTTPException(status_code=400, detail="Invalid path: outside workspace")
    
    return normalized_path

def get_file_info(file_path: str) -> FileInfo:
    """获取文件信息"""
    stat = os.stat(file_path)
    is_dir = os.path.isdir(file_path)
    
    # 获取相对路径
    rel_path = os.path.relpath(file_path, WORKSPACE_PATH)
    if rel_path == '.':
        rel_path = '/'
    elif not rel_path.startswith('/'):
        rel_path = '/' + rel_path
    
    # 获取MIME类型
    mime_type = None
    if not is_dir:
        mime_type, _ = mimetypes.guess_type(file_path)
    
    return FileInfo(
        name=os.path.basename(file_path) if file_path != WORKSPACE_PATH else '/',
        path=rel_path,
        size=stat.st_size,
        type='directory' if is_dir else 'file',
        modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
        permissions=oct(stat.st_mode)[-3:],
        mime_type=mime_type
    )

# 中间件：确保工作目录存在
@app.middleware("http")
async def ensure_workspace(request: Request, call_next):
    if not os.path.exists(WORKSPACE_PATH):
        os.makedirs(WORKSPACE_PATH, exist_ok=True)
    response = await call_next(request)
    return response

# API端点
@app.get("/")
async def root():
    """根端点"""
    return {
        "message": "Suna Sandbox File Server",
        "workspace": WORKSPACE_PATH,
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "workspace_exists": os.path.exists(WORKSPACE_PATH),
        "workspace_writable": os.access(WORKSPACE_PATH, os.W_OK),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/files", response_model=List[FileInfo])
async def list_files(path: str = "/"):
    """列出目录中的文件"""
    try:
        dir_path = get_safe_path(path)
        
        if not os.path.exists(dir_path):
            raise HTTPException(status_code=404, detail="Directory not found")
        
        if not os.path.isdir(dir_path):
            raise HTTPException(status_code=400, detail="Path is not a directory")
        
        files = []
        for item in os.listdir(dir_path):
            item_path = os.path.join(dir_path, item)
            try:
                file_info = get_file_info(item_path)
                files.append(file_info)
            except (OSError, PermissionError):
                # 跳过无法访问的文件
                continue
        
        # 按类型和名称排序
        files.sort(key=lambda x: (x.type == 'file', x.name.lower()))
        
        return files
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")

@app.get("/files/info")
async def get_file_info_endpoint(path: str):
    """获取文件或目录信息"""
    try:
        file_path = get_safe_path(path)
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
        
        return get_file_info(file_path)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get file info: {str(e)}")

@app.get("/files/download")
async def download_file(path: str):
    """下载文件"""
    try:
        file_path = get_safe_path(path)
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
        
        if os.path.isdir(file_path):
            raise HTTPException(status_code=400, detail="Cannot download directory")
        
        return FileResponse(
            file_path,
            filename=os.path.basename(file_path),
            media_type='application/octet-stream'
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download file: {str(e)}")

@app.get("/files/content")
async def get_file_content(path: str, encoding: str = "utf-8"):
    """获取文件内容（文本文件）"""
    try:
        file_path = get_safe_path(path)
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
        
        if os.path.isdir(file_path):
            raise HTTPException(status_code=400, detail="Cannot read directory as file")
        
        # 检查文件大小
        file_size = os.path.getsize(file_path)
        if file_size > 10 * 1024 * 1024:  # 10MB限制
            raise HTTPException(status_code=400, detail="File too large to read as text")
        
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read()
            
            return {
                "content": content,
                "encoding": encoding,
                "size": len(content),
                "path": path
            }
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail=f"Cannot decode file with {encoding} encoding")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}")

@app.post("/files/create")
async def create_file(request: CreateFileRequest):
    """创建文件"""
    try:
        file_path = get_safe_path(request.path)
        
        # 确保父目录存在
        parent_dir = os.path.dirname(file_path)
        os.makedirs(parent_dir, exist_ok=True)
        
        # 写入文件
        with open(file_path, 'w', encoding=request.encoding) as f:
            f.write(request.content)
        
        return {
            "message": "File created successfully",
            "path": request.path,
            "size": len(request.content.encode(request.encoding))
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create file: {str(e)}")

@app.post("/files/upload")
async def upload_file(file: UploadFile = File(...), path: str = Form(...)):
    """上传文件"""
    try:
        file_path = get_safe_path(path)
        
        # 确保父目录存在
        parent_dir = os.path.dirname(file_path)
        os.makedirs(parent_dir, exist_ok=True)
        
        # 保存文件
        with open(file_path, 'wb') as f:
            content = await file.read()
            f.write(content)
        
        return {
            "message": "File uploaded successfully",
            "path": path,
            "filename": file.filename,
            "size": len(content)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")

@app.put("/files/content")
async def update_file_content(request: CreateFileRequest):
    """更新文件内容"""
    try:
        file_path = get_safe_path(request.path)
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
        
        if os.path.isdir(file_path):
            raise HTTPException(status_code=400, detail="Cannot update directory")
        
        # 更新文件内容
        with open(file_path, 'w', encoding=request.encoding) as f:
            f.write(request.content)
        
        return {
            "message": "File updated successfully",
            "path": request.path,
            "size": len(request.content.encode(request.encoding))
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update file: {str(e)}")

@app.post("/directories/create")
async def create_directory(request: CreateDirectoryRequest):
    """创建目录"""
    try:
        dir_path = get_safe_path(request.path)
        
        os.makedirs(dir_path, exist_ok=True)
        
        return {
            "message": "Directory created successfully",
            "path": request.path
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create directory: {str(e)}")

@app.delete("/files/delete")
async def delete_file(path: str):
    """删除文件或目录"""
    try:
        file_path = get_safe_path(path)
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
        
        if os.path.isdir(file_path):
            shutil.rmtree(file_path)
            message = "Directory deleted successfully"
        else:
            os.remove(file_path)
            message = "File deleted successfully"
        
        return {
            "message": message,
            "path": path
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete: {str(e)}")

@app.post("/files/move")
async def move_file(request: MoveRequest):
    """移动文件或目录"""
    try:
        source_path = get_safe_path(request.source)
        dest_path = get_safe_path(request.destination)
        
        if not os.path.exists(source_path):
            raise HTTPException(status_code=404, detail="Source file not found")
        
        # 确保目标目录存在
        dest_dir = os.path.dirname(dest_path)
        os.makedirs(dest_dir, exist_ok=True)
        
        shutil.move(source_path, dest_path)
        
        return {
            "message": "File moved successfully",
            "source": request.source,
            "destination": request.destination
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to move file: {str(e)}")

@app.post("/files/copy")
async def copy_file(request: CopyRequest):
    """复制文件或目录"""
    try:
        source_path = get_safe_path(request.source)
        dest_path = get_safe_path(request.destination)
        
        if not os.path.exists(source_path):
            raise HTTPException(status_code=404, detail="Source file not found")
        
        # 确保目标目录存在
        dest_dir = os.path.dirname(dest_path)
        os.makedirs(dest_dir, exist_ok=True)
        
        if os.path.isdir(source_path):
            shutil.copytree(source_path, dest_path)
        else:
            shutil.copy2(source_path, dest_path)
        
        return {
            "message": "File copied successfully",
            "source": request.source,
            "destination": request.destination
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to copy file: {str(e)}")

@app.get("/workspace/info")
async def get_workspace_info():
    """获取工作空间信息"""
    try:
        stat = os.statvfs(WORKSPACE_PATH)
        
        return {
            "path": WORKSPACE_PATH,
            "exists": os.path.exists(WORKSPACE_PATH),
            "writable": os.access(WORKSPACE_PATH, os.W_OK),
            "disk_usage": {
                "total": stat.f_frsize * stat.f_blocks,
                "free": stat.f_frsize * stat.f_bavail,
                "used": stat.f_frsize * (stat.f_blocks - stat.f_bavail)
            },
            "permissions": oct(os.stat(WORKSPACE_PATH).st_mode)[-3:] if os.path.exists(WORKSPACE_PATH) else None
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get workspace info: {str(e)}")

# 静态文件服务（用于直接访问工作空间文件）
app.mount("/static", StaticFiles(directory=WORKSPACE_PATH), name="static")

if __name__ == "__main__":
    print(f"Starting Suna Sandbox File Server on port {SERVER_PORT}")
    print(f"Workspace: {WORKSPACE_PATH}")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=SERVER_PORT,
        log_level="info"
    )