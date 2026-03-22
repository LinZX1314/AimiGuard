export interface SwitchPort {
  id: number
  name: string
  status: 'up' | 'down' | 'admin-down'
  vlan: number
  speed: string
  tx: number
  rx: number
}

export function createDefaultSwitchPorts(): SwitchPort[] {
  const statuses: SwitchPort['status'][] = ['up', 'down', 'admin-down']

  return Array.from({ length: 24 }, (_, index) => {
    const id = index + 1
    const status = statuses[index % statuses.length] ?? 'up'

    return {
      id,
      name: `GE0/${id}`,
      status,
      vlan: id <= 8 ? 10 : id <= 16 ? 20 : 30,
      speed: id <= 4 ? '1 Gbps' : id <= 16 ? '100 Mbps' : '10 Mbps',
      tx: 24 + id * 3,
      rx: 17 + id * 2,
    }
  })
}

export function chunkPortsForDisplay(ports: readonly SwitchPort[]): {
  topRow: SwitchPort[]
  bottomRow: SwitchPort[]
} {
  return {
    topRow: ports.filter((port) => port.id % 2 !== 0),
    bottomRow: ports.filter((port) => port.id % 2 === 0),
  }
}

export function applySwitchPortConfig(
  ports: readonly SwitchPort[],
  portId: number,
  status: SwitchPort['status'],
  vlan: number,
): SwitchPort[] {
  return ports.map((port) =>
    port.id === portId
      ? {
          ...port,
          status,
          vlan,
        }
      : port,
  )
}
