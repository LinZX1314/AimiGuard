"""
弱口令检测模块
使用 fscan 的内置弱口令检测能力，同时支持 Python 直接检测
"""

import os
import shutil
import subprocess
import socket

# ─── 常量定义 ────────────────────────────────────────────────────────────────
BRUTEFORCE_TIMEOUT = 120  # fscan 执行超时（秒）
SOCKET_TIMEOUT = 3  # 端口检测超时（秒）
CONN_TIMEOUT = 5  # 服务连接超时（秒）
MAX_OUTPUT_DISPLAY = 2000  # 返回结果截断长度（字符）

# ─── fscan 路径探测（环境变量 -> 本地目录 -> PATH）──────────────────────
_BRUTEFORCE_BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)


def _resolve_fscan_path() -> str | None:
    env_fscan = os.environ.get("FSCAN_PATH", "").strip().strip('"')
    if env_fscan:
        if os.path.isfile(env_fscan):
            return env_fscan
        return None

    project_root = os.path.dirname(_BRUTEFORCE_BASE_DIR)
    local_candidates = [
        os.path.join(project_root, "lib", "fscan.exe"),
        os.path.join(project_root, "bin", "fscan.exe"),
        os.path.join(project_root, "plugin", "bin", "fscan.exe"),
    ]
    for candidate in local_candidates:
        if os.path.isfile(candidate):
            return candidate

    return shutil.which("fscan")


COMMON_SSH_CREDS = [
    ("root", "root"),
    ("root", "toor"),
    ("root", "password"),
    ("root", "123456"),
    ("admin", "admin"),
    ("admin", "password"),
    ("admin", "123456"),
    ("administrator", "administrator"),
    ("user", "user"),
    ("test", "test"),
    ("guest", "guest"),
    ("oracle", "oracle"),
    ("mysql", "mysql"),
]

COMMON_MYSQL_CREDS = [
    ("root", ""),
    ("root", "root"),
    ("root", "mysql"),
    ("root", "123456"),
    ("admin", "admin"),
    ("admin", "root"),
]

# 是否已导入可选依赖（避免重复尝试导入）
_mysql_connector_available = None
_paramiko_available = None


# ─── fscan 内置弱口令检测 ───────────────────────────────────────────────────


def run_fscan_bruteforce(target: str, service_type: str, port: int = None) -> dict:
    """
    使用 fscan 进行弱口令检测。
    fscan 支持 SSH、RDP、SMB、MySQL、MSSQL、PostgreSQL 等服务的弱口令检测。

    参数:
        target: 目标IP
        service_type: 服务类型 (ssh/rdp/mysql/smb/mssql/postgres)
        port: 端口号（可选，fscan会自动扫描）
    """
    fscan_path = _resolve_fscan_path()

    if not fscan_path:
        return {
            "ok": False,
            "error": "未找到 fscan.exe，请放置到项目的 lib/bin/plugin/bin 目录，或配置 FSCAN_PATH，或加入系统 PATH",
            "vulnerable": False,
        }

    # fscan 弱口令检测命令格式: fscan.exe -h ip -m ssh/rdp/mysql/smb
    # fscan 内置用户名字典和密码字典
    try:
        cmd = [
            fscan_path,
            "-h",
            target,
            "-m",
            service_type,
        ]
        if port:
            cmd.extend(["-p", str(port)])

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
        stdout, stderr = proc.communicate(timeout=BRUTEFORCE_TIMEOUT)
        output = stdout + stderr

        # 解析 fscan 输出
        vulnerable_creds = []
        service_found = False

        for line in output.split("\n"):
            line = line.strip()
            if not line:
                continue

            # fscan 检测到弱口令时的输出特征
            if any(
                kw in line.lower() for kw in ["weak", "password", "success", "login"]
            ):
                service_found = True
                # 尝试解析 [+] user password 格式
                if "[+]" in line or "[*]" in line:
                    parts = line.split()
                    for part in parts:
                        if "/" in part and not part.startswith("-"):
                            vulnerable_creds.append(part)

        if vulnerable_creds:
            return {
                "ok": True,
                "host": target,
                "service": service_type.upper(),
                "vulnerable": True,
                "vulnerable_creds": [{"credential": c} for c in vulnerable_creds],
                "message": f"fscan 发现 {len(vulnerable_creds)} 组有效凭据！",
                "raw_output": output[:MAX_OUTPUT_DISPLAY],
            }
        elif service_found:
            return {
                "ok": True,
                "host": target,
                "service": service_type.upper(),
                "vulnerable": False,
                "vulnerable_creds": [],
                "message": "fscan 检测完成，未发现常见弱口令",
                "raw_output": output[:MAX_OUTPUT_DISPLAY],
            }
        else:
            return {
                "ok": True,
                "host": target,
                "service": service_type.upper(),
                "vulnerable": False,
                "vulnerable_creds": [],
                "message": f"fscan 未检测到 {service_type.upper()} 服务或服务无响应",
                "raw_output": output[:MAX_OUTPUT_DISPLAY],
            }

    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "error": f"fscan 弱口令检测超时（超过{BRUTEFORCE_TIMEOUT}秒）",
            "vulnerable": False,
        }
    except Exception as e:
        return {
            "ok": False,
            "error": f"fscan 执行失败: {e}",
            "vulnerable": False,
        }


# ─── 端口检测辅助函数 ───────────────────────────────────────────────────────


