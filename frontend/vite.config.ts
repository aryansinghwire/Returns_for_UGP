import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

// The dev server passes every /api request on to the backend on port 8000.
// There's deliberately no cookieDomainRewrite. The login cookie doesn't name a
// domain, so the browser ties it to localhost:5173 and sends it back
// correctly. Rewriting the cookie's domain here is what would break login.
const apiProxy = {
  '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
}

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { proxy: apiProxy },
  // `npm run preview` used to have no proxy, so every /api request failed.
  // That didn't matter before there was a login, but afterwards it looked like
  // "login is broken in the built website".
  preview: { proxy: apiProxy },
})
