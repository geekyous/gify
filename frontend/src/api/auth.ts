/** 认证接口（对应后端 /api/auth/*）。 */
import { http } from './request'

export type Role = 'admin' | 'builder' | 'user'

export interface SessionUser {
  id: string
  username: string
  displayName: string | null
  role: Role
  mustChangePassword: boolean
}

export function login(username: string, password: string) {
  return http.post<SessionUser>('/auth/login', { username, password })
}

export function logout() {
  return http.post<null>('/auth/logout')
}

export function getMe() {
  return http.get<SessionUser>('/auth/me')
}

export function changePassword(oldPassword: string, newPassword: string) {
  return http.post<null>('/auth/change-password', { oldPassword, newPassword })
}
