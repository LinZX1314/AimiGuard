export interface WorldView {
  coordinates: [number, number]
  zoom: number
}

export function createInitialWorldView(): WorldView {
  return {
    coordinates: [0, 20],
    zoom: 1.1,
  }
}

export function buildLineColor(attackType: string): string {
  if (attackType.includes('DDoS') || attackType.includes('暴力')) {
    return '#ff4444'
  }

  if (attackType.includes('SQL') || attackType.includes('XSS')) {
    return '#ff7f24'
  }

  return '#ffd700'
}

export function sourcePulseKey(source: [number, number]): string {
  return `${source[0]}-${source[1]}`
}

export function nextAnimatedView(current: WorldView, target: WorldView, progress: number): WorldView {
  const clamped = Math.max(0, Math.min(1, progress))
  const ease = 1 - Math.pow(1 - clamped, 4)

  return {
    coordinates: [
      current.coordinates[0] + (target.coordinates[0] - current.coordinates[0]) * ease,
      current.coordinates[1] + (target.coordinates[1] - current.coordinates[1]) * ease,
    ],
    zoom: current.zoom + (target.zoom - current.zoom) * ease,
  }
}
