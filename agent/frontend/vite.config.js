import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 3000,
    proxy: {
      '/projects': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        ws: true
      },
      '/docs': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      },
      '/openapi.json': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      }
    }
  }
})
