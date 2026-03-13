import { defineConfig } from 'vite'
import { loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import vuetify from 'vite-plugin-vuetify'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const proxyTarget = (env.VITE_PROXY_TARGET || 'http://127.0.0.1:5000').trim()

  return {
    plugins: [
      vue(),
      vuetify({ autoImport: true })
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
          configure: (proxy) => {
            // 方便在 dev 终端直接确认请求是否被转发到后端。
            proxy.on('proxyReq', (proxyReq, req) => {
              const forwardedPath = proxyReq.path || req.url || ''
              console.log(`[proxy] ${req.method} ${req.url} -> ${proxyTarget}${forwardedPath}`)
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
            'vuetify': ['vuetify'],
          }
        }
      }
    }
  }
})
