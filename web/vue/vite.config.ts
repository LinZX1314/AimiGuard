import { defineConfig } from 'vite'
import { loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const proxyTarget = (env.VITE_PROXY_TARGET || 'http://127.0.0.1:5000').trim()

  return {
    plugins: [
      vue(),
    ],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url))
      }
    },
    server: {
      port: 3001,
      proxy: {
        '/api': {
          target: proxyTarget,
          changeOrigin: true,
          // 对流式接口禁用代理缓冲，确保 SSE chunk 实时透传
          bypass(req) {
            // 返回 undefined 表示走代理；仅用于附加日志
            return undefined
          },
          configure: (proxy) => {
            // 方便在 dev 终端直接确认请求是否被转发到后端。
            proxy.on('proxyReq', (proxyReq, req) => {
              const forwardedPath = proxyReq.path || req.url || ''
              console.log(`[proxy] ${req.method} ${req.url} -> ${proxyTarget}${forwardedPath}`)
              // 流式接口：禁用代理侧缓冲
              if ((req.url || '').includes('/chat/stream')) {
                proxyReq.setHeader('X-Accel-Buffering', 'no')
              }
            })
            proxy.on('proxyRes', (proxyRes, req) => {
              // 透传 SSE 必要响应头，防止 Vite 代理层缓冲
              if ((req.url || '').includes('/chat/stream')) {
                proxyRes.headers['cache-control'] = 'no-cache'
                proxyRes.headers['x-accel-buffering'] = 'no'
              }
            })
          }
        }
      }
    },
    build: {
      outDir: '../static/vue-dist',
      emptyOutDir: true,
      chunkSizeWarningLimit: 600,
      rollupOptions: {
        output: {
          manualChunks: {
            'echarts': ['echarts', 'vue-echarts'],
          }
        }
      }
    }
  }
})
