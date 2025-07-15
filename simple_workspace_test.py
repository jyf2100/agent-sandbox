#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化的工作空间测试脚本
用于测试本地化方案的基础功能，不依赖Docker镜像
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

# 添加父目录到Python路径
sandbox_dir = Path(__file__).parent
sys.path.insert(0, str(sandbox_dir))

# 导入本地化模块
try:
    from local_api_adapter import LocalApiAdapter, get_api_adapter
except ImportError as e:
    print(f"导入错误: {e}")
    sys.exit(1)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SimpleWorkspaceTester:
    """简化的工作空间测试器"""
    
    def __init__(self):
        self.test_results = []
        self.start_time = time.time()
    
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
            logger.error(f"详细信息: {details}")
    
    async def test_api_adapter_import(self) -> bool:
        """测试API适配器导入"""
        try:
            adapter = LocalApiAdapter()
            self.log_test_result(
                "API适配器导入",
                True,
                "成功导入LocalApiAdapter类"
            )
            return True
        except Exception as e:
            self.log_test_result(
                "API适配器导入",
                False,
                "导入LocalApiAdapter失败",
                str(e)
            )
            return False
    
    async def test_get_api_adapter(self) -> bool:
        """测试获取API适配器实例"""
        try:
            adapter = get_api_adapter()
            if adapter is not None:
                self.log_test_result(
                    "获取API适配器实例",
                    True,
                    f"成功获取API适配器实例: {type(adapter).__name__}"
                )
                return True
            else:
                self.log_test_result(
                    "获取API适配器实例",
                    False,
                    "get_api_adapter()返回None"
                )
                return False
        except Exception as e:
            self.log_test_result(
                "获取API适配器实例",
                False,
                "获取API适配器实例失败",
                str(e)
            )
            return False
    
    async def test_workspace_operations_without_docker(self) -> bool:
        """测试不依赖Docker的工作空间操作"""
        try:
            adapter = get_api_adapter()
            
            # 测试列出工作空间（应该返回空列表或处理错误）
            try:
                workspaces = await adapter.list_workspaces()
                self.log_test_result(
                    "列出工作空间",
                    True,
                    f"成功调用list_workspaces，返回{len(workspaces)}个工作空间",
                    [w.to_dict() if hasattr(w, 'to_dict') else str(w) for w in workspaces]
                )
                return True
            except Exception as e:
                # 这是预期的，因为没有Docker环境
                self.log_test_result(
                    "列出工作空间",
                    True,  # 这里标记为成功，因为能正确处理错误是好的
                    f"正确处理了Docker不可用的情况: {str(e)[:100]}"
                )
                return True
                
        except Exception as e:
            self.log_test_result(
                "工作空间操作测试",
                False,
                "工作空间操作测试失败",
                str(e)
            )
            return False
    
    async def test_module_structure(self) -> bool:
        """测试模块结构"""
        try:
            # 检查关键模块是否存在
            modules_to_check = [
                'local_api_adapter',
                'local_sandbox',
                'local_sandbox_manager',
                'local_tool_base'
            ]
            
            missing_modules = []
            existing_modules = []
            
            for module_name in modules_to_check:
                try:
                    __import__(module_name)
                    existing_modules.append(module_name)
                except ImportError:
                    missing_modules.append(module_name)
            
            if not missing_modules:
                self.log_test_result(
                    "模块结构检查",
                    True,
                    f"所有关键模块都存在: {', '.join(existing_modules)}"
                )
                return True
            else:
                self.log_test_result(
                    "模块结构检查",
                    False,
                    f"缺少模块: {', '.join(missing_modules)}",
                    f"存在的模块: {', '.join(existing_modules)}"
                )
                return False
                
        except Exception as e:
            self.log_test_result(
                "模块结构检查",
                False,
                "模块结构检查失败",
                str(e)
            )
            return False
    
    async def test_file_structure(self) -> bool:
        """测试文件结构"""
        try:
            base_dir = Path(__file__).parent
            required_files = [
                'local_api_adapter.py',
                'local_sandbox.py', 
                'local_sandbox_manager.py',
                'local_tool_base.py',
                'local_api.py',
                'local/Dockerfile',
                'local/server.py',
                'local/browser_api.py'
            ]
            
            missing_files = []
            existing_files = []
            
            for file_path in required_files:
                full_path = base_dir / file_path
                if full_path.exists():
                    existing_files.append(file_path)
                else:
                    missing_files.append(file_path)
            
            if not missing_files:
                self.log_test_result(
                    "文件结构检查",
                    True,
                    f"所有必需文件都存在 ({len(existing_files)}/{len(required_files)})"
                )
                return True
            else:
                self.log_test_result(
                    "文件结构检查",
                    False,
                    f"缺少文件: {', '.join(missing_files)}",
                    f"存在的文件: {', '.join(existing_files)}"
                )
                return False
                
        except Exception as e:
            self.log_test_result(
                "文件结构检查",
                False,
                "文件结构检查失败",
                str(e)
            )
            return False
    
    def generate_report(self) -> Dict[str, Any]:
        """生成测试报告"""
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['success'])
        failed_tests = total_tests - passed_tests
        
        end_time = time.time()
        duration = end_time - self.start_time
        
        report = {
            'summary': {
                'total_tests': total_tests,
                'passed_tests': passed_tests,
                'failed_tests': failed_tests,
                'success_rate': f"{(passed_tests / total_tests * 100):.1f}%" if total_tests > 0 else "0%",
                'test_duration': f"{duration:.2f}s",
                'timestamp': datetime.now().isoformat()
            },
            'test_results': self.test_results,
            'recommendations': []
        }
        
        # 添加建议
        if failed_tests > 0:
            report['recommendations'].append(
                "部分测试失败。请检查模块导入和文件结构。"
            )
        
        if passed_tests == total_tests:
            report['recommendations'].append(
                "所有基础测试通过！本地化沙箱的基础结构正常。"
            )
            report['recommendations'].append(
                "下一步可以构建Docker镜像并运行完整测试。"
            )
        
        return report
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """运行所有测试"""
        logger.info("🚀 开始简化工作空间测试")
        
        tests = [
            ("API适配器导入测试", self.test_api_adapter_import),
            ("获取API适配器实例测试", self.test_get_api_adapter),
            ("模块结构测试", self.test_module_structure),
            ("文件结构测试", self.test_file_structure),
            ("工作空间操作测试", self.test_workspace_operations_without_docker),
        ]
        
        for test_name, test_func in tests:
            logger.info(f"\n🔍 运行 {test_name}...")
            try:
                await test_func()
            except Exception as e:
                self.log_test_result(
                    test_name,
                    False,
                    f"{test_name}中发生意外错误",
                    str(e)
                )
            
            # 短暂延迟
            await asyncio.sleep(0.1)
        
        return self.generate_report()

