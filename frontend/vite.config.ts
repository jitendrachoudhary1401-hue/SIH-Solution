import {defineConfig, loadEnv} from 'vite';
import react from '@vitejs/plugin-react';
import tailwind from '@tailwindcss/vite';
export default defineConfig(({mode}) => {
  const env = loadEnv(mode, process.cwd(), '');
  return {plugins:[react(),tailwind()],server:{host:env.FRONTEND_HOST || '127.0.0.1',port:Number(env.FRONTEND_PORT || 5173),proxy:{'/api':{target:env.API_PROXY_TARGET || 'http://127.0.0.1:5000',changeOrigin:false}}},build:{outDir:'dist',rollupOptions:{output:{manualChunks:{charts:['recharts'],vendor:['react','react-dom','react-router-dom','@tanstack/react-query']}}}}};
});
