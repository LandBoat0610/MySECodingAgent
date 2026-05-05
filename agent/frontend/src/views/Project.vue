<template>
  <div class="project-workspace">
    <el-container class="workspace-container">
      <!-- 左侧文件树 -->
      <el-aside width="260px" class="file-sidebar">
        <div class="sidebar-header">
          <el-button link @click="goBack" class="back-btn">
            <el-icon><ArrowLeft /></el-icon>
          </el-button>
          <span class="project-name">{{ currentProject?.name }}</span>
        </div>
        
        <div class="file-tree-container">
          <div class="tree-title">
            <el-icon><Folder /></el-icon>
            <span>文件树</span>
          </div>
          <el-tree
            v-if="fileTree.length > 0"
            :data="fileTree"
            :props="{ label: 'path', children: 'children' }"
            @node-click="handleFileClick"
            class="file-tree"
          />
          <el-empty v-else description="暂无文件" :image-size="60" />
        </div>
      </el-aside>

      <!-- 中间内容区 -->
      <el-main class="content-area">
        <div v-if="selectedFile" class="file-content">
          <div class="file-header">
            <el-icon><Document /></el-icon>
            <span>{{ selectedFile.path }}</span>
          </div>
          <pre class="code-block">{{ fileContent }}</pre>
        </div>
        <div v-else class="empty-content">
          <el-empty description="请选择左侧文件查看内容">
            <template #image>
              <el-icon :size="60" color="#dcdfe6"><Document /></el-icon>
            </template>
          </el-empty>
        </div>
      </el-main>

      <!-- 右侧会话区 -->
      <el-aside width="380px" class="session-sidebar">
        <div class="session-header">
          <div class="session-select">
            <el-select 
              v-model="currentSessionId" 
              placeholder="选择会话"
              @change="handleSessionChange"
              class="session-select-box"
            >
              <el-option
                v-for="session in sessions"
                :key="session.id"
                :label="session.title"
                :value="session.id"
              >
                <div class="session-option">
                  <span>{{ session.title }}</span>
                  <el-tag :type="getStatusType(session.status)" size="small">{{ session.status }}</el-tag>
                </div>
              </el-option>
            </el-select>
            <el-button type="primary" size="small" @click="showCreateDialog = true">
              <el-icon><Plus /></el-icon>
            </el-button>
          </div>
        </div>

        <div class="session-messages" ref="messagesRef">
          <div v-if="currentMessages.length === 0" class="empty-messages">
            <el-empty description="暂无消息，发送任务开始对话" :image-size="80" />
          </div>
          <div
            v-for="msg in currentMessages"
            :key="msg.id"
            :class="['message-item', msg.type]"
          >
            <!-- 用户消息 -->
            <div v-if="msg.type === 'user'" class="user-message">
              <div class="message-bubble">{{ msg.content }}</div>
            </div>
            
            <!-- Agent 回复 -->
            <div v-else-if="msg.type === 'agent'" class="agent-message">
              <div class="message-bubble">{{ msg.content }}</div>
            </div>
            
            <!-- 可折叠的思考/规划内容 -->
            <div v-else-if="msg.type === 'thinking' || msg.type === 'plan'" class="collapsible-message">
              <div class="collapse-header" @click="toggleCollapse(msg.id)">
                <el-icon>
                  <ArrowRight v-if="msg.collapsed" />
                  <ArrowDown v-else />
                </el-icon>
                <span>{{ msg.type === 'thinking' ? '思考过程' : '执行规划' }}</span>
              </div>
              <div v-show="!msg.collapsed" class="collapse-content">
                <pre>{{ msg.content }}</pre>
              </div>
            </div>
            
            <!-- 工具调用 -->
            <div v-else-if="msg.type === 'tool'" class="tool-message">
              <div class="tool-header" @click="toggleCollapse(msg.id)">
                <el-icon>
                  <ArrowRight v-if="msg.collapsed" />
                  <ArrowDown v-else />
                </el-icon>
                <span>工具调用</span>
              </div>
              <div v-show="!msg.collapsed" class="tool-content">
                <pre>{{ msg.content }}</pre>
              </div>
            </div>
            
            <!-- 系统/错误消息 -->
            <div v-else class="system-message">
              <span>{{ msg.content }}</span>
            </div>
          </div>
        </div>

        <!-- 计划确认区域 -->
        <div v-if="isAwaitingApproval" class="plan-approval">
          <el-alert
            title="等待计划确认"
            type="warning"
            :closable="false"
            class="approval-alert"
          />
          <div class="approval-actions">
            <el-button type="success" size="small" @click="submitPlanAction('agree')">
              同意
            </el-button>
            <el-button type="warning" size="small" @click="submitPlanAction('refine')">
              优化
            </el-button>
            <el-button size="small" @click="submitPlanAction('skip')">
              跳过
            </el-button>
            <el-button type="danger" size="small" @click="submitPlanAction('stop')">
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
            resize="none"
          />
          <el-button
            type="primary"
            :disabled="!inputMessage.trim() || isRunning"
            :loading="isRunning"
            @click="sendMessage"
            class="send-btn"
          >
            <el-icon><Promotion /></el-icon>
          </el-button>
        </div>
      </el-aside>
    </el-container>

    <!-- 创建会话对话框 -->
    <el-dialog v-model="showCreateDialog" title="新建会话" width="400px">
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
import { ref, onMounted, onUnmounted, computed, watch, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAgentStore } from '@/stores'
import { useSessionStore } from '@/stores/session'
import { sessionApi, chatApi, planApi, fileApi, createWebSocketConnection } from '@/api'
import type { FileTreeNode, Plan, Session } from '@/types'

