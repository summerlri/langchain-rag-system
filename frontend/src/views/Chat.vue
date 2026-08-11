<template>
  <div class="chat-page">
    <!-- 顶部导航 -->
    <div class="chat-header">
      <div class="header-left">
        <div class="brand-mark">知</div>
        <div>
          <div class="brand-eyebrow">KNOWLEDGE DESK</div>
          <h3>知问台</h3>
        </div>
      </div>
      <div class="header-right">
        <el-button v-if="currentConvId" @click="handleExport" :icon="Download" plain size="small">
          导出
        </el-button>
        <el-button v-if="authStore.isAdmin" @click="$router.push('/admin/knowledge')" type="primary" plain size="small">
          知识库管理
        </el-button>
        <el-button @click="$router.push('/profile')" :icon="User" circle size="small" />
        <el-button @click="handleLogout" :icon="SwitchButton" circle size="small" />
      </div>
    </div>

    <div class="chat-body">
      <!-- 左侧：会话列表 -->
      <div class="session-sidebar" :class="{ collapsed: sidebarCollapsed }">
        <div class="sidebar-header">
          <el-button @click="handleNewSession" type="primary" style="width: 100%" :icon="Plus" :disabled="!hasKB">
            新对话
          </el-button>
        </div>
        <div class="session-list" v-if="!sidebarCollapsed">
          <div
            v-for="conv in conversations"
            :key="conv.id"
            class="session-item"
            :class="{ active: currentConvId === conv.id }"
            @click="switchSession(conv.id)"
          >
            <div class="session-title">{{ conv.title }}</div>
            <div class="session-info">
              <span>{{ conv.message_count }} 条消息</span>
              <span>{{ conv.updated_at?.split(' ')[0] }}</span>
            </div>
            <el-popconfirm title="确定删除此对话？" @confirm="handleDeleteSession(conv.id)">
              <el-button class="session-delete" :icon="Delete" text size="small" @click.stop />
            </el-popconfirm>
          </div>
          <el-empty v-if="conversations.length === 0" description="暂无对话" :image-size="80" />
        </div>
        <div class="sidebar-toggle" @click="sidebarCollapsed = !sidebarCollapsed">
          <el-icon><component :is="sidebarCollapsed ? Expand : Fold" /></el-icon>
        </div>
      </div>

      <!-- 中间：对话区 -->
      <div class="chat-main">
        <!-- 尚无会话 -->
        <div v-if="!currentConvId && !hasKB" class="no-conv">
          <el-empty description="知识库尚未初始化" :image-size="120">
            <template v-if="authStore.isAdmin">
              <el-button type="primary" @click="$router.push('/admin/knowledge')">前往管理知识库</el-button>
            </template>
            <template v-else>
              <p style="color: #909399">请联系管理员上传知识库文档</p>
            </template>
          </el-empty>
        </div>

        <div v-else-if="!currentConvId" class="no-conv">
          <div class="welcome-block">
            <div class="welcome-kicker">从资料中找到答案</div>
            <h1>问题可以很随意，<br><span>证据必须很具体。</span></h1>
            <p>创建一段对话。系统会结合上下文理解追问，并同时使用语义与关键词检索。</p>
            <el-button type="primary" size="large" @click="handleNewSession" :disabled="!hasKB" :icon="Plus">开始提问</el-button>
          </div>
        </div>

        <!-- 消息列表 -->
        <div v-else class="messages-container" ref="msgContainer">
          <div v-for="(msg, idx) in messages" :key="idx" class="message-wrapper">
            <!-- 用户消息 -->
            <div v-if="msg.role === 'user'" class="message user-message">
              <div class="msg-avatar">
                <el-avatar :icon="UserFilled" size="small" />
              </div>
              <div class="msg-bubble user-bubble">{{ msg.content }}</div>
            </div>

            <!-- AI 消息 -->
            <div v-else class="message ai-message">
              <div class="msg-avatar">
                <el-avatar :icon="Cpu" size="small" style="background: #409eff" />
              </div>
              <div class="msg-content">
                <div class="msg-bubble ai-bubble" v-html="renderMarkdown(msg.content)" />
                <!-- 引用来源 -->
                <div v-if="msg.sources && parseSources(msg.sources).length > 0" class="msg-sources">
                  <div class="sources-title">📚 参考来源：</div>
                  <div v-for="(src, si) in parseSources(msg.sources)" :key="si" class="source-item">
                    <div class="source-header">
                      <el-tag size="small" type="info">[{{ si + 1 }}] {{ src.filename }}</el-tag>
                      <span class="source-score">匹配度: {{ (src.score * 100).toFixed(1) }}%</span>
                    </div>
                    <div class="source-text">{{ src.content?.substring(0, 200) }}{{ src.content?.length > 200 ? '...' : '' }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 流式生成中的临时消息 -->
          <div v-if="streaming" class="message ai-message">
            <div class="msg-avatar">
              <el-avatar :icon="Cpu" size="small" style="background: #409eff" />
            </div>
            <div class="msg-content">
              <div v-if="rewrittenQuestion" class="retrieval-trace">
                <span class="trace-dot"></span>
                正在检索：{{ rewrittenQuestion }}
              </div>
              <div class="msg-bubble ai-bubble" v-html="renderMarkdown(streamContent)" />
              <span class="streaming-cursor">▊</span>
            </div>
          </div>

          <div ref="msgBottom" />
        </div>

        <!-- 输入框 -->
        <div class="chat-input" v-if="currentConvId">
          <el-input
            v-model="inputText"
            type="textarea"
            :rows="2"
            placeholder="继续追问，或输入一个新的问题…"
            @keyup.enter.shift="handleSend"
            @keyup.ctrl.enter="handleSend"
            :disabled="streaming"
          />
          <div class="input-actions">
            <span class="input-hint">Enter 换行 · Shift / Ctrl + Enter 发送</span>
            <el-button type="primary" :icon="Promotion" @click="handleSend" :loading="streaming" :disabled="!inputText.trim()">
              {{ streaming ? '生成中...' : '发送' }}
            </el-button>
          </div>
        </div>
      </div>

      <!-- 右侧：引用面板（可折叠） -->
      <div class="source-panel" v-if="currentSources.length > 0 && !sourcePanelHidden">
        <div class="panel-header">
          <span>引用来源 ({{ currentSources.length }})</span>
          <el-button :icon="Close" @click="sourcePanelHidden = true" text size="small" />
        </div>
        <div class="panel-body">
          <div v-for="(src, i) in currentSources" :key="i" class="panel-source">
            <el-tag size="small" type="success">[{{ i + 1 }}]</el-tag>
            <div class="panel-filename">{{ src.filename }}</div>
            <div class="panel-text">{{ src.content?.substring(0, 300) }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 暂无知识库提示 -->
    <el-dialog v-model="noKBDialog" title="提示" width="400px">
      <p>系统中还没有知识库，无法进行问答。{{ authStore.isAdmin ? '请先前往知识库管理页面上传文档。' : '请联系管理员上传知识库文档。' }}</p>
      <template #footer>
        <el-button v-if="authStore.isAdmin" type="primary" @click="$router.push('/admin/knowledge')">前往管理</el-button>
        <el-button @click="noKBDialog = false">知道了</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Plus, Delete, Expand, Fold, UserFilled, Cpu, Promotion, User, SwitchButton, Close, Download } from '@element-plus/icons-vue'
import { useAuthStore } from '../stores/auth'
import { convAPI, chatAPI, kbAPI } from '../api'
import { marked } from 'marked'

const authStore = useAuthStore()
const router = useRouter()

// 状态
const sidebarCollapsed = ref(false)
const sourcePanelHidden = ref(false)
const conversations = ref([])
const currentConvId = ref('')
const messages = ref([])
const inputText = ref('')
const streaming = ref(false)
const streamContent = ref('')
const currentSources = ref([])
const rewrittenQuestion = ref('')
const hasKB = ref(false)
const noKBDialog = ref(false)
const msgContainer = ref(null)
const msgBottom = ref(null)

// ==================== 初始化 ====================
onMounted(async () => {
  await loadConversations()
  await checkKB()
  if (conversations.value.length > 0) {
    switchSession(conversations.value[0].id)
  }
})

async function checkKB() {
  try {
    const res = await kbAPI.list()
    hasKB.value = res.data.length > 0
  } catch (e) {
    hasKB.value = false
  }
}

// ==================== 会话管理 ====================
async function loadConversations() {
  try {
    const res = await convAPI.list()
    conversations.value = res.data
  } catch (e) {
    conversations.value = []
  }
}

async function handleNewSession() {
  if (!hasKB.value) {
    noKBDialog.value = true
    return
  }
  try {
    const res = await convAPI.create({ title: '新对话' })
    await loadConversations()
    switchSession(res.data.id)
  } catch (e) { /* handled */ }
}

async function switchSession(convId) {
  currentConvId.value = convId
  currentSources.value = []
  rewrittenQuestion.value = ''
  try {
    const res = await chatAPI.getMessages(convId, 1)
    messages.value = res.data
    await nextTick()
    scrollToBottom()
  } catch (e) {
    messages.value = []
  }
}

async function handleDeleteSession(convId) {
  try {
    await convAPI.delete(convId)
    await loadConversations()
    if (currentConvId.value === convId) {
      currentConvId.value = ''
      messages.value = []
      if (conversations.value.length > 0) {
        switchSession(conversations.value[0].id)
      }
    }
  } catch (e) { /* handled */ }
}

// ==================== 发送消息 ====================
async function handleSend() {
  if (!inputText.value.trim() || streaming.value) return
  const question = inputText.value.trim()
  inputText.value = ''

  // 添加用户消息到界面
  messages.value.push({ role: 'user', content: question, created_at: new Date().toISOString() })
  await nextTick()
  scrollToBottom()

  // 开始流式
  streaming.value = true
  streamContent.value = ''
    currentSources.value = []
    rewrittenQuestion.value = ''

  try {
    const response = await chatAPI.sendMessageStream(currentConvId.value, { message: question })
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const event = JSON.parse(line.slice(6))
            if (event.type === 'rewrite') {
              rewrittenQuestion.value = event.rewritten_question === event.original_question ? '' : event.rewritten_question
            } else if (event.type === 'sources') {
              currentSources.value = event.data || []
            } else if (event.type === 'token') {
              streamContent.value += event.content
              await nextTick()
              scrollToBottom()
            } else if (event.type === 'done') {
              // 流式完成 — 保存到消息列表
              const finalContent = streamContent.value
              const finalSources = JSON.parse(JSON.stringify(currentSources.value))
              messages.value.push({
                role: 'assistant',
                content: finalContent,
                sources: JSON.stringify(finalSources),
                created_at: new Date().toISOString(),
              })
              streamContent.value = ''
              currentSources.value = finalSources
              rewrittenQuestion.value = ''
              break
            } else if (event.type === 'error') {
              streamContent.value += `\n\n⚠️ ${event.content}`
            }
          } catch (e) { /* JSON parse error, skip */ }
        }
      }
    }
  } catch (e) {
    ElMessage.error('请求失败: ' + (e.message || '网络错误'))
  } finally {
    streaming.value = false
    if (streamContent.value) {
      // 如果流中断但有内容，保留
      messages.value.push({
        role: 'assistant',
        content: streamContent.value,
        sources: JSON.stringify(currentSources.value),
        created_at: new Date().toISOString(),
      })
      streamContent.value = ''
    }
    // 刷新会话列表更新标题
    loadConversations()
  }
}

