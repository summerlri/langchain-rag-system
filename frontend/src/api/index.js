import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

// 请求拦截器 — 自动添加 Token
api.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器 — 统一错误处理
api.interceptors.response.use(
  response => response,
  error => {
    const msg = error.response?.data?.detail || error.message || '请求失败'
    ElMessage.error(msg)

    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }

    return Promise.reject(error)
  }
)

export default api

// ==================== 认证 API ====================
export const authAPI = {
  register: (data) => api.post('/auth/register', data),
  login: (data) => api.post('/auth/login', data),
  changePassword: (data) => api.put('/auth/password', data),
  getMe: () => api.get('/auth/me'),
}

// ==================== 知识库 API ====================
export const kbAPI = {
  list: () => api.get('/knowledge-bases'),
  create: (data) => api.post('/knowledge-bases', data),
  update: (id, data) => api.put(`/knowledge-bases/${id}`, data),
  delete: (id) => api.delete(`/knowledge-bases/${id}`),
  listDocs: (kbId) => api.get(`/knowledge-bases/${kbId}/documents`),
  uploadDoc: (kbId, formData) => api.post(`/knowledge-bases/${kbId}/documents`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
  deleteDoc: (kbId, docId) => api.delete(`/knowledge-bases/${kbId}/documents/${docId}`),
  reprocessDoc: (kbId, docId) => api.post(`/knowledge-bases/${kbId}/documents/${docId}/reprocess`),
}

// ==================== 会话 API ====================
export const convAPI = {
  list: () => api.get('/conversations'),
  create: (data) => api.post('/conversations', data),
  update: (id, data) => api.put(`/conversations/${id}`, data),
  delete: (id) => api.delete(`/conversations/${id}`),
  exportMarkdown: (id) => api.get(`/conversations/${id}/export`, { responseType: 'blob' }),
}

// ==================== 聊天 API (SSE) ====================
export const chatAPI = {
  getMessages: (convId, page = 1) => api.get(`/chat/${convId}/messages`, { params: { page, page_size: 20 } }),
  regenerate: (convId) => api.post(`/chat/${convId}/regenerate`),
  // SSE 流式请求 — 返回 fetch response 以便前端读取流
  sendMessageStream: (convId, data) => {
    const token = localStorage.getItem('token')
    return fetch(`/api/chat/${convId}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify(data),
    })
  },
}
