/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Backend origin baked into native builds, e.g. http://192.168.0.9:8000 */
  readonly VITE_API_BASE?: string;
}
