<script setup lang="ts">




import type { HTMLAttributes } from 'vue'




import { cn } from '@/lib/utils'









const props = defineProps<{




  class?: HTMLAttributes['class']




}>()




</script>









<template>




  <div




    :class="




      cn(




        'relative rounded-xl border text-card-foreground backdrop-blur-2xl transition-all duration-500',









        /* Light mode base */




        'bg-gradient-to-br from-card/78 via-secondary/42 to-muted/28 border-border/85 shadow-[0_10px_22px_rgba(60,76,99,0.14)]',




        /* Light mode hover */




        'hover:border-primary/25 hover:from-card/84 hover:via-secondary/46 hover:to-muted/34 hover:shadow-[0_14px_28px_rgba(60,76,99,0.16)]',









        /* Dark mode base */




        'dark:bg-gradient-to-br dark:from-slate-900/60 dark:to-slate-900/20 dark:border-white/[0.08] dark:shadow-[0_8px_32px_rgba(0,0,0,0.4)]',




        /* Dark mode hover */




        'dark:hover:from-slate-800/80 dark:hover:to-slate-900/40 dark:hover:border-primary/40 dark:hover:shadow-[0_0_30px_rgba(59,130,246,0.15)]',









        /* Inner rim lighting */




        'after:pointer-events-none after:absolute after:inset-0 after:rounded-xl after:border after:border-primary/10 after:mix-blend-overlay dark:after:border-white/5',









        props.class,




      )




    "




  >




    <slot />




  </div>




</template>



