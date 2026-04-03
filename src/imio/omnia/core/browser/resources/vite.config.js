// vite.config.js
import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
import svgr from 'vite-plugin-svgr';

export default defineConfig({
  plugins: [svgr(),react()],
  root: './src',

  build: {
    outDir: 'dist',
    manifest: true,
    rollupOptions: {
      input: 'src/index.jsx',
      output: {
        chunkFileNames: '[name].js',
        entryFileNames: '[name].js',
        assetFileNames: '[name].[ext]'
      }
    }
  },
  server: {
    port: 3333,
    open: false
  }
});
