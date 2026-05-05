<template>
  <div class="project">
    <el-container>
      <el-header class="header">
        <div class="left">
          <el-button link @click="goBack">
            <el-icon><ArrowLeft /></el-icon>
          </el-button>
          <span class="title">{{ currentProject?.name }}</span>
        </div>
        <el-button type="primary" @click="showCreateDialog = true">
          <el-icon><Plus /></el-icon>
          新建会话
        </el-button>
      </el-header>
      
      <el-main class="main">
        <div class="sessions-container">
          <h3>会话列表</h3>
          
          <el-empty v-if="!hasSessions" description="暂无会话">
            <el-button type="primary" @click="showCreateDialog = true">创建会话</el-button>
          </el-empty>
          
          <el-table v-else :data="sessions" style="width: 100%" @row-click="goToSession">
            <el-table-column prop="title" label="会话标题" />
            <el-table-column prop="status" label="状态" width="120">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="180">
              <template #default="{ row }">
                {{ formatDate(row.created_at) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120">
              <template #default="{ row }">
                <el-button link type="primary" @click.stop="goToSession(row)">
                  进入
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-main>
    </el-container>

    <!-- 创建会话对话框 -->
    <el-dialog v-model="showCreateDialog" title="新建会话" width="500px">
      <el-form :model="createForm" label-width="80px">
        <el-form-item label="会话标题">
          <el-input v-model="createForm.title" placeholder="请输入会话标题" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="createSession" :loading="creating">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAgentStore } from '@/stores'
import { sessionApi } from '@/api'
import type { Session } from '@/types'
import dayjs from 'dayjs'

const router = useRouter()
const route = useRoute()
const store = useAgentStore()

const projectId = route.params.projectId as string
const showCreateDialog = ref(false)
const creating = ref(false)
const createForm = ref({
  title: '',
})

const currentProject = computed(() => store.currentProject)
const sessions = computed(() => store.sessions)
const hasSessions = computed(() => store.hasSessions)

function formatDate(date: string) {
  return dayjs(date).format('YYYY-MM-DD HH:mm:ss')
}

function getStatusType(status: string) {
  const typeMap: Record<string, string> = {
    idle: 'info',
    running: 'warning',
    completed: 'success',
    stopped: 'danger',
    awaiting_approval: 'warning',
  }
  return typeMap[status] || 'info'
}

async function loadSessions() {
  try {
    const data = await sessionApi.getSessions(projectId)
    store.setSessions(data)
  } catch (error) {
    ElMessage.error('加载会话列表失败')
  }
}

async function createSession() {
  if (!createForm.value.title.trim()) {
    createForm.value.title = 'New Session'
  }
  
  creating.value = true
  try {
    const data = await sessionApi.createSession(projectId, {
      title: createForm.value.title,
    })
    store.setSessions([data, ...store.sessions])
    ElMessage.success('会话创建成功')
    showCreateDialog.value = false
    createForm.value.title = ''
    
    // 自动进入新会话
    goToSession(data)
  } catch (error) {
    ElMessage.error('创建会话失败')
  } finally {
    creating.value = false
  }
}

function goToSession(session: Session) {
  store.setCurrentSession(session)
  router.push(`/project/${projectId}/session/${session.id}`)
}

function goBack() {
  router.push('/')
}

onMounted(() => {
  loadSessions()
})
</script>

<style scoped lang="scss">
.project {
  height: 100%;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: #fff;
  border-bottom: 1px solid #e4e7ed;
  
  .left {
    display: flex;
    align-items: center;
    gap: 12px;
    
    .title {
      font-size: 18px;
      font-weight: 500;
    }
  }
}

.main {
  background-color: #f5f7fa;
  min-height: calc(100vh - 60px);
}

.sessions-container {
  max-width: 1000px;
  margin: 0 auto;
  background-color: #fff;
  padding: 20px;
  border-radius: 8px;
  
  h3 {
    margin-bottom: 20px;
    color: #303133;
  }
}
</style>