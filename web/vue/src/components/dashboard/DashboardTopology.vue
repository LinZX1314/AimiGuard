<script setup lang="ts">
import { ref, computed } from 'vue'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Wifi, Server, Shield, Globe, Router } from 'lucide-vue-next'

interface TopologyNode {
  id: string
  label: string
  type: string
  status: string
}

interface TopologyLink {
  source: string
  target: string
  type: string
}

interface TopologyData {
  nodes: TopologyNode[]
  links: TopologyLink[]
}

const props = defineProps<{
  topology: TopologyData
  loading: boolean
}>()

// 获取节点图标
const getNodeIcon = (type: string) => {
  switch (type) {
    case 'edge':
      return Globe
    case 'firewall':
      return Shield
    case 'switch':
      return Router
    case 'server':
      return Server
    default:
      return Wifi
  }
}

// 获取状态颜色
const getStatusColor = (status: string) => {
  switch (status) {
    case 'online':
      return 'text-green-400'
    case 'offline':
      return 'text-red-400'
    default:
      return 'text-yellow-400'
  }
}

// 获取连接类型颜色
const getLinkColor = (type: string) => {
  switch (type) {
    case 'uplink':
      return 'stroke-cyan-500'
    case 'lan':
      return 'stroke-green-500'
    default:
      return 'stroke-gray-500'
  }
}
</script>

<template>
  <div class="h-full flex flex-col gap-4">
    <!-- 拓扑图区域 -->
    <Card class="flex-1 bg-card/40 backdrop-blur-sm border-border/20">
      <CardContent class="p-6 h-full flex items-center justify-center">
        <div class="text-center w-full">
          <Wifi class="w-16 h-16 text-green-400 mx-auto mb-4 animate-pulse" />
          <h3 class="text-lg font-semibold mb-2">网络拓扑结构</h3>
          <p class="text-sm text-muted-foreground mb-6">实时网络设备连接状态</p>
          
          <!-- 拓扑图模拟 -->
          <div class="relative w-full max-w-2xl mx-auto h-64 bg-gradient-to-br from-slate-800/30 to-slate-700/20 rounded-lg border border-border/20 p-4">
            <!-- 简单的拓扑连接线 -->
            <svg class="absolute inset-0 w-full h-full pointer-events-none">
              <!-- 互联网到防火墙 -->
              <line
                x1="20%"
                y1="20%"
                x2="50%"
                y2="20%"
                :class="getLinkColor('uplink')"
                stroke-width="2"
                stroke-dasharray="5,5"
                class="animate-pulse"
              />
              <!-- 防火墙到交换机 -->
              <line
                v-for="(_, idx) in Math.min(3, topology.nodes.filter(n => n.type === 'switch').length)"
                :key="idx"
                x1="50%"
                y1="20%"
                :x2="(30 + idx * 20) + '%'"
                y2="60%"
                :class="getLinkColor('lan')"
                stroke-width="2"
              />
            </svg>
            
            <!-- 节点 -->
            <div
              v-for="node in topology.nodes.slice(0, 6)"
              :key="node.id"
              class="absolute transform -translate-x-1/2 -translate-y-1/2"
              :style="{
                left: node.type === 'edge' ? '20%' : node.type === 'firewall' ? '50%' : node.type === 'switch' ? (30 + (topology.nodes.findIndex(n => n.id === node.id) % 3) * 20) + '%' : '50%',
                top: node.type === 'edge' || node.type === 'firewall' ? '20%' : '60%'
              }"
            >
              <div class="flex flex-col items-center">
                <div class="relative">
                  <component
                    :is="getNodeIcon(node.type)"
                    class="w-8 h-8"
                    :class="getStatusColor(node.status)"
                  />
                  <div
                    class="absolute -bottom-1 -right-1 w-3 h-3 rounded-full border-2 border-background"
                    :class="node.status === 'online' ? 'bg-green-500' : node.status === 'offline' ? 'bg-red-500' : 'bg-yellow-500'"
                  />
                </div>
                <span class="text-xs text-muted-foreground mt-1 max-w-20 truncate">{{ node.label }}</span>
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>

    <!-- 设备状态列表 -->
    <Card class="bg-card/40 backdrop-blur-sm border-border/20">
      <CardContent class="p-4">
        <h4 class="text-sm font-medium mb-3">设备状态</h4>
        <div class="grid grid-cols-2 gap-2">
          <div
            v-for="node in topology.nodes.slice(0, 4)"
            :key="node.id"
            class="flex items-center gap-2 p-2 rounded-lg bg-muted/20 border border-border/40"
          >
            <component :is="getNodeIcon(node.type)" class="w-4 h-4" :class="getStatusColor(node.status)" />
            <div class="flex-1 min-w-0">
              <p class="text-xs font-medium truncate">{{ node.label }}</p>
              <p class="text-xs text-muted-foreground capitalize">{{ node.type }}</p>
            </div>
            <Badge :variant="node.status === 'online' ? 'default' : 'destructive'" class="text-xs">
              {{ node.status === 'online' ? '在线' : '离线' }}
            </Badge>
          </div>
        </div>
      </CardContent>
    </Card>
  </div>
</template>
