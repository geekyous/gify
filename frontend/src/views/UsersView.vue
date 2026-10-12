<script setup lang="ts">
/** 用户管理（管理员，FR-01 功能要求 5）：创建、编辑角色、重置密码、禁用。 */
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'

import type { Role, User } from '@/api/users'
import { createUser, listUsers, resetPassword, updateUser } from '@/api/users'
import { useAuthStore } from '@/stores/auth'
import { formatDateTime } from '@/utils/format'

const ROLE_OPTIONS: { value: Role; label: string }[] = [
  { value: 'admin', label: '管理员' },
  { value: 'builder', label: 'Agent 负责人' },
  { value: 'user', label: '普通用户' },
]
const ROLE_LABELS: Record<string, string> = Object.fromEntries(
  ROLE_OPTIONS.map((option) => [option.value, option.label]),
)

const auth = useAuthStore()

const loading = ref(false)
const users = ref<User[]>([])
const total = ref(0)
const query = reactive({ page: 1, pageSize: 20, orderBy: 'createdAt', order: 'desc' as const })

async function load() {
  loading.value = true
  try {
    const data = await listUsers(query)
    users.value = data.items
    total.value = data.total
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}

onMounted(load)

function isSelf(user: User) {
  return user.id === auth.user?.id
}

// ---- 创建 ----
const createVisible = ref(false)
const createFormRef = ref<FormInstance>()
const createSubmitting = ref(false)
const createForm = reactive({
  username: '',
  displayName: '',
  role: 'user' as Role,
  password: '',
})
const createRules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 50, message: '长度 2–50 字符', trigger: 'blur' },
  ],
  displayName: [{ max: 50, message: '最长 50 字符', trigger: 'blur' }],
  password: [{ min: 8, max: 128, message: '长度 8–128 位', trigger: 'blur' }],
}

function openCreate() {
  createVisible.value = true
}

async function submitCreate() {
  const valid = await createFormRef.value?.validate().catch(() => false)
  if (!valid) return
  createSubmitting.value = true
  try {
    const user = await createUser({
      username: createForm.username,
      displayName: createForm.displayName || null,
      role: createForm.role,
      password: createForm.password || undefined,
    })
    createVisible.value = false
    if (user.initialPassword) {
      await showInitialPassword(`${user.username} 的初始密码`, user.initialPassword)
    } else {
      ElMessage.success('用户已创建')
    }
    await load()
  } catch {
    // 拦截器已提示
  } finally {
    createSubmitting.value = false
  }
}

function onCreateClosed() {
  createFormRef.value?.resetFields()
  createForm.username = ''
  createForm.displayName = ''
  createForm.password = ''
}

// ---- 初始密码展示 ----
const initialPasswordState = reactive({
  visible: false,
  title: '',
  value: '',
})

async function showInitialPassword(title: string, password: string) {
  initialPasswordState.title = title
  initialPasswordState.value = password
  initialPasswordState.visible = true
}

async function copyInitialPassword() {
  await navigator.clipboard.writeText(initialPasswordState.value)
  ElMessage.success('已复制')
}

// ---- 编辑 ----
const editVisible = ref(false)
const editFormRef = ref<FormInstance>()
const editSubmitting = ref(false)
const editing = ref<User | null>(null)
const editForm = reactive({ displayName: '', role: 'user' as Role, enabled: true })

function openEdit(user: User) {
  editing.value = user
  editForm.displayName = user.displayName ?? ''
  editForm.role = user.role
  editForm.enabled = user.enabled
  editVisible.value = true
}

async function submitEdit() {
  if (!editing.value) return
  const valid = await editFormRef.value?.validate().catch(() => false)
  if (!valid) return
  editSubmitting.value = true
  try {
    await updateUser(editing.value.id, {
      displayName: editForm.displayName || null,
      role: editForm.role,
      enabled: editForm.enabled,
    })
    editVisible.value = false
    ElMessage.success('已保存')
    await load()
  } catch {
    // 拦截器已提示
  } finally {
    editSubmitting.value = false
  }
}

// ---- 重置密码 / 禁用 ----
async function confirmBox(message: string, title: string): Promise<boolean> {
  try {
    await ElMessageBox.confirm(message, title, { type: 'warning' })
    return true
  } catch {
    return false
  }
}

