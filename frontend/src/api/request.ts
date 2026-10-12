/**
 * HTTP 客户端单例（开发规范 7.4）。
 * 统一解包信封：code === 0 返回 data；HTTP 401 跳登录页；
 * code !== 0 弹出 message 并 reject；网络错误统一提示。
 */
import { ElMessage } from 'element-plus'

export class ApiError extends Error {
  code: number
  fieldErrors: Record<string, string> | null

  constructor(code: number, message: string, fieldErrors: Record<string, string> | null) {
    super(message)
    this.code = code
    this.fieldErrors = fieldErrors
  }
}

interface Envelope<T> {
  code: number
  message: string
  data: T
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  let resp: Response
  try {
    resp = await fetch(`/api${path}`, {
      method,
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    ElMessage.error('网络错误，请检查服务是否可用')
    throw new ApiError(-1, '网络错误', null)
  }

  if (resp.status === 401 && path !== '/auth/login') {
    window.location.assign('/login')
    throw new ApiError(2003, '未登录或会话已失效', null)
  }

  let payload: Envelope<T>
  try {
    payload = (await resp.json()) as Envelope<T>
  } catch {
    ElMessage.error(`响应格式错误（HTTP ${resp.status}）`)
    throw new ApiError(-1, '响应格式错误', null)
  }

  if (payload.code !== 0) {
    const fieldErrors =
      resp.status === 422 && payload.data && typeof payload.data === 'object'
        ? (payload.data as Record<string, string>)
        : null
    if (fieldErrors) {
      const first = Object.values(fieldErrors)[0]
      ElMessage.error(first ?? payload.message)
    } else {
      ElMessage.error(payload.message)
    }
    throw new ApiError(payload.code, payload.message, fieldErrors)
  }
  return payload.data
}

export const http = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),
  patch: <T>(path: string, body?: unknown) => request<T>('PATCH', path, body),
  delete: <T>(path: string) => request<T>('DELETE', path),
}
