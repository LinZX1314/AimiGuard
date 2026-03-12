import nmap
import os

NMAP_PATH = r"c:\Users\lzx78\Desktop\AimiGuard\nmap\Nmap\nmap.exe"

try:
    print(f"Using nmap at: {NMAP_PATH}")
    nm = nmap.PortScanner(nmap_search_path=(NMAP_PATH,))
    print("Nmap version:", nm.nmap_version())
    
    target = "127.0.0.1"
    args = "-sV -T4"
    print(f"Scanning {target} with {args}...")
    
    nm.scan(hosts=target, arguments=args)
    print("Scan results:", nm.all_hosts())
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
