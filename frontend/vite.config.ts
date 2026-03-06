import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { copyFileSync, readdirSync, watchFile } from 'fs'
import { resolve, join } from 'path'

const CONFIG_SRC = resolve(__dirname, '../src/config')
const CONFIG_DEST = resolve(__dirname, 'public')

function syncConfigs() {
  readdirSync(CONFIG_SRC)
    .filter(f => f.endsWith('.json'))
    .forEach(f => copyFileSync(join(CONFIG_SRC, f), join(CONFIG_DEST, f)))
}

function configSyncPlugin() {
  return {
    name: 'config-sync',
    buildStart() {
      syncConfigs()
    },
    configureServer() {
      syncConfigs()
      readdirSync(CONFIG_SRC)
        .filter(f => f.endsWith('.json'))
        .forEach(f => {
          watchFile(join(CONFIG_SRC, f), () => {
            copyFileSync(join(CONFIG_SRC, f), join(CONFIG_DEST, f))
            console.log(`[config-sync] Copied ${f} → public/`)
          })
        })
    },
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), configSyncPlugin()],
})