def _check_port_open(host: str, port: int, timeout: int = None) -> bool:
    """检测端口是否开放"""
    timeout = timeout or SOCKET_TIMEOUT
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


# ─── Python 原生弱口令检测（备选方案）────────────────────────────────────────


def check_ssh_weak_passwords(host: str, port: int = 22, timeout: int = None) -> dict:
    """Python SSH 弱口令检测（当 fscan 不可用时）"""
    global _paramiko_available
    timeout = timeout or CONN_TIMEOUT

    if _paramiko_available is None:
        try:
            import paramiko as _p

            paramiko = _p
            _paramiko_available = True
        except ImportError:
            _paramiko_available = False

    if not _paramiko_available:
        return {
            "ok": False,
            "error": "缺少 paramiko 库（fscan 方案不可用时需要）",
            "vulnerable": False,
        }

    vulnerable_creds = []
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
    except (socket.timeout, OSError):
        return {
            "ok": False,
            "error": f"SSH 端口 {port} 无法连接",
            "vulnerable": False,
        }

    for username, password in COMMON_SSH_CREDS:
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(
                hostname=host,
                port=port,
                username=username,
                password=password,
                timeout=timeout,
                banner_timeout=timeout,
                auth_timeout=timeout,
                allow_agent=False,
                look_for_keys=False,
            )
            client.close()
            vulnerable_creds.append({"username": username, "password": password})
            break
        except (paramiko.AuthenticationException, socket.timeout, OSError):
            continue
        except Exception:
            continue

    return {
        "ok": True,
        "host": host,
        "port": port,
        "service": "SSH",
        "vulnerable": len(vulnerable_creds) > 0,
        "vulnerable_creds": vulnerable_creds,
        "message": f"发现 {len(vulnerable_creds)} 组 SSH 弱口令！"
        if vulnerable_creds
        else "未发现常见 SSH 弱口令",
    }


def check_mysql_weak_passwords(
    host: str, port: int = 3306, timeout: int = None
) -> dict:
    """Python MySQL 弱口令检测"""
    global _mysql_connector_available
    timeout = timeout or CONN_TIMEOUT

    if _mysql_connector_available is None:
        try:
            import mysql.connector as _mc

            mysql.connector = _mc
            _mysql_connector_available = True
        except ImportError:
            _mysql_connector_available = False

    if not _mysql_connector_available:
        return {
            "ok": False,
            "error": "缺少 mysql-connector-python 库（fscan 方案不可用时需要）",
            "vulnerable": False,
        }

    vulnerable_creds = []
    if not _check_port_open(host, port, SOCKET_TIMEOUT):
        return {
            "ok": False,
            "error": f"MySQL 端口 {port} 无法连接",
            "vulnerable": False,
        }

    for username, password in COMMON_MYSQL_CREDS:
        try:
            conn = mysql.connector.connect(
                host=host,
                port=port,
                user=username,
                password=password,
                connect_timeout=timeout,
            )
            conn.close()
            vulnerable_creds.append(
                {"username": username, "password": password or "(空密码)"}
            )
            break
        except mysql.connector.Error:
            continue
        except Exception:
            continue

    return {
        "ok": True,
        "host": host,
        "port": port,
        "service": "MySQL",
        "vulnerable": len(vulnerable_creds) > 0,
        "vulnerable_creds": vulnerable_creds,
        "message": f"发现 {len(vulnerable_creds)} 组 MySQL 弱口令！"
        if vulnerable_creds
        else "未发现常见 MySQL 弱口令",
    }


# ─── 统一入口 ───────────────────────────────────────────────────────────────


def run_bruteforce(tool_name: str, target_ip: str, port: int = None) -> dict:
    """
    统一弱口令检测入口，优先使用 fscan 方案。

    支持的服务类型映射:
        bruteforce_ssh   -> fscan -m ssh
        bruteforce_rdp   -> fscan -m rdp
        bruteforce_mysql -> fscan -m mysql
    """
    # 从工具名推断服务类型
    if "ssh" in tool_name:
        service_type = "ssh"
        default_port = 22
    elif "rdp" in tool_name:
        service_type = "rdp"
        default_port = 3389
    elif "mysql" in tool_name:
        service_type = "mysql"
        default_port = 3306
    elif "smb" in tool_name:
        service_type = "smb"
        default_port = 445
    elif "mssql" in tool_name:
        service_type = "mssql"
        default_port = 1433
    elif "postgres" in tool_name:
        service_type = "postgres"
        default_port = 5432
    else:
        return {"ok": False, "error": f"不支持的服务类型: {tool_name}"}

    target_port = port or default_port

    # 先检测端口是否开放
    if not _check_port_open(target_ip, target_port):
        return {
            "ok": True,
            "host": target_ip,
            "port": target_port,
            "service": service_type.upper(),
            "vulnerable": False,
            "vulnerable_creds": [],
            "message": f"{service_type.upper()} 端口 {target_port} 未开放，跳过弱口令检测",
        }

    # 优先使用 fscan
    fscan_result = run_fscan_bruteforce(target_ip, service_type, target_port)
    if fscan_result.get("ok"):
        return fscan_result

    # fscan 不可用时降级到 Python 原生检测
    if service_type == "ssh":
        return check_ssh_weak_passwords(target_ip, target_port)
    elif service_type == "mysql":
        return check_mysql_weak_passwords(target_ip, target_port)
    else:
        return {
            "ok": False,
            "error": f"不支持检测 {service_type}，且 fscan 不可用",
            "vulnerable": False,
        }
