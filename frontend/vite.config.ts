import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

/**
 * 开发环境：Vite 直接把 /api 与 /ws 代理到本地 FastAPI (127.0.0.1:18080)
 * 生产环境：Nginx 提供静态文件并反代 /api/。
 *
 * 注意：这里刻意不引入 node:url / node:path，避免为了一个路径别名
 * 额外引入 @types/node 依赖（路径别名在 tsconfig.json 中已声明，
 * 使用相对导入即可，无需 vite 端重复配置）。
 */
export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 15173,
    strictPort: false,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:18080',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    chunkSizeWarningLimit: 1200,
    rollupOptions: {
      output: {
        manualChunks: {
          echarts: ['echarts'],
          react: ['react', 'react-dom'],
        },
      },
    },
  },
})