// ==================== 工具函数 ====================
function parseSources(sources) {
  if (!sources) return []
  try {
    return typeof sources === 'string' ? JSON.parse(sources) : sources
  } catch {
    return []
  }
}

function renderMarkdown(text) {
  if (!text) return ''
  return marked.parse(text, { breaks: true })
}

function scrollToBottom() {
  nextTick(() => {
    msgBottom.value?.scrollIntoView({ behavior: 'smooth' })
  })
}

async function handleExport() {
  if (!currentConvId.value) return
  try {
    const response = await convAPI.exportMarkdown(currentConvId.value)
    const blob = response.data
    // 从响应头获取文件名（支持 RFC 5987 编码和普通格式）
    const disposition = response.headers['content-disposition'] || ''
    const starMatch = disposition.match(/filename\*=UTF-8''([^;]+)/)
    const filename = starMatch
      ? decodeURIComponent(starMatch[1])
      : (disposition.match(/filename="?([^";\n]+)"?/) || [])[1] || 'conversation_export.md'
    // 触发浏览器下载
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    // 延迟回收 blob URL，等待浏览器下载管理器读取完毕
    setTimeout(() => URL.revokeObjectURL(url), 1000)
    ElMessage.success('导出成功')
  } catch (e) {
    ElMessage.error('导出失败: ' + (e.response?.data?.detail || e.message || '未知错误'))
  }
}

