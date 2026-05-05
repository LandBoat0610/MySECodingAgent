<template>
  <div class="session">
    <el-container>
      <el-aside width="250px" class="sidebar">
        <div class="sidebar-header">
          <el-button link @click="goBack">
            <el-icon><ArrowLeft /></el-icon>
            返回
          </el-button>
        </div>
        
        <div class="file-tree">
          <h4>文件树</h4>
          <el-tree
            v-if="fileTree.length > 0"
            :data="fileTree"
            :props="{ label: 'path', children: 'children' }"
            @node-click="handleFileClick"
          />
          <el-empty v-else description="暂无文件" />
        </div>
      </el-aside>
      
      <el-container>
        <el-header class="chat-header">
          <span>{{ currentSession?.title }}</span>
          <el-tag :type="getStatusType(agentState?.status)">{{ agentState?.status || 'idle' }}</el-tag>
        </el-header>
        
        <el-main class="chat-main">
          <div class="messages" ref="messagesRef">
            <div
              v-for="(msg, index) in messages"
              :key="index"
              :class="['message', msg.type]"
            >
              <div class="message-content">
                <pre v-if="msg.type === 'trace'">{{ msg.content }}</pre>
                <span v-else>{{ msg.content }}</span>
              </div>
              <div class="message-time">{{ formatTime(msg.timestamp) }}</div>
            </div>
          </div>
        </el-main>
        
        <el-footer class="chat-footer" height="200px">
          <!-- 计划确认区域 -->
          <div v-if="isAwaitingApproval" class="plan-approval">
            <el-alert
              title="Agent 等待计划确认"
              description="请查看生成的执行计划并选择操作"
              type="warning"
              :closable="false"
            />
            <div class="plan-actions">
              <el-button type="success" @click="submitPlanAction('agree')">
                <el-icon><Check /></el-icon>
                同意执行
              </el-button>
              <el-button type="warning" @click="submitPlanAction('refine')">
                <el-icon><Refresh /></el-icon>
                优化计划
              </el-button>
              <el-button @click="submitPlanAction('skip')">
                <el-icon><Right /></el-icon>
                跳过
              </el-button>
              <el-button type="danger" @click="submitPlanAction('stop')">
                <el-icon><CircleClose /></el-icon>
                终止
              </el-button>
            </div>
          </div>
          
          <!-- 输入区域 -->
          <div class="input-area">
            <el-input
              v-model="inputMessage"
              type="textarea"
              :rows="3"
              placeholder="输入任务描述..."
              :disabled="isRunning"
              @keydown.enter.prevent="sendMessage"
            />
            <el-button
              type="primary"
              :disabled="!inputMessage.trim() || isRunning"
              :loading="isRunning"
              @click="sendMessage"
            >
              发送
            </el-button>
          </div>
        </el-footer>
      </el-container>
    </el-container>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAgentStore } from '@/stores'
import { chatApi, planApi, fileApi, createWebSocketConnection } from '@/api'
import type { FileTreeNode, Plan, WebSocketMessage } from '@/types'
import dayjs from 'dayjs'

const router = useRouter()
const route = useRoute()
const store = useAgentStore()

const projectId = route.params.projectId as string
const sessionId = route.params.sessionId as string

const messagesRef = ref<HTMLElement>()
const inputMessage = ref('')
const fileTree = ref<FileTreeNode[]>([])
const plans = ref<Plan[]>([])
const ws = ref<WebSocket | null>(null)

const currentSession = computed(() => store.currentSession)
const agentState = computed(() => store.agentState)
const messages = computed(() => store.messages)
const isRunning = computed(() => store.isRunning)
const isAwaitingApproval = computed(() => store.isAwaitingApproval)

function formatTime(timestamp: number) {
  return dayjs(timestamp).format('HH:mm:ss')
}

function getStatusType(status: string | undefined) {
  if (!status) return 'info'
  const typeMap: Record<string, string> = {
    idle: 'info',
    running: 'warning',
    completed: 'success',
    stopped: 'danger',
    awaiting_approval: 'warning',
  }
  return typeMap[status] || 'info'
}

async function loadFileTree() {
  try {
    const data = await fileApi.getFileTree(projectId)
    fileTree.value = data
  } catch (error) {
    console.error('加载文件树失败', error)
  }
}

async function loadPlans() {
  try {
    const data = await planApi.getPlans(projectId, sessionId)
    plans.value = data
  } catch (error) {
    console.error('加载计划失败', error)
  }
}

