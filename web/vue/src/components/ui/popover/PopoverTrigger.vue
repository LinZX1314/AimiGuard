<script setup lang="ts">
import type { PopoverTriggerProps } from "reka-ui"
import { PopoverTrigger as PopoverTriggerPrimitive, useForwardProps } from "reka-ui"

const props = defineProps<PopoverTriggerProps>()
const forwarded = useForwardProps(props)
</script>

<template>
  <PopoverTriggerPrimitive v-bind="forwarded">
    <slot />
  </PopoverTriggerPrimitive>
</template>
