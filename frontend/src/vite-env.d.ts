/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** API 基址：开发默认空（走 Vite 代理），生产构建时注入 */
  readonly VITE_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
