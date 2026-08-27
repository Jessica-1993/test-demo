import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

const apiProxyTarget = process.env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8000'
const wsProxyTarget = apiProxyTarget.replace(/^http/, 'ws')

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 3000,
    host: '0.0.0.0',
    proxy: {
      '^/api/': {
        target: apiProxyTarget,
        changeOrigin: true,
        secure: false,
      },
      '^/ws/': {
        target: wsProxyTarget,
        ws: true,
        changeOrigin: true,
      },
    },
  },
})
