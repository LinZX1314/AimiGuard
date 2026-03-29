import urllib.request
import json
import sqlite3
import time
from datetime import datetime
import os
import sys
import urllib3
import requests
import threading

# 禁用 SSL 证书校验警告（蜜罐内网自签名证书场景）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 添加项目根目录到 sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from database.db import get_connection
from database.models import HFishModel
from utils.logger import log

# 配置文件路径 (从程序所在目录的上一级读取)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")


# ==================== 配置加载 ====================

def load_config():
    """加载配置文件"""
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


# ==================== API 获取 ====================

def timestamp_to_time(timestamp):
    """时间戳转可读时间"""
    if timestamp == 0:
        return "N/A"
    
    # 判断时间戳单位（秒/毫秒/微秒）
    # 秒级: ~1e9 (2001年) ~1e10 (2286年)
    # 毫秒级: ~1e12 (2001年)
    # 微秒级: ~1e15 (2001年)
    
    if timestamp > 1e14:  # 微秒级
        timestamp = timestamp / 1_000_000
    elif timestamp > 1e12:  # 毫秒级
        timestamp = timestamp / 1000
    
    try:
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    except (OSError, OverflowError, ValueError) as e:
        log("HFish", f"时间戳转换失败: {timestamp}, error: {e}", "ERROR")
        return "Invalid Timestamp"


def _format_error(host_port, err_msg):
    """格式化控制台错误输出"""
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return f""" [{ts}] 罐连接异常，地址: {host_port} """


def get_attack_logs(start_time, end_time, host_port, api_key, api_base_url=''):
    """
    获取攻击详情列表

    参数:
        start_time: 开始时间戳
        end_time: 结束时间戳 (0 表示最新时间)
        host_port: 主机地址和端口，如 "127.0.0.1:4433"
        api_key: API密钥

    返回:
        处理后的攻击详情列表
    """
    urls = []
    base_url = (api_base_url or '').strip().rstrip('/')
    if base_url:
        urls.append(f"{base_url}/api/v1/attack/detail?api_key={api_key}")

    hp = (host_port or '').strip().rstrip('/')
    if hp:
        if hp.startswith('http://') or hp.startswith('https://'):
            urls.append(f"{hp}/api/v1/attack/detail?api_key={api_key}")
        else:
            # 优先 HTTPS，失败后回退 HTTP，兼容不同部署方式
            urls.append(f"https://{hp}/api/v1/attack/detail?api_key={api_key}")
            urls.append(f"http://{hp}/api/v1/attack/detail?api_key={api_key}")

    # 去重保持顺序
    urls = list(dict.fromkeys(urls))
    if not urls:
        log("HFish", _format_error(host_port, "地址配置无效"), "ERROR")
        return None

    all_logs = []
    page_no = 1
    page_size = 10000

    while True:
        payload = json.dumps({
            "start_time": start_time,
            "end_time": end_time,
            "page_no": page_no,
            "page_size": page_size,
            "intranet": -1,
            "threat_label": [],
            "client_id": [],
            "service_name": [],
            "info_confirm": "0"
        })

        headers = {'Content-Type': 'application/json'}

        max_retries = 2
        data = None
        detail_list = []

        for url in urls:
            request_ok = False
            for attempt in range(max_retries):
                try:
                    response = requests.post(url, headers=headers, data=payload, verify=False, timeout=60)
                    response.raise_for_status()
                    data = response.json()

                    # 列表处理
                    if "data" in data and "detail_list" in data.get("data", {}):
                        detail_list = data["data"]["detail_list"]

                        if not detail_list:
                            # 没有更多数据了
                            request_ok = True
                            break

                        for item in detail_list:
                            # 1. 时间戳转换
                            if "create_time" in item:
                                item["create_time_str"] = timestamp_to_time(item["create_time"])
                                del item["create_time"]

                            # 2. 删除多余字段
                            for key in ["attack_info", "threat_name", "threat_label", "threat_level"]:
                                item.pop(key, None)

                        all_logs.extend(detail_list)

                        # 检查是否还有更多数据
                        total = data.get("data", {}).get("total", 0)
                        if page_no * page_size >= total:
                            request_ok = True
                            break

                        request_ok = True
                    else:
                        request_ok = True

                    break  # 当前URL请求成功

                except requests.exceptions.ConnectionError as e:
                    raw = str(e)
                    if attempt < max_retries - 1:
                        time.sleep(2)
                        continue
                    if "10061" in raw or "ConnectionRefusedError" in raw or "积极拒绝" in raw:
                        err_msg = "连接被拒绝，目标主机未响应（请确认 HFish 服务已启动）"
                    elif "Name or service not known" in raw or "nodename nor servname" in raw:
                        err_msg = "无法解析主机名，请检查地址配置"
                    else:
                        err_msg = raw[:80] + "..." if len(raw) > 80 else raw
                    # 继续尝试下一个URL
                    log("HFish", _format_error(host_port, err_msg), "WARN")
                    break

                except requests.exceptions.Timeout:
                    if attempt < max_retries - 1:
                        time.sleep(2)
                        continue
                    log("HFish", _format_error(host_port, "请求超时，HFish 服务响应过慢"), "WARN")
                    break

                except requests.exceptions.HTTPError as e:
                    log("HFish", _format_error(host_port, f"HTTP 错误 {e.response.status_code}: {str(e)}"), "WARN")
                    break

                except Exception as e:
                    log("HFish", _format_error(host_port, str(e)), "WARN")
                    break

            if request_ok:
                break

        if not data:
            log("HFish", _format_error(host_port, "所有协议尝试均失败"), "ERROR")
            return None

        if "data" not in data or "detail_list" not in data.get("data", {}):
            break

        # 检查是否需要继续获取下一页
        total = data.get("data", {}).get("total", 0)
        if page_no * page_size >= total or not detail_list:
            break
        page_no += 1

    return all_logs



