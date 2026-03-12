import time
from pysnmp.entity.rfc3413.oneliner import cmdgen
from pysnmp.proto import rfc1902

# ==================== 锐捷 SNMP v3 测试配置区 ====================
SWITCH_IP = "192.168.0.254"     # 交换机IP
SNMP_VERSION = 3                # 锐捷建议使用 v3

# SNMP v3 参数填写
V3_USER = "ruijie"              # SNMP口令/用户名 (对应你的 'SNMP口令')
V3_AUTH_KEY = "auth_pass"       # 认证密码 (Authentication Password)
V3_PRIV_KEY = "priv_pass"       # 加密密码 (Privacy Password)

# 目标端口索引 (ifIndex)
TARGET_IF_INDEX = 1             # 请根据实际情况修改（可以通过查看接口索引表获得）
# ===============================================================

class RuijieSNMPTest:
    def __init__(self):
        self.cmd_gen = cmdgen.CommandGenerator()

    def _get_auth(self):
        if SNMP_VERSION == 3:
            return cmdgen.UsmUserData(
                V3_USER, V3_AUTH_KEY, V3_PRIV_KEY,
                authProtocol=cmdgen.usmHMACSHAAuthProtocol,
                privProtocol=cmdgen.usmDESPrivProtocol
            )
        return cmdgen.CommunityData(COMMUNITY)

    def set_port_status(self, if_index, status):
        """
        status: 1 (up), 2 (down/shutdown)
        OID: 1.3.6.1.2.1.2.2.1.7 (ifAdminStatus)
        """
        oid = (1, 3, 6, 1, 2, 1, 2, 2, 1, 7, int(if_index))
        var_binds = [(oid, rfc1902.Integer(status))]
        
        print(f"[*] 正在尝试将交换机 {SWITCH_IP} 端口 {if_index} 状态设为: {'UP' if status==1 else 'DOWN'}...")
        
        error_indication, error_status, error_index, var_bind_res = self.cmd_gen.setCmd(
            self._get_auth(),
            cmdgen.UdpTransportTarget((SWITCH_IP, 161)),
            *var_binds
        )
        
        if error_indication:
            print(f"[!] 错误: {error_indication}")
            return False
        elif error_status:
            print(f"[!] SNMP 错误: {error_status.prettyPrint()}")
            return False
        
        print(f"[+] 指令发送成功！")
        return True

    def get_port_info(self, if_index):
        """获取端口描述和当前状态"""
        # Descr OID: 1.3.6.1.2.1.2.2.1.2
        # Status OID: 1.3.6.1.2.1.2.2.1.8 (ifOperStatus)
        descr_oid = (1, 3, 6, 1, 2, 1, 2, 2, 1, 2, int(if_index))
        status_oid = (1, 3, 6, 1, 2, 1, 2, 2, 1, 8, int(if_index))
        
        error_indication, error_status, error_index, var_bind_res = self.cmd_gen.getCmd(
            self._get_auth(),
            cmdgen.UdpTransportTarget((SWITCH_IP, 161)),
            descr_oid, status_oid
        )
        
        if not error_indication and not error_status:
            descr = var_bind_res[0][1].prettyPrint()
            status = "UP" if int(var_bind_res[1][1]) == 1 else "DOWN"
            print(f"[i] 端口信息: 索引={if_index}, 描述={descr}, 当前实时状态={status}")
            return True
        return False

if __name__ == "__main__":
    print("=== 锐捷交换机 SNMP 控制测试工具 ===")
    tester = RuijieSNMPTest()
    
    # 1. 先读取一下状态
    if tester.get_port_info(TARGET_IF_INDEX):
        print("\n--- 执行封禁测试 (Shutdown) ---")
        # 2. 执行 Shutdown (慎用，确保 TARGET_IF_INDEX 不是你连接交换机的口)
        # tester.set_port_status(TARGET_IF_INDEX, 2)
        
        # 3. 5秒后恢复 (Undo Shutdown)
        # time.sleep(5)
        # tester.set_port_status(TARGET_IF_INDEX, 1)
        
        print("\n[提示] 为了安全，脚本默认注释掉了 Set 操作。请在代码中取消注释后运行。")
    else:
        print("[!] 无法获取端口信息，请检查 SNMP 配置或网络连通性。")
