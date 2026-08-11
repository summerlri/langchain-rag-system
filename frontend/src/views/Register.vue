<template>
  <div class="auth-page">
    <div class="auth-card">
      <div class="auth-brand"><span>知</span> KNOWLEDGE DESK</div>
      <h1 class="auth-title">创建新账号</h1>
      <p class="auth-subtitle">让每一次回答，都能回到原始资料。</p>

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" size="large">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="2-50个字符" :prefix-icon="User" />
        </el-form-item>

        <el-form-item label="邮箱（选填）" prop="email">
          <el-input v-model="form.email" placeholder="请输入邮箱" :prefix-icon="Message" />
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" placeholder="至少6位密码" :prefix-icon="Lock" show-password />
        </el-form-item>

        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input v-model="form.confirmPassword" type="password" placeholder="再次输入密码" :prefix-icon="Lock" show-password />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="loading" @click="handleRegister" style="width: 100%">
            注 册
          </el-button>
        </el-form-item>
      </el-form>

      <div class="auth-footer">
        已有账号？<router-link to="/login">返回登录</router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock, Message } from '@element-plus/icons-vue'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()
const loading = ref(false)
const formRef = ref(null)

const form = reactive({
  username: '',
  email: '',
  password: '',
  confirmPassword: '',
})

const validateConfirmPassword = (rule, value, callback) => {
  if (value !== form.password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 50, message: '用户名长度2-50个字符', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少6位', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' },
  ],
}

async function handleRegister() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await authStore.register(form.username, form.password, form.email)
    ElMessage.success('注册成功')
    router.push('/chat')
  } catch (e) {
    // 错误由 axios 拦截器统一处理
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-page {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  padding: 24px;
  background: radial-gradient(circle at 82% 16%, rgba(15,159,154,.18), transparent 32%), var(--ink-950);
}

.auth-card {
  width: 420px;
  padding: 40px 44px;
  background: #fff;
  border-radius: 4px 24px 24px 24px;
  box-shadow: var(--shadow-lg);
}
.auth-brand { margin-bottom: 28px; color: var(--aqua-dark); font: 750 10px/1 ui-monospace, monospace; letter-spacing: .14em; }
.auth-brand span { display: inline-grid; place-items: center; width: 28px; height: 28px; margin-right: 8px; color: white; background: var(--ink-950); border-radius: 8px 8px 8px 2px; font: 700 15px Georgia, serif; }

.auth-title {
  font: 700 34px/1.16 Georgia, "Songti SC", serif;
  color: var(--ink-950);
  margin-bottom: 8px;
}

.auth-subtitle {
  color: var(--ink-600);
  margin-bottom: 32px;
}

.auth-footer {
  text-align: center;
  color: var(--ink-400);
  font-size: 14px;
}

.auth-footer a {
  color: var(--aqua-dark);
  font-weight: 700;
  text-decoration: none;
}
</style>
