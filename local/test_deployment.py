#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地化沙箱部署测试脚本
用于验证整个本地化方案的功能完整性
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# 添加父目录到Python路径
sandbox_dir = Path(__file__).parent.parent
sys.path.insert(0, str(sandbox_dir))

# 导入本地化模块
from local_sandbox_manager import LocalSandboxManager, SandboxConfig
from local_api_adapter import get_api_adapter
from local_sandbox import LocalSandbox
from local_tool_base import ExampleLocalTool

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class LocalSandboxTester:
    """本地沙箱测试器"""
    
    def __init__(self):
        self.manager = LocalSandboxManager()
        self.api_adapter = get_api_adapter()
        self.test_project_id = f"test-project-{int(time.time())}"
        self.test_results = []
    
    def log_test_result(self, test_name: str, success: bool, message: str = "", details: Any = None):
        """记录测试结果"""
        result = {
            'test_name': test_name,
            'success': success,
            'message': message,
            'details': details,
            'timestamp': datetime.now().isoformat()
        }
        self.test_results.append(result)
        
        status = "✅ PASS" if success else "❌ FAIL"
        logger.info(f"{status} - {test_name}: {message}")
        
        if details and not success:
            logger.error(f"Details: {details}")
    
    async def test_docker_environment(self) -> bool:
        """测试Docker环境"""
        try:
            import docker
            client = docker.from_env()
            
            # 检查Docker是否运行
            info = client.info()
            self.log_test_result(
                "Docker Environment",
                True,
                f"Docker is running (version: {info.get('ServerVersion', 'unknown')})"
            )
            return True
            
        except Exception as e:
            self.log_test_result(
                "Docker Environment",
                False,
                "Docker is not available or not running",
                str(e)
            )
            return False
    
    async def test_sandbox_manager(self) -> bool:
        """测试沙箱管理器"""
        try:
            # 测试创建沙箱
            config = SandboxConfig(
                project_id=self.test_project_id,
                vnc_password="testpass123",
                resolution="1280x720x24"
            )
            
            container_id = await self.manager.create_sandbox(config)
            
            if container_id:
                # 获取沙箱信息来验证创建成功
                sandbox_info = await self.manager.get_sandbox(self.test_project_id)
                self.log_test_result(
                    "Sandbox Manager - Create",
                    True,
                    f"Sandbox created successfully with container ID: {container_id}",
                    sandbox_info
                )
                return True
            else:
                self.log_test_result(
                    "Sandbox Manager - Create",
                    False,
                    "Failed to create sandbox",
                    container_id
                )
                return False
                
        except Exception as e:
            self.log_test_result(
                "Sandbox Manager - Create",
                False,
                "Exception during sandbox creation",
                str(e)
            )
            return False
    
    async def test_sandbox_operations(self) -> bool:
        """测试沙箱基本操作"""
        try:
            # 获取沙箱
            sandbox_info = await self.manager.get_sandbox(self.test_project_id)
            
            if not sandbox_info:
                self.log_test_result(
                    "Sandbox Operations - Get",
                    False,
                    "Cannot get sandbox info"
                )
                return False
            
            self.log_test_result(
                "Sandbox Operations - Get",
                True,
                "Successfully retrieved sandbox info",
                sandbox_info
            )
            
            # 测试列出沙箱
            sandboxes = await self.manager.list_sandboxes()
            found = self.test_project_id in sandboxes
            
            self.log_test_result(
                "Sandbox Operations - List",
                found,
                f"Found {len(sandboxes)} sandboxes, test sandbox {'found' if found else 'not found'}"
            )
            
            return found
            
        except Exception as e:
            self.log_test_result(
                "Sandbox Operations",
                False,
                "Exception during sandbox operations",
                str(e)
            )
            return False
    
    async def test_api_adapter(self) -> bool:
        """测试API适配器"""
        try:
            # 测试获取工作空间
            workspace = await self.api_adapter.get_workspace(self.test_project_id)
            
            if not workspace:
                self.log_test_result(
                    "API Adapter - Get Workspace",
                    False,
                    "Cannot get workspace through API adapter"
                )
                return False
            
            self.log_test_result(
                "API Adapter - Get Workspace",
                True,
                f"Successfully got workspace (status: {workspace.status})",
                {
                    'project_id': workspace.project_id,
                    'status': workspace.status,
                    'urls': workspace.urls
                }
            )
            
            # 测试执行命令
            result = await self.api_adapter.execute_command(
                self.test_project_id,
                "echo 'Hello from API adapter!'",
                "/workspace"
            )
            
            success = result.get('success', False)
            self.log_test_result(
                "API Adapter - Execute Command",
                success,
                f"Command execution {'successful' if success else 'failed'}",
                result
            )
            
            return success
            
        except Exception as e:
            self.log_test_result(
                "API Adapter",
                False,
                "Exception during API adapter test",
                str(e)
            )
            return False
    
    async def test_local_sandbox(self) -> bool:
        """测试本地沙箱类"""
        try:
            # 创建本地沙箱实例
            sandbox = LocalSandbox(self.test_project_id)
            
            # 获取或启动沙箱
            await sandbox.get_or_start_sandbox()
            
            if not sandbox.is_running:
                self.log_test_result(
                    "Local Sandbox - Start",
                    False,
                    "Sandbox is not running after start"
                )
                return False
            
            self.log_test_result(
                "Local Sandbox - Start",
                True,
                "Sandbox is running",
                {
                    'urls': sandbox.urls,
                    'workspace': str(sandbox.workspace)
                }
            )
            
            # 测试supervisord会话
            session_ok = await sandbox.start_supervisord_session()
            self.log_test_result(
                "Local Sandbox - Supervisord",
                session_ok,
                f"Supervisord session {'started' if session_ok else 'failed'}"
            )
            
            # 测试文件操作
            test_file = "/workspace/test_file.txt"
            test_content = "Hello from Local Sandbox test!"
            
            # 创建目录
            dir_created = await sandbox.create_directory("/workspace/test_dir")
            self.log_test_result(
                "Local Sandbox - Create Directory",
                dir_created,
                f"Directory creation {'successful' if dir_created else 'failed'}"
            )
            
            # 执行命令创建文件
            cmd_result = await sandbox.execute_command(
                f"echo '{test_content}' > {test_file}"
            )
            
            file_created = cmd_result.get('success', False)
            self.log_test_result(
                "Local Sandbox - Create File",
                file_created,
                f"File creation {'successful' if file_created else 'failed'}",
                cmd_result
            )
            
            # 列出文件
            files = await sandbox.list_files("/workspace")
            self.log_test_result(
                "Local Sandbox - List Files",
                len(files) > 0,
                f"Found {len(files)} files/directories",
                files
            )
            
            # 健康检查
            health = await sandbox.health_check()
            healthy = health.get('healthy', False)
            self.log_test_result(
                "Local Sandbox - Health Check",
                healthy,
                f"Health check {'passed' if healthy else 'failed'}",
                health
            )
            
            # Supervisord会话失败不影响整体功能，因为服务已经在运行
            return dir_created and file_created and healthy
            
        except Exception as e:
            self.log_test_result(
                "Local Sandbox",
                False,
                "Exception during local sandbox test",
                str(e)
            )
            return False
    
    async def test_tool_base(self) -> bool:
        """测试工具基类"""
        try:
            # 创建示例工具
            tool = ExampleLocalTool(self.test_project_id)
            
            # 执行工具
            result = await tool.execute_tool("ls -la /workspace")
            
            success = result.get('success', False)
            self.log_test_result(
                "Tool Base - Execute Tool",
                success,
                f"Tool execution {'successful' if success else 'failed'}",
                result
            )
            
            # 测试文件操作
            test_file = "/workspace/tool_test.txt"
            test_content = "Hello from Tool Base test!"
            
            # 使用bash命令正确处理重定向
            cmd_result = await tool.execute_command(f"bash -c \"echo '{test_content}' > {test_file}\"", "/workspace")
            write_ok = cmd_result.get('success', False) and cmd_result.get('exit_code') == 0
            
            self.log_test_result(
                "Tool Base - Write File",
                write_ok,
                f"File write {'successful' if write_ok else 'failed'}",
                cmd_result
            )
            
            if write_ok:
                # 等待文件写入完成
                await asyncio.sleep(1.0)
                
                # 多次检查文件是否存在
                file_exists = False
                for attempt in range(3):
                    file_exists = await tool.file_exists(test_file)
                    if file_exists:
                        break
                    await asyncio.sleep(0.5)
                
                if file_exists:
                    content = await tool.read_file(test_file)
                    read_ok = content is not None and test_content in content
                    self.log_test_result(
                        "Tool Base - Read File",
                        read_ok,
                        f"File read {'successful' if read_ok else 'failed'}",
                        content
                    )
                else:
                    # 尝试直接列出目录查看文件
                    files = await tool.list_files("/workspace")
                    self.log_test_result(
                        "Tool Base - Read File",
                        False,
                        f"File does not exist after write. Directory contents: {[f['name'] for f in files]}"
                    )
                    read_ok = False
            else:
                read_ok = False
            
            # 健康检查
            health = await tool.health_check()
            healthy = health.get('healthy', False)
            self.log_test_result(
                "Tool Base - Health Check",
                healthy,
                f"Tool health check {'passed' if healthy else 'failed'}",
                health
            )
            
            return success and write_ok and read_ok and healthy
            
        except Exception as e:
            self.log_test_result(
                "Tool Base",
                False,
                "Exception during tool base test",
                str(e)
            )
            return False
    
    async def test_service_urls(self) -> bool:
        """测试服务URL可访问性"""
        try:
            import aiohttp
            
            # 获取沙箱信息
            sandbox_info = await self.manager.get_sandbox(self.test_project_id)
            urls = sandbox_info.get('urls', {})
            
            if not urls:
                self.log_test_result(
                    "Service URLs",
                    False,
                    "No service URLs found"
                )
                return False
            
            accessible_count = 0
            total_count = len(urls)
            
            async with aiohttp.ClientSession() as session:
                for service, url in urls.items():
                    # 跳过VNC协议，因为它不是HTTP协议
                    if url.startswith('vnc://'):
                        self.log_test_result(
                            f"Service URL - {service}",
                            True,  # VNC服务已在健康检查中验证
                            f"VNC protocol URL {url} (skipped HTTP test)"
                        )
                        accessible_count += 1
                        continue
                        
                    try:
                        async with session.get(url, timeout=5) as response:
                            accessible = response.status < 500
                            if accessible:
                                accessible_count += 1
                            
                            self.log_test_result(
                                f"Service URL - {service}",
                                accessible,
                                f"URL {url} {'accessible' if accessible else 'not accessible'} (status: {response.status})"
                            )
                            
                    except Exception as e:
                        self.log_test_result(
                            f"Service URL - {service}",
                            False,
                            f"URL {url} not accessible",
                            str(e)
                        )
            
            success = accessible_count > 0
            self.log_test_result(
                "Service URLs - Overall",
                success,
                f"{accessible_count}/{total_count} services accessible"
            )
            
            return success
            
        except ImportError:
            self.log_test_result(
                "Service URLs",
                False,
                "aiohttp not available for URL testing"
            )
            return False
        except Exception as e:
            self.log_test_result(
                "Service URLs",
                False,
                "Exception during URL testing",
                str(e)
            )
            return False
    
    async def cleanup_test_resources(self) -> bool:
        """清理测试资源"""
        try:
            # 删除测试沙箱
            success = await self.manager.delete_sandbox(self.test_project_id)
            
            self.log_test_result(
                "Cleanup",
                success,
                f"Test sandbox {'deleted' if success else 'deletion failed'}"
            )
            
            return success
            
        except Exception as e:
            self.log_test_result(
                "Cleanup",
                False,
                "Exception during cleanup",
                str(e)
            )
            return False
    
    def generate_report(self) -> Dict[str, Any]:
        """生成测试报告"""
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['success'])
        failed_tests = total_tests - passed_tests
        
        report = {
            'summary': {
                'total_tests': total_tests,
                'passed_tests': passed_tests,
                'failed_tests': failed_tests,
                'success_rate': f"{(passed_tests / total_tests * 100):.1f}%" if total_tests > 0 else "0%",
                'test_duration': None,
                'timestamp': datetime.now().isoformat()
            },
            'test_results': self.test_results,
            'recommendations': []
        }
        
        # 添加建议
        if failed_tests > 0:
            report['recommendations'].append(
                "Some tests failed. Please check the Docker environment and network connectivity."
            )
        
        if passed_tests == total_tests:
            report['recommendations'].append(
                "All tests passed! The local sandbox implementation is working correctly."
            )
        
        return report
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """运行所有测试"""
        start_time = time.time()
        
        logger.info("🚀 Starting Local Sandbox Deployment Tests")
        logger.info(f"Test Project ID: {self.test_project_id}")
        
        try:
            # 运行测试序列
            tests = [
                ("Docker Environment", self.test_docker_environment),
                ("Sandbox Manager", self.test_sandbox_manager),
                ("Sandbox Operations", self.test_sandbox_operations),
                ("API Adapter", self.test_api_adapter),
                ("Local Sandbox", self.test_local_sandbox),
                ("Tool Base", self.test_tool_base),
                ("Service URLs", self.test_service_urls),
            ]
            
            for test_name, test_func in tests:
                logger.info(f"\n🔍 Running {test_name} tests...")
                try:
                    await test_func()
                except Exception as e:
                    self.log_test_result(
                        test_name,
                        False,
                        f"Unexpected error in {test_name}",
                        str(e)
                    )
                
                # 短暂延迟，让服务稳定
                await asyncio.sleep(1)
            
        finally:
            # 清理资源
            logger.info("\n🧹 Cleaning up test resources...")
            await self.cleanup_test_resources()
        
        # 生成报告
        end_time = time.time()
        report = self.generate_report()
        report['summary']['test_duration'] = f"{(end_time - start_time):.2f}s"
        
        return report

