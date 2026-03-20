#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Web 页面截图模块
使用 Playwright Chromium 进行截图
"""

import os
import time
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from utils.logger import log

# Screenshots 存储目录（保持在 AimiGuard 内）
SCREENSHOT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'screenshots'
)


def _ensure_screenshot_dir():
    """确保截图目录存在"""
    if not os.path.exists(SCREENSHOT_DIR):
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def _get_screenshot_path(ip: str, port: int) -> str:
    """生成截图文件路径"""
    _ensure_screenshot_dir()
    filename = f"{ip.replace('.', '_')}_{port}.png"
    return os.path.join(SCREENSHOT_DIR, filename)


def take_screenshot(url: str, ip: str, port: int, timeout: int = 15000) -> str | None:
    """
    对指定 URL 进行页面截图
    """
    screenshot_path = _get_screenshot_path(ip, port)

    try:
        return _playwright_screenshot(url, screenshot_path, timeout)
    except ImportError:
        log("Screenshot", "未安装 playwright", "ERROR")
    except Exception as e:
        log("Screenshot", f"Playwright 截图失败: {e}", "ERROR")

    return None


def _playwright_screenshot(url: str, output_path: str, timeout: int) -> str | None:
    """使用 Playwright 进行截图"""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--ignore-certificate-errors',
                '--allow-running-insecure-content',
            ]
        )

        context = browser.new_context(
            ignore_https_errors=True,
            user_agent=(
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            )
        )

        page = context.new_page()
        page.set_default_timeout(timeout)

        try:
            response = page.goto(url, wait_until='domcontentloaded', timeout=timeout)

            if response is None:
                log("Screenshot", f"页面无响应: {url}", "WARN")
                return None

            status = response.status
            if status >= 400:
                log("Screenshot", f"HTTP {status}: {url}", "WARN")

            # 等待 JS 渲染
            time.sleep(2)

            # 获取页面高度
            height = page.evaluate(
                "Math.min(document.body.scrollHeight + window.innerHeight, 4000)"
            )
            page.set_viewport_size({'width': 1280, 'height': int(height)})

            page.screenshot(path=output_path, full_page=True, type='png')

            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                log("Screenshot", f"Playwright 截图成功: {output_path}", "INFO")
                return output_path
            return None

        finally:
            page.close()
            context.close()
            browser.close()


if __name__ == '__main__':
    test_url = 'http://example.com'
    path = take_screenshot(test_url, '93.184.216.34', 80)
    print(f"截图路径: {path}")
