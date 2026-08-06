<template>
  <div class="kb-page">
    <el-header class="page-header">
      <div class="header-left">
        <el-button @click="$router.push('/chat')" :icon="ArrowLeft" circle />
        <h2>知识库管理</h2>
      </div>
      <div class="header-right">
        <el-tag type="danger">管理员: {{ authStore.username }}</el-tag>
      </div>
    </el-header>

    <el-main class="page-main">
      <!-- 知识库列表 -->
      <div class="kb-section">
        <div class="section-header">
          <h3>知识库列表</h3>
          <el-button type="primary" :icon="Plus" @click="showKBDialog = true">新建知识库</el-button>
        </div>

        <el-table :data="knowledgeBases" border style="width: 100%" v-loading="loadingKB">
          <el-table-column prop="name" label="名称" min-width="150" />
          <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
          <el-table-column prop="doc_count" label="文档数" width="100" align="center" />
          <el-table-column prop="created_at" label="创建时间" width="180" />
          <el-table-column label="操作" width="200" align="center">
            <template #default="{ row }">
              <el-button size="small" @click="selectKB(row)" :type="selectedKB?.id === row.id ? 'primary' : ''">
                {{ selectedKB?.id === row.id ? '已选' : '管理文档' }}
              </el-button>
              <el-popconfirm title="确定删除此知识库？所有文档和向量数据将被删除！" @confirm="handleDeleteKB(row.id)">
                <el-button size="small" type="danger" :icon="Delete" />
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 文档管理 -->
      <div class="doc-section" v-if="selectedKB">
        <div class="section-header">
          <h3>文档管理 — {{ selectedKB.name }}</h3>
          <el-upload
            :before-upload="handleBeforeUpload"
            :http-request="handleUploadDoc"
            :show-file-list="false"
            accept=".pdf,.docx,.xlsx,.txt,.csv,.md"
          >
            <el-button type="success" :icon="Upload" :loading="uploading">上传文档</el-button>
          </el-upload>
        </div>

        <el-table :data="documents" border style="width: 100%" v-loading="loadingDocs">
          <el-table-column prop="filename" label="文件名" min-width="200" show-overflow-tooltip />
          <el-table-column prop="file_type" label="类型" width="80" align="center" />
          <el-table-column label="大小" width="100" align="center">
            <template #default="{ row }">{{ formatSize(row.file_size) }}</template>
          </el-table-column>
          <el-table-column label="状态" width="120" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.status === 'completed'" type="success">已完成</el-tag>
              <el-tag v-else-if="row.status === 'processing'" type="warning" :icon="Loading">处理中</el-tag>
              <el-tag v-else-if="row.status === 'failed'" type="danger">失败</el-tag>
              <el-tag v-else type="info">待处理</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="chunk_count" label="分块数" width="100" align="center" />
          <el-table-column prop="uploaded_at" label="上传时间" width="180" />
          <el-table-column label="操作" width="160" align="center">
            <template #default="{ row }">
              <el-button size="small" @click="handleReprocess(row)" :loading="row._reprocessing" :icon="RefreshRight">
                重新处理
              </el-button>
              <el-popconfirm title="确定删除此文档？" @confirm="handleDeleteDoc(row.id)">
                <el-button size="small" type="danger" :icon="Delete" />
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>

        <el-empty v-if="!loadingDocs && documents.length === 0" description="暂无文档，请上传" :image-size="80" />
      </div>
    </el-main>

    <!-- 新建知识库弹窗 -->
    <el-dialog v-model="showKBDialog" title="新建知识库" width="500px">
      <el-form :model="kbForm" label-width="80px">
        <el-form-item label="名称" required>
          <el-input v-model="kbForm.name" placeholder="知识库名称" maxlength="100" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="kbForm.description" type="textarea" :rows="3" placeholder="知识库描述（可选）" maxlength="500" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showKBDialog = false">取消</el-button>
        <el-button type="primary" @click="handleCreateKB" :loading="creatingKB">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Plus, Delete, Upload, Loading, RefreshRight } from '@element-plus/icons-vue'