async function handleResetPassword(user: User) {
  const ok = await confirmBox(
    `重置 ${user.username} 的密码？其全部在线会话将失效。`,
    '重置密码',
  )
  if (!ok) return
  const result = await resetPassword(user.id)
  await showInitialPassword(`${user.username} 的新初始密码`, result.initialPassword)
}

async function handleToggleEnabled(user: User) {
  const action = user.enabled ? '禁用' : '启用'
  const ok = await confirmBox(
    `${action}用户 ${user.username}？${user.enabled ? '禁用后其在线会话立即失效。' : ''}`,
    `${action}用户`,
  )
  if (!ok) return
  await updateUser(user.id, { enabled: !user.enabled })
  ElMessage.success(`已${action}`)
  await load()
}
</script>

<template>
  <div>
    <div class="toolbar">
      <h3>用户管理</h3>
      <el-button type="primary" @click="openCreate">创建用户</el-button>
    </div>

    <el-table v-loading="loading" :data="users">
      <el-table-column prop="username" label="用户名" width="160" />
      <el-table-column prop="displayName" label="显示名" width="160">
        <template #default="{ row }">{{ row.displayName || '—' }}</template>
      </el-table-column>
      <el-table-column prop="role" label="角色" width="130">
        <template #default="{ row }">
          <el-tag :type="row.role === 'admin' ? 'danger' : row.role === 'builder' ? 'warning' : 'info'">
            {{ ROLE_LABELS[row.role] }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="enabled" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.enabled ? 'success' : 'danger'">
            {{ row.enabled ? '启用' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="createdAt" label="创建时间" width="170">
        <template #default="{ row }">{{ formatDateTime(row.createdAt) }}</template>
      </el-table-column>
      <el-table-column label="操作" min-width="220">
        <template #default="{ row }">
          <el-button link type="primary" :disabled="isSelf(row)" @click="openEdit(row)">
            编辑
          </el-button>
          <el-button link type="primary" @click="handleResetPassword(row)">重置密码</el-button>
          <el-button
            link
            :type="row.enabled ? 'danger' : 'success'"
            :disabled="isSelf(row)"
            @click="handleToggleEnabled(row)"
          >
            {{ row.enabled ? '禁用' : '启用' }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      class="pagination"
      layout="total, prev, pager, next, sizes"
      :total="total"
      :current-page="query.page"
      :page-size="query.pageSize"
      :page-sizes="[20, 50, 100]"
      @current-change="(page: number) => { query.page = page; load() }"
      @size-change="(size: number) => { query.pageSize = size; query.page = 1; load() }"
    />

    <!-- 创建用户 -->
    <el-dialog v-model="createVisible" title="创建用户" width="440px" @closed="onCreateClosed">
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-width="80px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="createForm.username" autocomplete="off" />
        </el-form-item>
        <el-form-item label="显示名" prop="displayName">
          <el-input v-model="createForm.displayName" />
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-select v-model="createForm.role">
            <el-option
              v-for="option in ROLE_OPTIONS"
              :key="option.value"
              :value="option.value"
              :label="option.label"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="初始密码" prop="password">
          <el-input
            v-model="createForm.password"
            type="password"
            show-password
            autocomplete="new-password"
            placeholder="留空则自动生成"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="createSubmitting" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- 编辑用户 -->
    <el-dialog v-model="editVisible" :title="`编辑：${editing?.username ?? ''}`" width="440px">
      <el-form ref="editFormRef" :model="editForm" label-width="80px">
        <el-form-item label="显示名">
          <el-input v-model="editForm.displayName" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="editForm.role" :disabled="isSelf(editing!)">
            <el-option
              v-for="option in ROLE_OPTIONS"
              :key="option.value"
              :value="option.value"
              :label="option.label"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="editForm.enabled" active-text="启用" inactive-text="禁用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="editSubmitting" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 初始密码展示（仅一次） -->
    <el-dialog v-model="initialPasswordState.visible" :title="initialPasswordState.title" width="420px">
      <el-alert
        type="warning"
        :closable="false"
        title="请立即复制保存，关闭后无法再次查看"
        style="margin-bottom: 12px"
      />
      <el-input :model-value="initialPasswordState.value" readonly>
        <template #append>
          <el-button @click="copyInitialPassword">复制</el-button>
        </template>
      </el-input>
    </el-dialog>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.toolbar h3 {
  margin: 0;
}

.pagination {
  margin-top: 12px;
  justify-content: flex-end;
}
</style>
