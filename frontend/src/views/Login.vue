<template>
  <div class="auth-page">
    <div class="auth-card">
      <div class="auth-brand"><span>知</span> KNOWLEDGE DESK</div>
      <h1 class="auth-title">回到你的<br>知识工作台</h1>
      <p class="auth-subtitle">从已上传的资料中检索、追问并获得有依据的回答。</p>

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" size="large">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="请输入用户名" :prefix-icon="User" />
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" placeholder="请输入密码" :prefix-icon="Lock"
            @keyup.enter="handleLogin" show-password />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="loading" @click="handleLogin" style="width: 100%">
            登 录
          </el-button>
        </el-form-item>
      </el-form>

      <div class="auth-footer">
        还没有账号？<router-link to="/register">立即注册</router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()
const loading = ref(false)

const form = reactive({
  username: '',
  password: '',
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function handleLogin() {
  if (!form.username || !form.password) return
  loading.value = true
  try {
    await authStore.login(form.username, form.password)
    ElMessage.success('登录成功')
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
  background: radial-gradient(circle at 18% 20%, rgba(15,159,154,.17), transparent 32%), var(--ink-950);
}

.auth-card {
  width: 420px;
  padding: 44px;
  background: #fff;
  border: 1px solid rgba(255,255,255,.18);
  border-radius: 4px 24px 24px 24px;
  box-shadow: var(--shadow-lg);
}
.auth-brand { margin-bottom: 34px; color: var(--aqua-dark); font: 750 10px/1 ui-monospace, monospace; letter-spacing: .14em; }
.auth-brand span { display: inline-grid; place-items: center; width: 28px; height: 28px; margin-right: 8px; color: white; background: var(--ink-950); border-radius: 8px 8px 8px 2px; font: 700 15px Georgia, serif; }

.auth-title {
  font: 700 36px/1.16 Georgia, "Songti SC", serif;
  color: var(--ink-950);
  margin-bottom: 12px;
}

.auth-subtitle {
  color: var(--ink-600);
  line-height: 1.7;
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
