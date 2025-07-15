#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地沙箱浏览器API
提供浏览器自动化操作接口
"""

import asyncio
import json
import os
import base64
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
import uvicorn

# 配置
BROWSER_API_PORT = int(os.environ.get('BROWSER_API_PORT', '7788'))
DISPLAY = os.environ.get('DISPLAY', ':99')
CHROME_PERSISTENT_SESSION = os.environ.get('CHROME_PERSISTENT_SESSION', 'true').lower() == 'true'

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Suna Sandbox Browser API",
    description="本地沙箱浏览器自动化API",
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
class NavigateRequest(BaseModel):
    url: str
    wait_until: str = "domcontentloaded"  # load, domcontentloaded, networkidle
    timeout: int = 30000

class ClickRequest(BaseModel):
    selector: str
    button: str = "left"  # left, right, middle
    click_count: int = 1
    timeout: int = 30000
    force: bool = False

class TypeRequest(BaseModel):
    selector: str
    text: str
    delay: int = 0
    timeout: int = 30000
    clear: bool = True

class ScrollRequest(BaseModel):
    x: Optional[int] = None
    y: Optional[int] = None
    selector: Optional[str] = None
    behavior: str = "auto"  # auto, smooth

class WaitRequest(BaseModel):
    selector: Optional[str] = None
    url: Optional[str] = None
    timeout: int = 30000
    state: str = "visible"  # visible, hidden, attached, detached

class EvaluateRequest(BaseModel):
    script: str
    args: List[Any] = []

class ScreenshotRequest(BaseModel):
    full_page: bool = False
    clip: Optional[Dict[str, int]] = None
    format: str = "png"  # png, jpeg
    quality: Optional[int] = None

class ElementInfo(BaseModel):
    tag_name: str
    text: Optional[str] = None
    attributes: Dict[str, str] = {}
    bounding_box: Optional[Dict[str, float]] = None
    visible: bool = False

class PageInfo(BaseModel):
    url: str
    title: str
    viewport: Dict[str, int]
    user_agent: str
    cookies: List[Dict[str, Any]] = []

# 全局变量
playwright = None
browser: Optional[Browser] = None
context: Optional[BrowserContext] = None
page: Optional[Page] = None

# 浏览器管理
async def init_browser():
    """初始化浏览器"""
    global playwright, browser, context, page
    
    try:
        playwright = await async_playwright().start()
        
        # 启动浏览器
        browser = await playwright.chromium.launch(
            headless=False,  # 在VNC环境中显示浏览器
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--no-first-run',
                '--no-default-browser-check',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding',
                '--disable-features=TranslateUI',
                '--disable-ipc-flooding-protection',
                f'--display={DISPLAY}'
            ]
        )
        
        # 创建上下文
        context = await browser.new_context(
            viewport={'width': 1024, 'height': 768},
            user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        # 创建页面
        page = await context.new_page()
        
        logger.info("Browser initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize browser: {e}")
        raise

async def cleanup_browser():
    """清理浏览器资源"""
    global playwright, browser, context, page
    
    try:
        if page:
            await page.close()
            page = None
        
        if context:
            await context.close()
            context = None
        
        if browser:
            await browser.close()
            browser = None
        
        if playwright:
            await playwright.stop()
            playwright = None
        
        logger.info("Browser cleanup completed")
        
    except Exception as e:
        logger.error(f"Error during browser cleanup: {e}")

async def ensure_browser():
    """确保浏览器已初始化"""
    global browser, context, page
    
    if not browser or not context or not page:
        await init_browser()

# API端点
@app.on_event("startup")
async def startup_event():
    """应用启动时初始化浏览器"""
    await init_browser()

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理浏览器"""
    await cleanup_browser()

@app.get("/")
async def root():
    """根端点"""
    return {
        "message": "Suna Sandbox Browser API",
        "version": "1.0.0",
        "display": DISPLAY
    }

