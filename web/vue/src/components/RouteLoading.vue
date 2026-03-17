<template>
  <div class="route-loading" role="status" aria-live="polite" aria-busy="true">
    <div class="route-loading__inner">
      <span class="route-loading__spinner" />
      <div class="route-loading__bar">
        <span class="route-loading__bar-fill" />
      </div>
      <p class="route-loading__text">页面加载中...</p>
    </div>
  </div>
</template>

<style scoped>
.route-loading {
  min-height: 240px;
  width: 100%;
  display: grid;
  place-items: center;
}

.route-loading__inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  color: hsl(var(--muted-foreground));
}

.route-loading__spinner {
  width: 28px;
  height: 28px;
  border: 3px solid hsl(var(--border));
  border-top-color: var(--route-loading-accent);
  border-radius: 9999px;
  animation: route-spin 0.7s linear infinite;
}

.route-loading__bar {
  width: min(220px, 60vw);
  height: 4px;
  border-radius: 9999px;
  overflow: hidden;
  background: hsl(var(--border));
}

.route-loading__bar-fill {
  display: block;
  width: 40%;
  height: 100%;
  border-radius: 9999px;
  background: var(--route-loading-accent);
  animation: route-bar 1s ease-in-out infinite;
}

.route-loading__text {
  font-size: 13px;
  letter-spacing: 0.02em;
}

:global(html) .route-loading {
  --route-loading-accent: #111111;
}

:global(html.dark) .route-loading {
  --route-loading-accent: #ffffff;
}

@keyframes route-spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes route-bar {
  0% {
    transform: translateX(-120%);
  }

  50% {
    transform: translateX(140%);
  }

  100% {
    transform: translateX(260%);
  }
}
</style>
