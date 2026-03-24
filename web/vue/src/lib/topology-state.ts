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
      { id: 'core-router', label: '核心路由器', type: 'router', status: 'online' },
      { id: 'sw-1', label: '交换机 1', type: 'switch', status: 'online' },
      { id: 'sw-2', label: '交换机 2', type: 'switch', status: 'online' },
    ],
    links: [
      { source: 'sw-1', target: 'core-router', type: 'lan' },
      { source: 'sw-2', target: 'core-router', type: 'lan' },
    ],
    positions: {
      'core-router': { x: 400, y: 200 },
      'sw-1': { x: 200, y: 200 },
      'sw-2': { x: 600, y: 200 },
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
