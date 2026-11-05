<script setup lang="ts">
/** 首页占位：Agent 使用入口在 M3 开发 */
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
</script>

<template>
  <el-empty description="Agent 使用入口将在 M3 上线，请先联系管理员配置平台">
    <template #image>
      <div style="font-size: 48px">💬</div>
    </template>
  </el-empty>
  <p v-if="auth.user?.role === 'admin'" class="hint">
    管理员可先前往 <router-link to="/users">用户管理</router-link> 创建账号。
  </p>
</template>

<style scoped>
.hint {
  text-align: center;
  color: var(--el-text-color-secondary);
}
</style>
