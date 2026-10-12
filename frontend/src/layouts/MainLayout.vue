<script setup lang="ts">
/** 主布局：侧边导航（按角色过滤）+ 顶栏（用户信息、修改密码、退出）。 */
import { computed, ref, watchEffect } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'

import ChangePasswordDialog from '@/components/ChangePasswordDialog.vue'
import { useAuthStore } from '@/stores/auth'

const ROLE_LABELS: Record<string, string> = {
  admin: '管理员',
  builder: 'Agent 负责人',
  user: '普通用户',
}

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const activeMenu = computed(() => `/${String(route.path.split('/')[1] ?? 'home')}`)

const menus = computed(() => {
  const items = [{ path: '/home', title: '首页' }]
  if (auth.user?.role === 'admin') {
    items.push({ path: '/users', title: '用户管理' })
  }
  return items
})

const changePasswordVisible = ref(false)

watchEffect(() => {
  // 首登 / 重置密码后强制修改（FR-01 要求 3）
  if (auth.user?.mustChangePassword) {
    changePasswordVisible.value = true
  }
})

async function handleLogout() {
  try {
    await ElMessageBox.confirm('确定退出登录？', '提示', { type: 'warning' })
  } catch {
    return
  }
  await auth.logout()
  await router.push('/login')
}
</script>

<template>
  <el-container class="main-layout">
    <el-aside width="200px" class="aside">
      <div class="brand">Gify</div>
      <el-menu :default-active="activeMenu" router>
        <el-menu-item v-for="item in menus" :key="item.path" :index="item.path">
          {{ item.title }}
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <span />
        <div class="header-right">
          <span class="user-info">
            {{ auth.user?.displayName || auth.user?.username }}
            <el-tag size="small" type="info">{{ ROLE_LABELS[auth.user?.role ?? ''] }}</el-tag>
          </span>
          <el-button link @click="changePasswordVisible = true">修改密码</el-button>
          <el-button link type="danger" @click="handleLogout">退出</el-button>
        </div>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>

  <ChangePasswordDialog
    v-model="changePasswordVisible"
    :forced="auth.user?.mustChangePassword ?? false"
  />
</template>

<style scoped>
.main-layout {
  height: 100%;
}

.aside {
  border-right: 1px solid var(--el-border-color-light);
}

.brand {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  font-weight: 600;
  letter-spacing: 2px;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--el-border-color-light);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 4px;
}

.user-info {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-right: 8px;
}
</style>