import { useAuthStore } from '../stores/auth'
import { kbAPI } from '../api'

const authStore = useAuthStore()

const loadingKB = ref(false)
const loadingDocs = ref(false)
const uploading = ref(false)
const creatingKB = ref(false)
const showKBDialog = ref(false)

const knowledgeBases = ref([])
const selectedKB = ref(null)
const documents = ref([])

const kbForm = ref({ name: '', description: '' })

// ==================== 初始化 ====================
onMounted(() => {
  loadKBs()
})

async function loadKBs() {
  loadingKB.value = true
  try {
    const res = await kbAPI.list()
    knowledgeBases.value = res.data
  } catch (e) { /* handled */ }
  finally { loadingKB.value = false }
}

async function loadDocs(kbId) {
  loadingDocs.value = true
  try {
    const res = await kbAPI.listDocs(kbId)
    documents.value = res.data.map(d => ({ ...d, _reprocessing: false }))
  } catch (e) { /* handled */ }
  finally { loadingDocs.value = false }
}

// ==================== 知识库操作 ====================
async function handleCreateKB() {
  if (!kbForm.value.name.trim()) {
    ElMessage.warning('请输入知识库名称')
    return
  }
  creatingKB.value = true
  try {
    await kbAPI.create(kbForm.value)
    ElMessage.success('知识库创建成功')
    showKBDialog.value = false
    kbForm.value = { name: '', description: '' }
    await loadKBs()
  } catch (e) { /* handled */ }
  finally { creatingKB.value = false }
}

async function handleDeleteKB(kbId) {
  try {
    await kbAPI.delete(kbId)
    ElMessage.success('知识库已删除')
    if (selectedKB.value?.id === kbId) {
      selectedKB.value = null
      documents.value = []
    }
    await loadKBs()
  } catch (e) { /* handled */ }
}

function selectKB(kb) {
  selectedKB.value = kb
  loadDocs(kb.id)
}

// ==================== 文档操作 ====================
function handleBeforeUpload(file) {
  const ext = file.name.split('.').pop()?.toLowerCase()
  const allowed = ['pdf', 'docx', 'xlsx', 'txt', 'csv', 'md']
  if (!allowed.includes(ext)) {
    ElMessage.error(`不支持的文件类型: .${ext}`)
    return false
  }
  if (file.size > 20 * 1024 * 1024) {
    ElMessage.error('文件大小不能超过 20MB')
    return false
  }
  return true
}

async function handleUploadDoc({ file }) {
  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    await kbAPI.uploadDoc(selectedKB.value.id, formData)
    ElMessage.success('文档已上传，正在后台处理...')
    // 定时刷新文档状态
    setTimeout(() => loadDocs(selectedKB.value.id), 2000)
    setTimeout(() => loadDocs(selectedKB.value.id), 5000)
  } catch (e) { /* handled */ }
  finally { uploading.value = false }
}

async function handleDeleteDoc(docId) {
  try {
    await kbAPI.deleteDoc(selectedKB.value.id, docId)
    ElMessage.success('文档已删除')
    await loadDocs(selectedKB.value.id)
  } catch (e) { /* handled */ }
}

async function handleReprocess(doc) {
  doc._reprocessing = true
  try {
    await kbAPI.reprocessDoc(selectedKB.value.id, doc.id)
    ElMessage.success('已提交重新处理')
    setTimeout(() => loadDocs(selectedKB.value.id), 3000)
  } catch (e) { /* handled */ }
  finally { doc._reprocessing = false }
}

function formatSize(bytes) {
  if (!bytes) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}
</script>

<style scoped>
.kb-page {
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
  max-width: 1200px;
  margin: 24px auto;
  padding: 0 24px;
}

.kb-section, .doc-section {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 24px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-header h3 {
  font-size: 16px;
  color: #303133;
}
</style>