function handleLogout() {
  authStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.chat-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #f5f7fa;
}

.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56px;
  padding: 0 20px;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  flex-shrink: 0;
}

.header-left h3 {
  color: #303133;
  font-size: 18px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.chat-body {
  display: flex;
  flex: 1;
  overflow: hidden;
}

/* ====== 左侧会话列表 ====== */
.session-sidebar {
  width: 260px;
  background: #fff;
  border-right: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
  position: relative;
  flex-shrink: 0;
  transition: width 0.2s;
}

.session-sidebar.collapsed {
  width: 40px;
}

.sidebar-header {
  padding: 12px;
  flex-shrink: 0;
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px;
}

.session-item {
  padding: 12px;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 4px;
  position: relative;
  transition: background 0.15s;
}

.session-item:hover {
  background: #f0f2f5;
}

.session-item.active {
  background: #ecf5ff;
}

.session-title {
  font-size: 14px;
  color: #303133;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding-right: 24px;
}

.session-info {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #909399;
}

.session-delete {
  position: absolute;
  top: 8px;
  right: 8px;
  opacity: 0;
  transition: opacity 0.15s;
}

.session-item:hover .session-delete {
  opacity: 1;
}

.sidebar-toggle {
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  border-top: 1px solid #e4e7ed;
  color: #909399;
}

/* ====== 中间对话区 ====== */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.no-conv {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 1;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.message-wrapper {
  margin-bottom: 16px;
}

.message {
  display: flex;
  gap: 12px;
}

.user-message {
  flex-direction: row-reverse;
}

.msg-avatar {
  flex-shrink: 0;
}

.msg-bubble {
  max-width: 70%;
  padding: 10px 16px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
  overflow-wrap: break-word;
}

.user-bubble {
  background: #409eff;
  color: #fff;
  border-bottom-right-radius: 4px;
}

.ai-bubble {
  background: #fff;
  border: 1px solid #e4e7ed;
  border-bottom-left-radius: 4px;
  line-height: 1.8;
}

.ai-bubble :deep(p) {
  margin: 4px 0;
}

.ai-bubble :deep(table) {
  border-collapse: collapse;
  margin: 8px 0;
  width: 100%;
}

.ai-bubble :deep(th), .ai-bubble :deep(td) {
  border: 1px solid #dcdfe6;
  padding: 6px 12px;
  text-align: left;
}

.ai-bubble :deep(th) {
  background: #f5f7fa;
}

.ai-bubble :deep(code) {
  background: #f0f2f5;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
}

.msg-content {
  flex: 1;
  min-width: 0;
}

.msg-sources {
  margin-top: 8px;
  padding: 8px 12px;
  background: #fafafa;
  border-radius: 8px;
  border: 1px solid #ebeef5;
}

.sources-title {
  font-size: 12px;
  color: #909399;
  margin-bottom: 6px;
  font-weight: bold;
}

.source-item {
  margin-bottom: 6px;
}

.source-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.source-score {
  font-size: 11px;
  color: #67c23a;
}

.source-text {
  font-size: 12px;
  color: #606266;
  padding-left: 4px;
  border-left: 2px solid #409eff;
  line-height: 1.5;
}

.streaming-cursor {
  animation: blink 1s infinite;
  color: #409eff;
  font-weight: bold;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

/* ====== 输入框 ====== */
.chat-input {
  padding: 12px 20px;
  background: #fff;
  border-top: 1px solid #e4e7ed;
  flex-shrink: 0;
}

.input-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
}

.input-hint {
  font-size: 12px;
  color: #c0c4cc;
}

/* ====== 右侧引用面板 ====== */
.source-panel {
  width: 300px;
  background: #fff;
  border-left: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  overflow-y: auto;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #e4e7ed;
  font-size: 14px;
  font-weight: bold;
  flex-shrink: 0;
}

.panel-body {
  padding: 12px;
  overflow-y: auto;
}

.panel-source {
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px dashed #ebeef5;
}

.panel-filename {
  font-size: 12px;
  color: #409eff;
  margin: 4px 0;
}

.panel-text {
  font-size: 12px;
  color: #606266;
  line-height: 1.5;
}

/* Knowledge Desk visual system */
.chat-page { background: var(--paper); }
.chat-header {
  height: 68px;
  padding: 0 24px;
  background: rgba(255,255,255,.94);
  border-bottom-color: var(--line);
  backdrop-filter: blur(14px);
}
.header-left { display: flex; align-items: center; gap: 11px; }
.brand-mark {
  width: 38px; height: 38px; display: grid; place-items: center;
  color: white; background: var(--ink-950); border-radius: 11px 11px 11px 3px;
  font-family: Georgia, "Songti SC", serif; font-size: 19px; font-weight: 700;
}
.brand-eyebrow { color: var(--aqua-dark); font: 700 9px/1.2 ui-monospace, monospace; letter-spacing: .17em; }
.header-left h3 { margin-top: 2px; color: var(--ink-950); font: 700 18px/1.1 Georgia, "Songti SC", serif; letter-spacing: .04em; }
.session-sidebar { width: 276px; background: #f0f5f8; border-right-color: var(--line); }
.sidebar-header { padding: 18px 14px 12px; }
.sidebar-header .el-button { height: 42px; border-radius: 12px; box-shadow: 0 7px 18px rgba(15,159,154,.18); }
.session-list { padding: 4px 10px; }
.session-item { margin-bottom: 5px; padding: 13px 12px; border: 1px solid transparent; border-radius: 11px; }
.session-item:hover { background: rgba(255,255,255,.72); border-color: var(--line); }
.session-item.active { background: var(--surface); border-color: #b8e0de; box-shadow: var(--shadow-sm); }
.session-title { color: var(--ink-800); font-weight: 650; }
.session-info { color: var(--ink-400); font-family: ui-monospace, monospace; font-size: 10px; }
.sidebar-toggle { border-top-color: var(--line); }
.chat-main { background: radial-gradient(circle at 50% 0%, rgba(15,159,154,.06), transparent 38%), var(--paper); }
.welcome-block { width: min(680px, 82%); }
.welcome-kicker { display: inline-flex; margin-bottom: 18px; padding: 6px 10px; color: var(--aqua-dark); background: var(--aqua-soft); border-radius: 7px; font: 700 11px/1 ui-monospace, monospace; letter-spacing: .08em; }
.welcome-block h1 { margin-bottom: 18px; color: var(--ink-950); font: 700 clamp(36px, 5vw, 64px)/1.12 Georgia, "Songti SC", serif; letter-spacing: -.035em; }
.welcome-block h1 span { color: var(--aqua-dark); }
.welcome-block p { max-width: 560px; margin-bottom: 28px; color: var(--ink-600); font-size: 15px; line-height: 1.8; }
.messages-container { padding: 34px max(24px, 7vw); }
.message-wrapper { margin-bottom: 24px; }
.message { gap: 14px; }
.msg-bubble { max-width: min(760px, 82%); padding: 14px 18px; font-size: 14px; line-height: 1.75; }
.user-bubble { background: var(--ink-950); border-radius: 16px 16px 4px 16px; box-shadow: 0 9px 22px rgba(16,42,67,.14); }
.ai-bubble { color: var(--ink-800); background: rgba(255,255,255,.94); border-color: var(--line); border-radius: 4px 16px 16px 16px; box-shadow: var(--shadow-sm); }
.ai-message .msg-avatar .el-avatar { background: var(--aqua) !important; }
.msg-sources { max-width: min(760px, 82%); margin-top: 10px; padding: 12px 14px; background: #eef7f7; border-color: #c7e7e5; border-radius: 12px; }
.sources-title { color: var(--ink-600); letter-spacing: .04em; }
.source-text { color: var(--ink-600); border-left-color: var(--aqua); }
.retrieval-trace { display: flex; align-items: center; gap: 8px; margin: 0 0 8px 2px; color: var(--aqua-dark); font-size: 12px; }
.trace-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--aqua); box-shadow: 0 0 0 5px rgba(15,159,154,.12); animation: pulse 1.6s ease-in-out infinite; }
@keyframes pulse { 50% { transform: scale(.72); opacity: .58; } }
.chat-input { padding: 14px max(24px, 7vw) 18px; background: rgba(247,249,252,.92); border-top: 0; }
.chat-input :deep(.el-textarea__inner) { min-height: 76px !important; padding: 14px 16px; border-radius: 14px; background: white; box-shadow: 0 0 0 1px var(--line), 0 12px 30px rgba(16,42,67,.07) !important; resize: none; }
.input-actions { margin-top: 10px; }
.input-hint { color: var(--ink-400); font-family: ui-monospace, monospace; font-size: 10px; }
.source-panel { width: 330px; background: #f0f5f8; border-left-color: var(--line); }
.panel-header { padding: 17px; color: var(--ink-800); border-bottom-color: var(--line); }
.panel-body { padding: 14px; }
.panel-source { padding: 13px; background: white; border: 1px solid var(--line); border-radius: 12px; box-shadow: var(--shadow-sm); }
.panel-filename { color: var(--aqua-dark); font-weight: 700; }
.panel-text { color: var(--ink-600); }

@media (max-width: 900px) {
  .source-panel { display: none; }
  .session-sidebar { width: 220px; }
  .messages-container, .chat-input { padding-left: 18px; padding-right: 18px; }
}
@media (max-width: 640px) {
  .chat-header { padding: 0 12px; }
  .brand-eyebrow, .header-left h3 { display: none; }
  .header-right .el-button span { display: none; }
  .session-sidebar:not(.collapsed) { position: absolute; z-index: 8; inset: 68px auto 0 0; box-shadow: var(--shadow-lg); }
  .msg-bubble, .msg-sources { max-width: 92%; }
  .welcome-block h1 { font-size: 38px; }
}
</style>