@app.get("/health")
async def health_check():
    """健康检查"""
    try:
        await ensure_browser()
        
        return {
            "status": "healthy",
            "browser_ready": browser is not None,
            "context_ready": context is not None,
            "page_ready": page is not None,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.post("/navigate")
async def navigate(request: NavigateRequest):
    """导航到指定URL"""
    try:
        await ensure_browser()
        
        response = await page.goto(
            request.url,
            wait_until=request.wait_until,
            timeout=request.timeout
        )
        
        return {
            "success": True,
            "url": page.url,
            "title": await page.title(),
            "status": response.status if response else None
        }
        
    except Exception as e:
        logger.error(f"Navigation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Navigation failed: {str(e)}")

@app.post("/click")
async def click_element(request: ClickRequest):
    """点击元素"""
    try:
        await ensure_browser()
        
        await page.click(
            request.selector,
            button=request.button,
            click_count=request.click_count,
            timeout=request.timeout,
            force=request.force
        )
        
        return {
            "success": True,
            "message": f"Clicked element: {request.selector}"
        }
        
    except Exception as e:
        logger.error(f"Click failed: {e}")
        raise HTTPException(status_code=500, detail=f"Click failed: {str(e)}")

@app.post("/type")
async def type_text(request: TypeRequest):
    """在元素中输入文本"""
    try:
        await ensure_browser()
        
        if request.clear:
            await page.fill(request.selector, "")
        
        await page.type(
            request.selector,
            request.text,
            delay=request.delay,
            timeout=request.timeout
        )
        
        return {
            "success": True,
            "message": f"Typed text in element: {request.selector}"
        }
        
    except Exception as e:
        logger.error(f"Type failed: {e}")
        raise HTTPException(status_code=500, detail=f"Type failed: {str(e)}")

@app.post("/scroll")
async def scroll_page(request: ScrollRequest):
    """滚动页面或元素"""
    try:
        await ensure_browser()
        
        if request.selector:
            # 滚动到指定元素
            await page.locator(request.selector).scroll_into_view_if_needed()
        else:
            # 滚动页面
            if request.x is not None and request.y is not None:
                await page.evaluate(f"window.scrollTo({request.x}, {request.y})")
            elif request.y is not None:
                await page.evaluate(f"window.scrollTo(0, {request.y})")
            elif request.x is not None:
                await page.evaluate(f"window.scrollTo({request.x}, 0)")
        
        return {
            "success": True,
            "message": "Scroll completed"
        }
        
    except Exception as e:
        logger.error(f"Scroll failed: {e}")
        raise HTTPException(status_code=500, detail=f"Scroll failed: {str(e)}")

@app.post("/wait")
async def wait_for_element(request: WaitRequest):
    """等待元素或条件"""
    try:
        await ensure_browser()
        
        if request.selector:
            await page.wait_for_selector(
                request.selector,
                state=request.state,
                timeout=request.timeout
            )
        elif request.url:
            await page.wait_for_url(request.url, timeout=request.timeout)
        else:
            await page.wait_for_timeout(request.timeout)
        
        return {
            "success": True,
            "message": "Wait completed"
        }
        
    except Exception as e:
        logger.error(f"Wait failed: {e}")
        raise HTTPException(status_code=500, detail=f"Wait failed: {str(e)}")

@app.post("/evaluate")
async def evaluate_script(request: EvaluateRequest):
    """执行JavaScript代码"""
    try:
        await ensure_browser()
        
        result = await page.evaluate(request.script, request.args)
        
        return {
            "success": True,
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Evaluate failed: {e}")
        raise HTTPException(status_code=500, detail=f"Evaluate failed: {str(e)}")

@app.post("/screenshot")
async def take_screenshot(request: ScreenshotRequest):
    """截取页面截图"""
    try:
        await ensure_browser()
        
        screenshot_options = {
            "full_page": request.full_page,
            "type": request.format
        }
        
        if request.clip:
            screenshot_options["clip"] = request.clip
        
        if request.quality and request.format == "jpeg":
            screenshot_options["quality"] = request.quality
        
        screenshot_bytes = await page.screenshot(**screenshot_options)
        screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')
        
        return {
            "success": True,
            "screenshot": screenshot_base64,
            "format": request.format,
            "size": len(screenshot_bytes)
        }
        
    except Exception as e:
        logger.error(f"Screenshot failed: {e}")
        raise HTTPException(status_code=500, detail=f"Screenshot failed: {str(e)}")

@app.get("/page/info", response_model=PageInfo)
async def get_page_info():
    """获取页面信息"""
    try:
        await ensure_browser()
        
        viewport = page.viewport_size
        cookies = await context.cookies()
        
        return PageInfo(
            url=page.url,
            title=await page.title(),
            viewport=viewport,
            user_agent=await page.evaluate("navigator.userAgent"),
            cookies=cookies
        )
        
    except Exception as e:
        logger.error(f"Get page info failed: {e}")
        raise HTTPException(status_code=500, detail=f"Get page info failed: {str(e)}")

@app.get("/element/info")
async def get_element_info(selector: str):
    """获取元素信息"""
    try:
        await ensure_browser()
        
        element = page.locator(selector)
        
        # 检查元素是否存在
        count = await element.count()
        if count == 0:
            raise HTTPException(status_code=404, detail="Element not found")
        
        # 获取元素信息
        tag_name = await element.evaluate("el => el.tagName.toLowerCase()")
        text = await element.text_content()
        attributes = await element.evaluate("el => Object.fromEntries([...el.attributes].map(attr => [attr.name, attr.value]))")
        bounding_box = await element.bounding_box()
        visible = await element.is_visible()
        
        return ElementInfo(
            tag_name=tag_name,
            text=text,
            attributes=attributes,
            bounding_box=bounding_box,
            visible=visible
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get element info failed: {e}")
        raise HTTPException(status_code=500, detail=f"Get element info failed: {str(e)}")

@app.get("/elements/find")
async def find_elements(selector: str):
    """查找元素"""
    try:
        await ensure_browser()
        
        elements = page.locator(selector)
        count = await elements.count()
        
        results = []
        for i in range(count):
            element = elements.nth(i)
            tag_name = await element.evaluate("el => el.tagName.toLowerCase()")
            text = await element.text_content()
            visible = await element.is_visible()
            
            results.append({
                "index": i,
                "tag_name": tag_name,
                "text": text[:100] if text else None,  # 限制文本长度
                "visible": visible
            })
        
        return {
            "selector": selector,
            "count": count,
            "elements": results
        }
        
    except Exception as e:
        logger.error(f"Find elements failed: {e}")
        raise HTTPException(status_code=500, detail=f"Find elements failed: {str(e)}")

@app.post("/page/reload")
async def reload_page():
    """重新加载页面"""
    try:
        await ensure_browser()
        
        await page.reload()
        
        return {
            "success": True,
            "url": page.url,
            "title": await page.title()
        }
        
    except Exception as e:
        logger.error(f"Reload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Reload failed: {str(e)}")

@app.post("/page/back")
async def go_back():
    """后退"""
    try:
        await ensure_browser()
        
        await page.go_back()
        
        return {
            "success": True,
            "url": page.url,
            "title": await page.title()
        }
        
    except Exception as e:
        logger.error(f"Go back failed: {e}")
        raise HTTPException(status_code=500, detail=f"Go back failed: {str(e)}")

@app.post("/page/forward")
async def go_forward():
    """前进"""
    try:
        await ensure_browser()
        
        await page.go_forward()
        
        return {
            "success": True,
            "url": page.url,
            "title": await page.title()
        }
        
    except Exception as e:
        logger.error(f"Go forward failed: {e}")
        raise HTTPException(status_code=500, detail=f"Go forward failed: {str(e)}")

@app.post("/browser/restart")
async def restart_browser():
    """重启浏览器"""
    try:
        await cleanup_browser()
        await init_browser()
        
        return {
            "success": True,
            "message": "Browser restarted successfully"
        }
        
    except Exception as e:
        logger.error(f"Browser restart failed: {e}")
        raise HTTPException(status_code=500, detail=f"Browser restart failed: {str(e)}")

if __name__ == "__main__":
    print(f"Starting Suna Sandbox Browser API on port {BROWSER_API_PORT}")
    print(f"Display: {DISPLAY}")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=BROWSER_API_PORT,
        log_level="info"
    )