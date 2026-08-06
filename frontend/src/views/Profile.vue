<template>
  <div class="profile-page">
    <el-header class="page-header">
      <div class="header-left">
        <el-button @click="$router.push('/chat')" :icon="ArrowLeft" circle />
        <h2>个人中心</h2>
      </div>
      <div class="header-right">
        <el-tag v-if="authStore.isAdmin" type="danger">管理员</el-tag>
        <el-button @click="authStore.logout(); $router.push('/login')" type="danger" plain>
          退出登录
        </el-button>
      </div>
    </el-header>

    <el-main class="page-main">
      <el-card class="profile-card">
        <template #header>
          <span>个人信息</span>
        </template>
        <el-descriptions :column="1" border>
          <el-descriptions-item label="用户名">{{ authStore.username }}</el-descriptions-item>
          <el-descriptions-item label="角色">{{ authStore.isAdmin ? '管理员' : '普通用户' }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card class="profile-card" style="margin-top: 20px">
        <template #header>
          <span>修改密码</span>
        </template>
        <el-form ref="formRef" :model="form" :rules="rules" label-width="100px" style="max-width: 500px">
          <el-form-item label="原密码" prop="oldPassword">
            <el-input v-model="form.oldPassword" type="password" show-password />
          </el-form-item>
          <el-form-item label="新密码" prop="newPassword">
            <el-input v-model="form.newPassword" type="password" show-password />
          </el-form-item>
          <el-form-item label="确认新密码" prop="confirmPassword">
            <el-input v-model="form.confirmPassword" type="password" show-password />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="loading" @click="handleChangePassword">
              修改密码
            </el-button>
          </el-form-item>
        </el-form>
      </el-card>
    </el-main>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import { useAuthStore } from '../stores/auth'
import { authAPI } from '../api'

const authStore = useAuthStore()
const loading = ref(false)
const formRef = ref(null)

const form = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: '',
})

const rules = {
  oldPassword: [{ required: true, message: '请输入原密码', trigger: 'blur' }],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码至少6位', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请确认新密码', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value !== form.newPassword) callback(new Error('两次密码不一致'))
        else callback()
      },
      trigger: 'blur',
    },
  ],
}

async function handleChangePassword() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await authAPI.changePassword({
      old_password: form.oldPassword,
      new_password: form.newPassword,
    })
    ElMessage.success('密码修改成功，请重新登录')
    authStore.logout()
    setTimeout(() => window.location.href = '/login', 1000)
  } catch (e) {
    // 错误由拦截器处理
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.profile-page {
  min-height: 100vh;
  background: #f5f7fa;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  padding: 0 24px;
  height: 60px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.page-main {
  max-width: 800px;
  margin: 24px auto;
  padding: 0 24px;
}
</style>
