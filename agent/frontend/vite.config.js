import { createLogger, defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const logger = createLogger()
const originalError = logger.error
const ignoredWsProxyErrors = [
  'ws proxy error',
  'ws proxy socket error',
  'ECONNRESET',
  'ECONNABORTED'
]

logger.error = (message, options) => {
  const text = String(message || '')
  if (
    ignoredWsProxyErrors.some((pattern) => text.includes(pattern)) &&
    (text.includes('ECONNRESET') || text.includes('ECONNABORTED'))
  ) {
    return
  }
  originalError.call(logger, message, options)
}

export default defineConfig({
  plugins: [vue()],
  customLogger: logger,
  server: {
    port: 3000,
    proxy: {
      '/projects': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        ws: true,
        configure: (proxy) => {
          proxy.on('error', (err) => {
            if (err.code === 'ECONNRESET' || err.code === 'ECONNABORTED') return
          })
          proxy.on('close', () => {})
        }
      },
      '/docs': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      },
      '/openapi.json': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      },
      '/settings': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      },
      // 仅转发后端 /eval/* API；浏览器页面使用 /workspace/*，避免与 API 同路径
      '/eval': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      }
    }
  }
})
