import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Certificati locali generati con mkcert (frontend/.certs/, non versionati) per poter
// testare da un telefono in LAN: getUserMedia (fotocamera) richiede un contesto sicuro
// (HTTPS), http://<ip-lan> non basta. Se i certificati non esistono, vite parte comunque
// in HTTP semplice (uso da browser desktop su localhost).
const certFile = resolve(import.meta.dirname, '.certs/dev-cert.pem')
const keyFile = resolve(import.meta.dirname, '.certs/dev-key.pem')
const httpsConfig =
  existsSync(certFile) && existsSync(keyFile)
    ? { cert: readFileSync(certFile), key: readFileSync(keyFile) }
    : undefined

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true,
    port: 5173,
    https: httpsConfig,
    proxy: {
      // il frontend chiama /api/*, vite lo inoltra server-to-server al backend: il
      // browser parla solo con l'origine HTTPS del frontend, niente mixed-content
      // (HTTPS -> HTTP) né bisogno di configurare CORS per l'IP della LAN.
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