const router = useRouter()
const route = useRoute()
const agentStore = useAgentStore()
const sessionStore = useSessionStore()

const projectId = route.params.projectId as string

// 文件树
const fileTree = ref<FileTreeNode[]>([])
const selectedFile = ref<FileTreeNode | null>(null)
const fileContent = ref('')

// 会话
const sessions = ref<Session[]>([])
const showCreateDialog = ref(false)
const creating = ref(false)
const createForm = ref({ title: '' })
const inputMessage = ref('')
const messagesRef = ref<HTMLElement>()

// 当前会话相关
const currentSessionId = computed({
  get: () => sessionStore.currentSessionId,
  set: (val) => sessionStore.switchSession(val)
})

const currentMessages = computed(() => sessionStore.currentMessages)
const currentAgentState = computed(() => sessionStore.currentAgentState)
const isRunning = computed(() => sessionStore.isRunning)
const isAwaitingApproval = computed(() => sessionStore.isAwaitingApproval)
const currentProject = computed(() => agentStore.currentProject)

// 加载文件树
async function loadFileTree() {
  try {
    const data = await fileApi.getFileTree(projectId)
    fileTree.value = data
  } catch (error) {
    console.error('加载文件树失败', error)
  }
}

// 加载会话列表
async function loadSessions() {
  try {
    const data = await sessionApi.getSessions(projectId)
    sessions.value = data
    
    // 初始化每个会话的状态
    data.forEach(session => {
      sessionStore.initSession(session)
    })
    
    // 默认选择第一个会话
    if (data.length > 0 && !sessionStore.currentSessionId) {
      sessionStore.switchSession(data[0].id)
      connectWebSocket(data[0].id)
    }
  } catch (error) {
    ElMessage.error('加载会话列表失败')
  }
}

// 处理文件点击
function handleFileClick(data: FileTreeNode) {
  if (data.type === 'file') {
    selectedFile.value = data
    // 这里可以调用 API 读取文件内容
    fileContent.value = '// 文件内容加载中...'
  }
}

// 处理会话切换
function handleSessionChange(sessionId: string) {
  // 关闭旧会话的 WebSocket
  const oldState = sessionStore.currentState
  if (oldState?.ws) {
    oldState.ws.close()
  }
  
  // 切换会话
  sessionStore.switchSession(sessionId)
  
  // 连接新会话的 WebSocket
  connectWebSocket(sessionId)
}

// WebSocket 连接
function connectWebSocket(sessionId: string) {
  const state = sessionStore.sessionStates.get(sessionId)
  if (state?.ws?.readyState === WebSocket.OPEN) {
    return
  }
  
  try {
    const ws = createWebSocketConnection(projectId, sessionId)
    sessionStore.setWebSocket(sessionId, ws)
    
    ws.onopen = () => {
      sessionStore.setConnected(sessionId, true)
    }
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        sessionStore.handleWebSocketMessage(sessionId, data)
        scrollToBottom()
      } catch (e) {
        console.error('解析 WebSocket 消息失败:', e)
      }
    }
    
    ws.onclose = () => {
      sessionStore.setConnected(sessionId, false)
    }
    
    ws.onerror = (error) => {
      console.error('WebSocket 错误:', error)
    }
  } catch (error) {
    console.error('创建 WebSocket 失败:', error)
  }
}

// 发送消息
async function sendMessage() {
  if (!inputMessage.value.trim() || !sessionStore.currentSessionId) return
  
  const sessionId = sessionStore.currentSessionId
  const message = inputMessage.value
  
  // 添加用户消息到当前会话
  sessionStore.addMessage(sessionId, { type: 'user', content: message })
  inputMessage.value = ''
  
  try {
    await chatApi.sendMessage(projectId, sessionId, { message })
    // WebSocket 会自动接收响应
  } catch (error) {
    ElMessage.error('发送消息失败')
  }
  
  scrollToBottom()
}

// 提交计划操作
async function submitPlanAction(action: 'agree' | 'refine' | 'skip' | 'stop') {
  const sessionId = sessionStore.currentSessionId
  if (!sessionId) return
  
  const plans = sessionStore.currentPlans
  if (plans.length === 0) return
  
  try {
    await planApi.submitAction(projectId, sessionId, plans[0].id, { action })
    ElMessage.success(`已提交操作: ${action}`)
  } catch (error) {
    ElMessage.error('提交操作失败')
  }
}

// 切换折叠
function toggleCollapse(messageId: string) {
  const sessionId = sessionStore.currentSessionId
  if (sessionId) {
    sessionStore.toggleMessageCollapse(sessionId, messageId)
  }
}