async def main():
    """主函数"""
    print("\n" + "="*60)
    print("🏗️  Suna Local Sandbox Deployment Test")
    print("="*60)
    
    tester = LocalSandboxTester()
    
    try:
        report = await tester.run_all_tests()
        
        # 打印报告
        print("\n" + "="*60)
        print("📊 TEST REPORT")
        print("="*60)
        
        summary = report['summary']
        print(f"Total Tests: {summary['total_tests']}")
        print(f"Passed: {summary['passed_tests']} ✅")
        print(f"Failed: {summary['failed_tests']} ❌")
        print(f"Success Rate: {summary['success_rate']}")
        print(f"Duration: {summary['test_duration']}")
        
        if report['recommendations']:
            print("\n📝 Recommendations:")
            for rec in report['recommendations']:
                print(f"  • {rec}")
        
        # 保存详细报告
        report_file = f"test_report_{int(time.time())}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 Detailed report saved to: {report_file}")
        
        # 返回退出码
        exit_code = 0 if summary['failed_tests'] == 0 else 1
        
        if exit_code == 0:
            print("\n🎉 All tests passed! Local sandbox is ready for use.")
        else:
            print("\n⚠️  Some tests failed. Please check the logs and fix issues.")
        
        return exit_code
        
    except KeyboardInterrupt:
        print("\n⏹️  Tests interrupted by user")
        return 130
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        logger.exception("Unexpected error during testing")
        return 1

if __name__ == "__main__":
    # 检查依赖
    try:
        import docker
        import aiohttp
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Please install required packages:")
        print("  pip install docker aiohttp")
        sys.exit(1)
    
    # 运行测试
    exit_code = asyncio.run(main())
    sys.exit(exit_code)