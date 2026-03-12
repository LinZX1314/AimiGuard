import nmap
import os

# 当前配置的路径（带 nmap.exe）
NMAP_PATH_FILE = r"c:\Users\lzx78\Desktop\AimiGuard\nmap_plugin\Nmap\nmap.exe"
# 目录路径
NMAP_PATH_DIR = r"c:\Users\lzx78\Desktop\AimiGuard\nmap_plugin\Nmap"

print(f"Testing with FILE path: {NMAP_PATH_FILE}")
try:
    nm = nmap.PortScanner(nmap_search_path=(NMAP_PATH_FILE,))
    print("Nmap version (FILE):", nm.nmap_version())
except Exception as e:
    print(f"FAILED with FILE path: {e}")

print(f"\nTesting with DIR path: {NMAP_PATH_DIR}")
try:
    nm = nmap.PortScanner(nmap_search_path=(NMAP_PATH_DIR,))
    print("Nmap version (DIR):", nm.nmap_version())
except Exception as e:
    print(f"FAILED with DIR path: {e}")
