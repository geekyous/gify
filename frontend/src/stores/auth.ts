/** 登录态与当前用户（服务端数据缓存进 Pinia，开发规范 7.3.3）。 */
import { defineStore } from 'pinia'
import { ref } from 'vue'

import {
  changePassword as apiChangePassword,
  getMe,
  login as apiLogin,
  logout as apiLogout,
  type SessionUser,
} from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<SessionUser | null>(null)

  async function login(username: string, password: string) {
    user.value = await apiLogin(username, password)
  }

  async function fetchUser() {
    user.value = await getMe()
  }

  async function logout() {
    try {
      await apiLogout()
    } finally {
      user.value = null
    }
  }

  async function changePassword(oldPassword: string, newPassword: string) {
    // 成功后服务端已销毁全部会话，前端清空本地态
    await apiChangePassword(oldPassword, newPassword)
    user.value = null
  }

  return { user, login, fetchUser, logout, changePassword }
})