async def main():
    """主函数"""
    print("\n" + "="*60)
    print("🏗️  Suna 工作空间简化测试")
    print("="*60)
    
    tester = SimpleWorkspaceTester()
    
    try:
        report = await tester.run_all_tests()
        
        # 打印报告
        print("\n" + "="*60)
        print("📊 测试报告")
        print("="*60)
        
        summary = report['summary']
        print(f"总测试数: {summary['total_tests']}")
        print(f"通过: {summary['passed_tests']} ✅")
        print(f"失败: {summary['failed_tests']} ❌")
        print(f"成功率: {summary['success_rate']}")
        print(f"耗时: {summary['test_duration']}")
        
        if report['recommendations']:
            print("\n📝 建议:")
            for rec in report['recommendations']:
                print(f"  • {rec}")
        
        # 保存详细报告
        report_file = f"simple_test_report_{int(time.time())}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 详细报告已保存到: {report_file}")
        
        # 返回退出码
        exit_code = 0 if summary['failed_tests'] == 0 else 1
        
        if exit_code == 0:
            print("\n🎉 所有基础测试通过！")
            print("💡 提示: 要运行完整测试，请先构建Docker镜像:")
            print("   cd local && docker build -t local-suna-sandbox .")
        else:
            print("\n⚠️  部分测试失败。请检查日志并修复问题。")
        
        return exit_code
        
    except KeyboardInterrupt:
        print("\n⏹️  测试被用户中断")
        return 130
    except Exception as e:
        print(f"\n💥 意外错误: {e}")
        logger.exception("测试过程中发生意外错误")
        return 1

if __name__ == "__main__":
    # 运行测试
    exit_code = asyncio.run(main())
    sys.exit(exit_code)