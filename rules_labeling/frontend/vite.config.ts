import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const apiProxy = process.env.VITE_API_PROXY ?? 'http://127.0.0.1:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Large list endpoints (~11 MB, ~12 s while the DB lock serializes)
      // were getting "socket hang up" on the default proxy. Explicit long
      // timeouts + agent:false (no keep-alive pooling) keep the pipe open
      // for the full response.
      '/api': {
        target: apiProxy,
        changeOrigin: true,
        proxyTimeout: 600_000,
        timeout: 600_000,
        agent: false,
      },
    },
  },
  test: {
    environment: 'jsdom',
    exclude: ['node_modules/**', 'dist/**', 'tests/e2e/**'],
    setupFiles: './src/test/setup.ts',
  },
});
