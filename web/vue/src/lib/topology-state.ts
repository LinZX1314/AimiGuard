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
      { id: 'internet', label: '互联网', type: 'edge', status: 'attack' },
      { id: 'firewall', label: '主防火墙', type: 'firewall', status: 'online' },
      { id: 'core-switch', label: '核心交换机', type: 'switch', status: 'online' },
      { id: 'dmz-web', label: 'DMZ_WEB', type: 'server', status: 'online' },
      { id: 'api-node', label: 'API 节点', type: 'server', status: 'online' },
      { id: 'db-node', label: '数据库节点', type: 'server', status: 'online' },
      { id: 'soc-console', label: 'SOC 控制台', type: 'router', status: 'online' },
      { id: 'honeypot', label: '诱捕蜜罐', type: 'honeypot', status: 'warning' },
      { id: 'switch-east', label: '接入交换机', type: 'switch', status: 'online' },
    ],
    links: [
      { source: 'internet', target: 'firewall', type: 'uplink' },
      { source: 'internet', target: 'dmz-web', type: 'attack' },
      { source: 'firewall', target: 'core-switch', type: 'lan' },
      { source: 'core-switch', target: 'api-node', type: 'lan' },
      { source: 'core-switch', target: 'db-node', type: 'lan' },
      { source: 'core-switch', target: 'soc-console', type: 'lan' },
      { source: 'core-switch', target: 'switch-east', type: 'lan' },
      { source: 'switch-east', target: 'honeypot', type: 'lan' },
      { source: 'firewall', target: 'honeypot', type: 'blocked' },
    ],
    positions: {
      internet: { x: 106, y: 96 },
      firewall: { x: 282, y: 112 },
      'core-switch': { x: 470, y: 162 },
      'dmz-web': { x: 412, y: 314 },
      'api-node': { x: 600, y: 94 },
      'db-node': { x: 668, y: 248 },
      'soc-console': { x: 584, y: 334 },
      honeypot: { x: 824, y: 152 },
      'switch-east': { x: 756, y: 286 },
    },
  }
}

export function resolveTopologyNodeTone(status: TopologyStatus): string {
  if (status === 'online') return 'var(--cyber-green)'
  if (status === 'warning') return 'var(--cyber-orange)'
  return 'var(--cyber-red)'
}

export function getTopologyLinkColor(type: TopologyLinkType): string {
  if (type === 'uplink') return 'rgba(0, 212, 255, 0.82)'
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
