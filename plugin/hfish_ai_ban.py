"""
HFish AI 分析与自动封禁模块
"""
import json
import logging
import re

from ai import call_openai_chat_completion
from ai.tools import execute_tool
from database.models import AiModel, HFishModel, SwitchAclModel


def analyze_and_ban_attack_ips(logs: list, cfg: dict) -> dict:
    """
    分析攻击日志，使用AI判断是否需要封禁攻击IP
    每次分析一个IP

    Args:
        logs: 攻击日志列表
        cfg: 系统配置

    Returns:
        dict: 包含分析结果和封禁数量的字典
    """
    logger = logging.getLogger('hfish_ai_ban')

    ai_cfg = cfg.get('ai', {})
    ai_enabled = ai_cfg.get('enabled', False)
    auto_ban = ai_cfg.get('auto_ban', False)
    # ban_threshold 配置项已废弃：实际封禁逻辑由 AI 模型输出 [BAN] 标记决定

    ban_count = 0
    analysis_results = {}

    if not ai_enabled:
        return {'success': True, 'analyzed': 0, 'ban_count': 0}

    # 获取所有唯一攻击IP（排除白名单）
    skip_ips = ["192.168.0.3", "192.168.0.4"]
    attack_ips = list(set(log.get('attack_ip') for log in logs if log.get('attack_ip') and log.get('attack_ip') not in skip_ips))

    if not attack_ips:
        return {'success': True, 'analyzed': 0, 'ban_count': 0}

    logger.info(f"开始分析 {len(attack_ips)} 个攻击IP: {attack_ips}")

    # 过滤掉已封禁的IP（跳过已封禁的IP，不再重复分析）
    ips_to_analyze = []
    for ip in attack_ips:
        existing = AiModel.get_analysis_by_ip(ip)
        if existing and existing.get('decision') == '已封禁':
            logger.info(f"跳过已封禁IP: {ip}")
            continue  # 跳过已封禁的IP
        ips_to_analyze.append(ip)

    logger.info(f"需要分析的IP: {ips_to_analyze}")

    if not ips_to_analyze:
        return {'success': True, 'analyzed': 0, 'ban_count': 0, 'skipped': len(attack_ips)}

    # 逐个IP进行分析
    for ip in ips_to_analyze:
        logger.info(f"开始分析IP: {ip}")

        # 获取该IP的全部历史攻击数据
        all_logs = HFishModel.get_attack_logs_by_ip(ip)

        services = list(set(log.get('service_name') for log in all_logs if log.get('service_name')))
        attack_count = len(all_logs)

        # 获取最近攻击时间
        latest_time = None
        for log in all_logs:
            t = log.get('create_time_str')
            if t and (not latest_time or t > latest_time):
                latest_time = t

        logger.info(f"IP {ip} 攻击次数: {attack_count}, 服务: {services}")

        # 构建单个IP的分析提示词
        prompt = f"""你是一个网络安全分析专家。请分析以下攻击者IP，判断是否需要封禁。

分析规则：
1. 攻击频率高需要封禁
2. 攻击多种服务需要封禁
3. 攻击敏感服务（SSH、RDP、数据库、FTP等）需要封禁

IP信息：
- IP地址: {ip}
- 累计攻击次数: {attack_count} 次
- 攻击服务: {', '.join(services) if services else '未知'}
- 最近攻击时间: {latest_time or '未知'}

请按以下格式返回分析结果：
- 如果需要封禁：返回 [BAN] 原因：<具体原因>
- 如果不需要封禁：返回 [NOBAN] 原因：<具体原因>

例如：
[BAN] 原因：该IP在短时间内攻击12次，且攻击了SSH、FTP、MySQL等多种服务
[NOBAN] 原因：该IP仅尝试攻击1次，且攻击的是非敏感服务"""

        # 调用AI分析
        messages = [{'role': 'user', 'content': prompt}]
        result = call_openai_chat_completion(messages, cfg)
        analysis_text = result.get('content', '')

        logger.info(f"AI返回结果: {analysis_text[:200]}")

        # 解析AI返回结果
        should_ban = False
        ban_reason = ''
        analysis_stripped = analysis_text.strip().upper()

        if '[BAN]' in analysis_stripped:
            should_ban = True
            # 提取原因
            ban_match = re.search(r'\[BAN\][\s：:]*原因[：:]*(.+)', analysis_text, re.IGNORECASE)
            if ban_match:
                ban_reason = ban_match.group(1).strip()
                if len(ban_reason) < 5:  # 原因太短，可能解析错误
                    ban_reason = '攻击频率或威胁等级过高'
            else:
                ban_reason = '攻击频率或威胁等级过高'
            logger.info(f"AI判定需要封禁: {ip}, 原因: {ban_reason}")
        elif '[NOBAN]' in analysis_stripped:
            should_ban = False
            # 提取原因
            noban_match = re.search(r'\[NOBAN\][\s：:]*原因[：:]*(.+)', analysis_text, re.IGNORECASE)
            if noban_match:
                ban_reason = noban_match.group(1).strip()
            else:
                ban_reason = '威胁等级低或攻击频率正常'
            logger.info(f"AI判定不需要封禁: {ip}, 原因: {ban_reason}")
        else:
            # 格式无法识别，默认不封禁但记录错误
            should_ban = False
            ban_reason = f'AI返回格式无法解析: {analysis_text[:50]}...'
            logger.error(f"AI返回格式未知: {analysis_text[:100]}")

        decision = '封禁' if should_ban else '不封禁'

        # 保存分析结果到数据库（包含原因）
        AiModel.save_analysis(ip, analysis_text, decision, status='approved')
        analysis_results[ip] = decision

        # 自动封禁
        if auto_ban and should_ban:
            # 白名单检查
            whitelist = ["192.168.0.4"]
            if ip in whitelist:
                logger.info(f"IP {ip} 在白名单中，已跳过封禁")
                AiModel.save_analysis(ip, analysis_text, '已跳过（白名单）', status='whitelisted')
                continue

            logger.info(f"开始封禁IP: {ip}")

            # 使用 ai/tools.py 中的工具封禁
            ban_result_str = execute_tool('switch_acl_config', {'action': 'ban', 'target_ip': ip}, cfg)
            try:
                ban_result = json.loads(ban_result_str)
            except json.JSONDecodeError:
                ban_result = {'ok': False, 'error': f'解析结果失败: {ban_result_str}'}

            logger.info(f"封禁结果: {ban_result}")

            # 检查封禁是否成功（只要有一台交换机成功就认为成功）
            if ban_result.get('ok'):
                ban_count += 1
                AiModel.save_analysis(ip, analysis_text, '已封禁', status='approved')
                # 记录每台交换机的封禁结果
                for r in ban_result.get('results', []):
                    logger.info(f"  - {r.get('switch_name', r.get('host'))}: {'成功' if r.get('ok') else r.get('error', '失败')}")
                logger.info(f"IP {ip} 封禁完成: {ban_result.get('message', '')}")
            else:
                # 封禁失败，更新状态为失败
                AiModel.save_analysis(ip, analysis_text, '封禁失败', status='error')
                logger.error(f"IP {ip} 封禁失败: {ban_result.get('error', '未知错误')}")
        else:
            # 不需要封禁或封禁未启用，更新状态
            AiModel.save_analysis(ip, analysis_text, decision, status='analyzed')

    return {
        'success': True,
        'analyzed': len(ips_to_analyze),
        'ban_count': ban_count,
        'results': analysis_results
    }
