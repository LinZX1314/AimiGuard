<script setup lang="ts">
import { computed } from 'vue'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-vue-next'

interface Props {
  page: number
  pageSize: number
  total: number
  pageSizes?: number[]
}

const props = withDefaults(defineProps<Props>(), {
  pageSizes: () => [50, 100, 200, 500, 1000]
})

const emit = defineEmits<{
  (e: 'update:page', value: number): void
  (e: 'update:pageSize', value: number): void
}>()

const totalPages = computed(() => Math.ceil(props.total / props.pageSize) || 1)

const startItem = computed(() => (props.page - 1) * props.pageSize + 1)
const endItem = computed(() => Math.min(props.page * props.pageSize, props.total))

const pages = computed(() => {
  const result: (number | string)[] = []
  const current = props.page
  const total = totalPages.value

  if (total <= 7) {
    for (let i = 1; i <= total; i++) result.push(i)
  } else {
    result.push(1)
    if (current > 3) result.push('...')

    const start = Math.max(2, current - 1)
    const end = Math.min(total - 1, current + 1)

    for (let i = start; i <= end; i++) result.push(i)

    if (current < total - 2) result.push('...')
    result.push(total)
  }
  return result
})

function goToPage(p: number) {
  if (p >= 1 && p <= totalPages.value) {
    emit('update:page', p)
  }
}

function handlePageSizeChange(val: unknown) {
  // Select 的值类型是 AcceptableValue，这里统一做字符串化处理
  if (val === null || val === undefined) return
  emit('update:pageSize', Number(String(val)))
  emit('update:page', 1) // Reset to first page when page size changes
}
</script>

<template>
  <div class="flex flex-col sm:flex-row items-center justify-between gap-4 px-4 py-3 bg-muted/5 border-t border-border/20">
    <div class="flex items-center gap-4 text-sm text-muted-foreground">
      <span>共 <span class="font-semibold text-foreground">{{ total }}</span> 条记录</span>
      <span v-if="total > 0">
        第 <span class="font-semibold text-foreground">{{ startItem }}</span>-<span class="font-semibold text-foreground">{{ endItem }}</span> 条
      </span>
    </div>

    <div class="flex items-center gap-4">
      <div class="flex items-center gap-2">
        <span class="text-xs text-muted-foreground">每页</span>
        <Select :model-value="String(pageSize)" @update:model-value="handlePageSizeChange">
          <SelectTrigger class="w-20 h-8 bg-black/20 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem v-for="size in pageSizes" :key="size" :value="String(size)">{{ size }}</SelectItem>
          </SelectContent>
        </Select>
        <span class="text-xs text-muted-foreground">条</span>
      </div>

      <div class="flex items-center gap-1">
        <Button variant="ghost" size="icon" class="h-8 w-8" :disabled="page === 1" @click="goToPage(1)">
          <ChevronsLeft class="h-4 w-4" />
        </Button>
        <Button variant="ghost" size="icon" class="h-8 w-8" :disabled="page === 1" @click="goToPage(page - 1)">
          <ChevronLeft class="h-4 w-4" />
        </Button>

        <template v-for="(p, idx) in pages" :key="idx">
          <span v-if="p === '...'" class="px-2 text-muted-foreground text-xs">...</span>
          <Button v-else variant="ghost" size="icon" class="h-8 w-8" :class="{ 'bg-primary text-primary-foreground hover:bg-primary': p === page }" @click="goToPage(p as number)">
            {{ p }}
          </Button>
        </template>

        <Button variant="ghost" size="icon" class="h-8 w-8" :disabled="page === totalPages" @click="goToPage(page + 1)">
          <ChevronRight class="h-4 w-4" />
        </Button>
        <Button variant="ghost" size="icon" class="h-8 w-8" :disabled="page === totalPages" @click="goToPage(totalPages)">
          <ChevronsRight class="h-4 w-4" />
        </Button>
      </div>
    </div>
  </div>
</template>