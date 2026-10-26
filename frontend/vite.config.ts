import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
import tailwind from '@tailwindcss/vite';
export default defineConfig({plugins:[react(),tailwind()],server:{port:5173,proxy:{'/api':{target:'http://127.0.0.1:5000',changeOrigin:false}}},build:{outDir:'dist',rollupOptions:{output:{manualChunks:{charts:['recharts'],vendor:['react','react-dom','react-router-dom','@tanstack/react-query']}}}}});
