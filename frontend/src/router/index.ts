/** 路由与守卫：登录态与角色集中处理 */
import { createRouter, createWebHistory } from 'vue-router'
import { ElMessage } from 'element-plus'

import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
    },
    {
      path: '/',
      component: () => import('@/layouts/MainLayout.vue'),
      redirect: '/home',
      children: [
        {
          path: 'home',
          name: 'home',
          component: () => import('@/views/HomeView.vue'),
        },
        {
          path: 'users',
          name: 'users',
          component: () => import('@/views/UsersView.vue'),
          meta: { roles: ['admin'] },
        },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/home' },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()

  if (to.name === 'login') {
    return auth.user ? { path: '/home' } : true
  }

  if (!auth.user) {
    try {
      await auth.fetchUser()
    } catch {
      return { path: '/login' }
    }
  }

  const roles = to.meta.roles as string[] | undefined
  if (roles && auth.user && !roles.includes(auth.user.role)) {
    ElMessage.warning('没有访问该页面的权限')
    return { path: '/home' }
  }
  return true
})

export default router
