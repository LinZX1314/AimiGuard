export type TopologyStatus = 'online' | 'offline' | 'warning' | 'attack'
export type TopologyNodeType = 'edge' | 'router' | 'firewall' | 'server' | 'switch' | 'honeypot'
export type TopologyLinkType = 'uplink' | 'lan' | 'blocked' | 'attack'

export interface TopologyNode {
  id: string
  label: string
  type: TopologyNodeType
  status: TopologyStatus
}

export interface TopologyLink {
  source: string
  target: string
  type: TopologyLinkType
}

export interface TopologyPoint {
  x: number
  y: number
}

export interface TopologyFixture {
  nodes: TopologyNode[]
  links: TopologyLink[]
  positions: Record<string, TopologyPoint>
}

export interface TopologySummary {
  nodeCount: number
  onlineCount: number
  warningCount: number
  attackCount: number
  linkCount: number
}

export interface TopologyStageLink {
  id: string
  sourceId: string
  targetId: string
  sourcePoint: TopologyPoint
  targetPoint: TopologyPoint
  type: TopologyLinkType
  color: string
  active: boolean
}

export interface TopologyStageNode extends TopologyNode {
  point: TopologyPoint
  tone: string
  selected: boolean
}

export function createTopologyFixture(): TopologyFixture {
  return {
    nodes: [
      { id: 'attacker-1', label: '境外攻击源 (Botnet)', type: 'honeypot', status: 'attack' },
      { id: 'attacker-2', label: '代理IP池', type: 'honeypot', status: 'warning' },
      { id: 'internet', label: '互联网出口 (BGP)', type: 'edge', status: 'attack' },
      { id: 'fw-master', label: '主边界防火墙 (Active)', type: 'firewall', status: 'online' },
      { id: 'waf-cluster', label: 'WAF 集群 (拦截态)', type: 'firewall', status: 'warning' },
      { id: 'core-switch', label: '核心数据中心交换机', type: 'switch', status: 'online' },
      { id: 'sw-dmz', label: '前置接入区(DMZ)交换机', type: 'switch', status: 'online' },
      { id: 'sw-data', label: '后端数据区交换机', type: 'switch', status: 'online' },
      { id: 'web-portal', label: '官网门户业务群', type: 'server', status: 'online' },
      { id: 'api-gateway', label: 'API 网关服务', type: 'server', status: 'online' },
      { id: 'auth-server', label: '认证统一鉴权服务', type: 'server', status: 'online' },
      { id: 'db-master', label: '主数据库 (MySQL)', type: 'server', status: 'online' },
      { id: 'db-redis', label: '缓存集群 (Redis)', type: 'server', status: 'online' },
      { id: 'hfish-node', label: 'HFish 高交互蜜罐', type: 'honeypot', status: 'warning' },
      { id: 'soc-center', label: '安全运营中心 (SOC)', type: 'router', status: 'online' },
    ],
    links: [
      { source: 'attacker-1', target: 'internet', type: 'attack' },
      { source: 'attacker-2', target: 'internet', type: 'attack' },
      { source: 'internet', target: 'fw-master', type: 'uplink' },
      { source: 'fw-master', target: 'waf-cluster', type: 'lan' },
      { source: 'waf-cluster', target: 'core-switch', type: 'lan' },
      { source: 'core-switch', target: 'sw-dmz', type: 'lan' },
      { source: 'core-switch', target: 'sw-data', type: 'lan' },
      { source: 'core-switch', target: 'soc-center', type: 'lan' },
      { source: 'sw-dmz', target: 'web-portal', type: 'lan' },
      { source: 'sw-dmz', target: 'api-gateway', type: 'lan' },
      { source: 'sw-dmz', target: 'auth-server', type: 'lan' },
      { source: 'sw-data', target: 'db-master', type: 'lan' },
      { source: 'sw-data', target: 'db-redis', type: 'lan' },
      { source: 'sw-dmz', target: 'hfish-node', type: 'lan' },
      { source: 'fw-master', target: 'hfish-node', type: 'blocked' }, // 防火墙联动蜜罐旁路镜像或重定向
      { source: 'waf-cluster', target: 'attacker-1', type: 'blocked' }, // WAF 拦截攻击者
    ],
    positions: {
      'attacker-1': { x: 42, y: 64 },
      'attacker-2': { x: 42, y: 196 },
      internet: { x: 168, y: 130 },
      'fw-master': { x: 300, y: 130 },
      'waf-cluster': { x: 432, y: 130 },
      'core-switch': { x: 564, y: 130 },
      'sw-dmz': { x: 740, y: 64 },
      'sw-data': { x: 740, y: 220 },
      'web-portal': { x: 880, y: 20 },
      'api-gateway': { x: 880, y: 90 },
      'auth-server': { x: 880, y: 160 },
      'db-master': { x: 880, y: 236 },
      'db-redis': { x: 880, y: 306 },
      'hfish-node': { x: 620, y: 320 },
      'soc-center': { x: 450, y: 320 },
    },
  }
}

export function resolveTopologyNodeTone(status: TopologyStatus): string {
  if (status === 'online') return 'var(--cyber-green)'
  if (status === 'warning') return 'var(--cyber-orange)'
  return 'var(--cyber-red)'
}

export function getTopologyLinkColor(type: TopologyLinkType): string {
if (type === 'uplink') return 'hsl(var(--primary))'
  if (type === 'lan') return 'rgba(0, 255, 136, 0.58)'
  if (type === 'blocked') return 'rgba(0, 255, 136, 0.8)'
  return 'rgba(255, 68, 68, 0.82)'
}

export function buildTopologyStageLinks(topology: TopologyFixture, selectedNodeId: string | null): TopologyStageLink[] {
  return topology.links
    .map((link) => {
      const sourcePoint = topology.positions[link.source]
      const targetPoint = topology.positions[link.target]
      if (!sourcePoint || !targetPoint) return null

      return {
        id: `${link.source}-${link.target}`,
        sourceId: link.source,
        targetId: link.target,
        sourcePoint,
        targetPoint,
        type: link.type,
        color: getTopologyLinkColor(link.type),
        active: selectedNodeId === link.source || selectedNodeId === link.target,
      }
    })
    .filter((link): link is TopologyStageLink => Boolean(link))
}

export function buildTopologyStageNodes(topology: TopologyFixture, selectedNodeId: string | null): TopologyStageNode[] {
  return topology.nodes.map((node) => ({
    ...node,
    point: topology.positions[node.id],
    tone: resolveTopologyNodeTone(node.status),
    selected: selectedNodeId === node.id,
  }))
}

export function getTopologySummary(topology: Pick<TopologyFixture, 'nodes' | 'links'>): TopologySummary {
  return {
    nodeCount: topology.nodes.length,
    onlineCount: topology.nodes.filter((node) => node.status === 'online').length,
    warningCount: topology.nodes.filter((node) => node.status === 'warning').length,
    attackCount: topology.nodes.filter((node) => node.status === 'attack').length,
    linkCount: topology.links.length,
  }
}
