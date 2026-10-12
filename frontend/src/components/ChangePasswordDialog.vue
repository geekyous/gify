<script setup lang="ts">
/**
 * 修改密码对话框：顶栏主动修改与首登强制修改共用。
 * 成功后服务端销毁全部会话，跳转登录页重新登录。
 */
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'

import { useAuthStore } from '@/stores/auth'

const props = defineProps<{ forced: boolean }>()

const router = useRouter()
const auth = useAuthStore()

const visible = defineModel<boolean>({ required: true })
const formRef = ref<FormInstance>()
const submitting = ref(false)
const form = ref({ oldPassword: '', newPassword: '', confirmPassword: '' })

const rules: FormRules = {
  oldPassword: [{ required: true, message: '请输入原密码', trigger: 'blur' }],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 8, max: 128, message: '长度 8–128 位', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    {
      validator: (_rule, value: string, callback) => {
        if (value !== form.value.newPassword) callback(new Error('两次输入不一致'))
        else callback()
      },
      trigger: 'blur',
    },
  ],
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    await auth.changePassword(form.value.oldPassword, form.value.newPassword)
    visible.value = false
    ElMessage.success('密码已修改，请重新登录')
    await router.push('/login')
  } catch {
    // 失败提示由 request.ts 拦截器统一弹出
  } finally {
    submitting.value = false
  }
}

function onClosed() {
  form.value = { oldPassword: '', newPassword: '', confirmPassword: '' }
  formRef.value?.resetFields()
}
</script>

<template>
  <el-dialog
    v-model="visible"
    :title="props.forced ? '首次登录，请修改密码' : '修改密码'"
    :close-on-click-modal="!props.forced"
    :close-on-press-escape="!props.forced"
    :show-close="!props.forced"
    width="420px"
    @closed="onClosed"
  >
    <el-alert
      v-if="props.forced"
      type="warning"
      :closable="false"
      title="当前使用初始密码，修改后才能继续使用平台"
      style="margin-bottom: 16px"
    />
    <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
      <el-form-item label="原密码" prop="oldPassword">
        <el-input v-model="form.oldPassword" type="password" show-password />
      </el-form-item>
      <el-form-item label="新密码" prop="newPassword">
        <el-input v-model="form.newPassword" type="password" show-password />
      </el-form-item>
      <el-form-item label="确认新密码" prop="confirmPassword">
        <el-input v-model="form.confirmPassword" type="password" show-password />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button type="primary" :loading="submitting" @click="submit">提交</el-button>
    </template>
  </el-dialog>
</template>