// 滚动到底部
function scrollToBottom() {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
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

function goBack() {
  router.push('/')
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
    sessions.value.push(data)
    sessionStore.initSession(data)
    sessionStore.switchSession(data.id)
    connectWebSocket(data.id)
    
    ElMessage.success('会话创建成功')
    showCreateDialog.value = false
    createForm.value.title = ''
  } catch (error) {
    ElMessage.error('创建会话失败')
  } finally {
    creating.value = false
  }
}

onMounted(() => {
  loadFileTree()
  loadSessions()
})

onUnmounted(() => {
  // 关闭所有 WebSocket 连接
  sessionStore.sessionStates.forEach((state) => {
    if (state.ws) {
      state.ws.close()
    }
  })
})
</script>

<style scoped lang="scss">
.project-workspace {
  height: 100vh;
  background-color: #f5f7fa;
}

.workspace-container {
  height: 100%;
}

// 左侧文件树
.file-sidebar {
  background-color: #fff;
  border-right: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;

  .sidebar-header {
    padding: 12px 16px;
    border-bottom: 1px solid #e4e7ed;
    display: flex;
    align-items: center;
    gap: 8px;

    .back-btn {
      padding: 4px;
    }

    .project-name {
      font-weight: 600;
      font-size: 14px;
      color: #303133;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }

  .file-tree-container {
    flex: 1;
    padding: 12px;
    overflow-y: auto;

    .tree-title {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 12px;
      color: #606266;
      font-size: 13px;
      font-weight: 500;
    }

    .file-tree {
      font-size: 13px;
    }
  }
}

// 中间内容区
.content-area {
  background-color: #fff;
  padding: 0;
  display: flex;
  flex-direction: column;

  .file-content {
    height: 100%;
    display: flex;
    flex-direction: column;

    .file-header {
      padding: 12px 16px;
      border-bottom: 1px solid #e4e7ed;
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 14px;
      color: #303133;
      background-color: #fafafa;
    }

    .code-block {
      flex: 1;
      padding: 16px;
      margin: 0;
      overflow: auto;
      font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
      font-size: 13px;
      line-height: 1.6;
      color: #333;
      background-color: #fafafa;
    }
  }

  .empty-content {
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
  }
}

// 右侧会话区
.session-sidebar {
  background-color: #fff;
  border-left: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;

  .session-header {
    padding: 12px;
    border-bottom: 1px solid #e4e7ed;

    .session-select {
      display: flex;
      gap: 8px;
      align-items: center;

      .session-select-box {
        flex: 1;
      }
    }
  }

  .session-messages {
    flex: 1;
    overflow-y: auto;
    padding: 12px;
    background-color: #f5f7fa;

    .empty-messages {
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .message-item {
      margin-bottom: 12px;

      &.user {
        .user-message {
          display: flex;
          justify-content: flex-end;

          .message-bubble {
            background-color: #409eff;
            color: #fff;
            padding: 8px 12px;
            border-radius: 12px 12px 2px 12px;
            max-width: 80%;
            word-break: break-word;
          }
        }
      }

      &.agent {
        .agent-message {
          display: flex;
          justify-content: flex-start;

          .message-bubble {
            background-color: #fff;
            color: #303133;
            padding: 8px 12px;
            border-radius: 12px 12px 12px 2px;
            max-width: 80%;
            word-break: break-word;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
          }
        }
      }

      &.thinking, &.plan, &.tool {
        .collapsible-message, .tool-message {
          background-color: #fff;
          border-radius: 8px;
          border: 1px solid #e4e7ed;
          overflow: hidden;

          .collapse-header, .tool-header {
            padding: 8px 12px;
            display: flex;
            align-items: center;
            gap: 8px;
            cursor: pointer;
            background-color: #f5f7fa;
            font-size: 12px;
            color: #606266;
            font-weight: 500;

            &:hover {
              background-color: #e4e7ed;
            }
          }

          .collapse-content, .tool-content {
            padding: 12px;
            font-size: 12px;
            color: #606266;

            pre {
              margin: 0;
              white-space: pre-wrap;
              word-break: break-word;
              font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            }
          }
        }
      }

      &.system, &.error {
        .system-message {
          text-align: center;
          padding: 4px 8px;
          font-size: 12px;
          color: #909399;
        }
      }

      &.error {
        .system-message {
          color: #f56c6c;
        }
      }
    }
  }

  .plan-approval {
    padding: 12px;
    border-top: 1px solid #e4e7ed;
    background-color: #fdf6ec;

    .approval-alert {
      margin-bottom: 8px;
    }

    .approval-actions {
      display: flex;
      gap: 8px;
      justify-content: center;
    }
  }

  .input-area {
    padding: 12px;
    border-top: 1px solid #e4e7ed;
    display: flex;
    gap: 8px;
    align-items: flex-end;

    .send-btn {
      height: 40px;
      width: 40px;
      padding: 0;
      display: flex;
      align-items: center;
      justify-content: center;
    }
  }
}

.session-option {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>