# ==================== 主程序 ====================

def main():
    """主函数"""
    import argparse
    import signal
    import sys

    parser = argparse.ArgumentParser(description='HFish攻击日志同步工具')
    parser.add_argument('--host', type=str, help='HFish API地址 (如 127.0.0.1:4433)')
    parser.add_argument('--key', type=str, help='HFish API密钥')
    parser.add_argument('--interval', '-i', type=int, help='同步间隔(秒)')
    parser.add_argument('--once', '-o', action='store_true', help='只同步一次，不循环')
    args = parser.parse_args()

    log("HFish", "程序启动")

    # 加载配置
    raw_config = load_config()
    hfish_config = raw_config.get("hfish", {}).copy()

    # 命令行参数覆盖配置
    if args.host:
        hfish_config["host_port"] = args.host
    if args.key:
        hfish_config["api_key"] = args.key
    if args.interval:
        hfish_config["sync_interval"] = args.interval

    host_port = hfish_config.get("host_port", "127.0.0.1:4433")
    api_base_url = hfish_config.get("api_base_url", "")
    api_key = hfish_config.get("api_key", "")
    interval = hfish_config.get("sync_interval", 60)

    log("HFish", f"配置加载: host={host_port}, interval={interval}秒")

    # 退出信号处理
    def signal_handler(sig, frame):
        log("HFish", "收到退出信号，正在关闭...", "WARN")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    def sync_once():
        """执行一次同步"""
        try:
            last_timestamp = HFishModel.get_last_timestamp()
            if last_timestamp == 0:
                start_time = 0
            else:
                start_time = last_timestamp

            log("HFish", f"开始同步，从时间戳 {start_time} 开始")

            logs = get_attack_logs(start_time, 0, host_port, api_key, api_base_url)

            if logs is None:
                log("HFish", "同步失败，跳过本次同步")
                return
            elif logs:
                new_count = HFishModel.save_logs(logs)
                log("HFish", f"同步完成: 获取 {len(logs)} 条, 新增 {new_count} 条")
            else:
                log("HFish", "无新数据")

        except Exception as e:
            log("HFish", f"同步错误: {e}", "ERROR")

    if args.once:
        sync_once()
    else:
        while True:
            sync_once()
            log("HFish", f"等待 {interval} 秒后进行下一次同步")
            time.sleep(interval)


if __name__ == "__main__":
    main()
