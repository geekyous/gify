/** 用户管理接口（管理员，对应后端 /api/users/*）。 */
import type { Role } from './auth'
import { http } from './request'

export type { Role }

export interface User {
  id: string
  username: string
  displayName: string | null
  role: Role
  enabled: boolean
  mustChangePassword: boolean
  createdAt: string
}

export interface UserCreateResult extends User {
  initialPassword: string | null
}

export interface Page<T> {
  items: T[]
  total: number
  page: number
  pageSize: number
}

export interface UserQuery {
  page: number
  pageSize: number
  orderBy: string
  order: 'asc' | 'desc'
}

export function listUsers(query: UserQuery) {
  const params = new URLSearchParams({
    page: String(query.page),
    pageSize: String(query.pageSize),
    orderBy: query.orderBy,
    order: query.order,
  })
  return http.get<Page<User>>(`/users?${params.toString()}`)
}

export function createUser(data: {
  username: string
  displayName?: string | null
  role: Role
  password?: string
}) {
  return http.post<UserCreateResult>('/users', data)
}

export function updateUser(
  id: string,
  data: { displayName?: string | null; role?: Role; enabled?: boolean },
) {
  return http.patch<User>(`/users/${id}`, data)
}

export function resetPassword(id: string, newPassword?: string) {
  return http.post<{ initialPassword: string }>(`/users/${id}/reset-password`, {
    newPassword,
  })
}
