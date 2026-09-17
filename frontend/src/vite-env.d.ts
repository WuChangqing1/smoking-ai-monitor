/// <reference types="vite/client" />

/**
 * Vite 环境变量类型声明。
 *
 * 只声明本项目实际用到的变量，避免引入额外的 @types 依赖。
 */
interface ImportMetaEnv {
  /** 后端 API 基地址；留空表示走同源 /api（开发由 Vite 代理，生产由 Nginx 反代） */
  readonly VITE_API_BASE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
