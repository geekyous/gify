<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import type { FormInstance, FormRules } from 'element-plus'

import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

const formRef = ref<FormInstance>()
const submitting = ref(false)
const form = ref({ username: '', password: '' })

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    // 首登强制改密由 MainLayout 的 watchEffect 接管
    await auth.login(form.value.username, form.value.password)
    await router.push('/home')
  } catch {
    // 错误提示由 request.ts 拦截器统一弹出
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <el-card class="login-card">
      <h2 class="title">Gify</h2>
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        @keyup.enter="submit"
      >
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" autocomplete="username" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            autocomplete="current-password"
          />
        </el-form-item>
        <el-button
          type="primary"
          class="submit"
          :loading="submitting"
          @click="submit"
        >
          登录
        </el-button>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.login-page {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--el-fill-color-light);
}

.login-card {
  width: 360px;
}

.title {
  text-align: center;
  margin: 0 0 20px;
  letter-spacing: 4px;
}

.submit {
  width: 100%;
}
</style>