function connectWebSocket() {
  ws.value = createWebSocketConnection(projectId, sessionId)
  
  ws.value.onopen = () => {
    store.setConnected(true)
    store.addMessage('system', 'WebSocket 连接已建立')
  }
  
  ws.value.onmessage = (event) => {
    const data: WebSocketMessage = JSON.parse(event.data)
    handleWebSocketMessage(data)
  }
  
  ws.value.onclose = () => {
    store.setConnected(false)
    store.addMessage('system', 'WebSocket 连接已关闭')
  }
  
  ws.value.onerror = (error) => {
    store.addMessage('error', 'WebSocket 连接错误')
  }
}

function handleWebSocketMessage(data: WebSocketMessage) {
  if (data.error) {
    store.addMessage('error', data.error)
    return
  }
  
  if (data.phase) {
    if (data.phase === 'start') {
      store.addMessage('system', data.message || 'Agent 开始执行')
    } else if (data.phase === 'done') {
      store.addMessage('success', data.message || '任务完成')
      if (data.final_answer) {
        store.addMessage('final', data.final_answer)
      }
    } else if (data.phase === 'cancelled') {
      store.addMessage('warning', data.message || 'Agent 已终止')
    }
  }
  
  if (data.type === 'trace' && data.data) {
    store.addMessage('trace', `[${data.data.phase}] ${data.data.content}`)
  }
  
  // 更新状态
  if (data.status) {
    store.setAgentState({ ...agentState.value, status: data.status } as any)
  }
  
  scrollToBottom()
}

async function sendMessage() {
  if (!inputMessage.value.trim()) return
  
  const message = inputMessage.value
  store.addMessage('user', message)
  inputMessage.value = ''
  
  try {
    await chatApi.sendMessage(projectId, sessionId, { message })
    // WebSocket 会自动接收响应
  } catch (error) {
    ElMessage.error('发送消息失败')
  }
  
  scrollToBottom()
}

async function submitPlanAction(action: 'agree' | 'refine' | 'skip' | 'stop') {
  if (plans.value.length === 0) return
  
  const planId = plans.value[0].id
  try {
    await planApi.submitAction(projectId, sessionId, planId, { action })
    ElMessage.success(`已提交操作: ${action}`)
    
    if (action === 'agree') {
      store.setAgentState({ ...agentState.value, status: 'running' } as any)
    }
  } catch (error) {
    ElMessage.error('提交操作失败')
  }
}

function handleFileClick(data: FileTreeNode) {
  if (data.type === 'file') {
    console.log('Selected file:', data.path)
  }
}

function goBack() {
  router.push(`/project/${projectId}`)
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

onMounted(() => {
  loadFileTree()
  loadPlans()
  connectWebSocket()
})

onUnmounted(() => {
  if (ws.value) {
    ws.value.close()
  }
})
</script>

<style scoped lang="scss">
.session {
  height: 100vh;
}

.sidebar {
  background-color: #f5f7fa;
  border-right: 1px solid #e4e7ed;
  padding: 16px;
  
  .sidebar-header {
    margin-bottom: 20px;
  }
  
  .file-tree {
    h4 {
      margin-bottom: 12px;
      color: #303133;
    }
  }
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: #fff;
  border-bottom: 1px solid #e4e7ed;
}

.chat-main {
  background-color: #f5f7fa;
  padding: 20px;
  
  .messages {
    height: 100%;
    overflow-y: auto;
    background-color: #fff;
    border-radius: 8px;
    padding: 16px;
    
    .message {
      margin-bottom: 12px;
      padding: 8px 12px;
      border-radius: 4px;
      
      &.user {
        background-color: #ecf5ff;
        margin-left: 20%;
      }
      
      &.system {
        background-color: #f4f4f5;
        text-align: center;
        color: #909399;
      }
      
      &.trace {
        background-color: #f6f6f6;
        font-family: monospace;
        font-size: 12px;
      }
      
      &.error {
        background-color: #fef0f0;
        color: #f56c6c;
      }
      
      &.success {
        background-color: #f0f9eb;
        color: #67c23a;
      }
      
      &.warning {
        background-color: #fdf6ec;
        color: #e6a23c;
      }
      
      .message-content {
        pre {
          margin: 0;
          white-space: pre-wrap;
          word-wrap: break-word;
        }
      }
      
      .message-time {
        font-size: 11px;
        color: #909399;
        margin-top: 4px;
        text-align: right;
      }
    }
  }
}

.chat-footer {
  background-color: #fff;
  border-top: 1px solid #e4e7ed;
  padding: 16px;
  
  .plan-approval {
    margin-bottom: 16px;
    
    .plan-actions {
      margin-top: 12px;
      display: flex;
      gap: 8px;
    }
  }
  
  .input-area {
    display: flex;
    gap: 12px;
    
    .el-textarea {
      flex: 1;
    }
  }
}
</style>