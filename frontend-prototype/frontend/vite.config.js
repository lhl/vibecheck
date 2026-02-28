import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'
import { svelteTesting } from '@testing-library/svelte/vite'

export default defineConfig({
  plugins: [svelte(), svelteTesting()],
  server: {
    host: '0.0.0.0',
    port: 5178,
    allowedHosts: ['hilario-femoral-verda.ngrok-free.dev'],
    proxy: {
      '/api': {
        target: 'http://localhost:8780',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.js'],
    include: ['./src/**/*.test.js'],
  },
})
