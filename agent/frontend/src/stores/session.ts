import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Session, Plan, AgentState, WebSocketMessage } from '@/types'

export interface SessionMessage {
  id: string
  type: 'user' | 'agent' | 'thinking' | 'plan' | 'tool' | 'error' | 'system'
  content: string
  timestamp: number
  metadata?: Record<string, any>
  collapsed?: boolean
}

export interface SessionState {
  session: Session | null
  agentState: AgentState | null
  messages: SessionMessage[]
  plans: Plan[]
  wsConnected: boolean
  ws: WebSocket | null
}

export const useSessionStore = defineStore('session', () => {
  // 使用 Map 存储每个会话的状态，实现真正的会话隔离
  const sessionStates = ref<Map<string, SessionState>>(new Map())
  const currentSessionId = ref<string>('')

  // 当前会话的状态
  const currentState = computed<SessionState | undefined>(() => {
    if (!currentSessionId.value) return undefined
    return sessionStates.value.get(currentSessionId.value)
  })

  const currentSession = computed(() => currentState.value?.session || null)
  const currentAgentState = computed(() => currentState.value?.agentState || null)
  const currentMessages = computed(() => currentState.value?.messages || [])
  const currentPlans = computed(() => currentState.value?.plans || [])
  const isConnected = computed(() => currentState.value?.wsConnected || false)
  const isRunning = computed(() => currentAgentState.value?.status === 'running')
  const isAwaitingApproval = computed(() => currentAgentState.value?.status === 'awaiting_approval')

  // 初始化会话状态
  function initSession(session: Session) {
    if (!sessionStates.value.has(session.id)) {
      sessionStates.value.set(session.id, {
        session,
        agentState: null,
        messages: [],
        plans: [],
        wsConnected: false,
        ws: null,
      })
    }
    currentSessionId.value = session.id
  }

  // 切换当前会话
  function switchSession(sessionId: string) {
    currentSessionId.value = sessionId
  }

  // 设置 WebSocket
  function setWebSocket(sessionId: string, ws: WebSocket | null) {
    const state = sessionStates.value.get(sessionId)
    if (state) {
      state.ws = ws
    }
  }

  // 设置连接状态
  function setConnected(sessionId: string, connected: boolean) {
    const state = sessionStates.value.get(sessionId)
    if (state) {
      state.wsConnected = connected
    }
  }

  // 设置 Agent 状态
  function setAgentState(sessionId: string, agentState: AgentState | null) {
    const state = sessionStates.value.get(sessionId)
    if (state) {
      state.agentState = agentState
    }
  }

  // 添加消息
  function addMessage(sessionId: string, message: Omit<SessionMessage, 'id' | 'timestamp'>) {
    const state = sessionStates.value.get(sessionId)
    if (state) {
      state.messages.push({
        ...message,
        id: `${sessionId}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        timestamp: Date.now(),
        collapsed: message.type === 'thinking' || message.type === 'plan',
      })
    }
  }

  // 切换消息折叠状态
  function toggleMessageCollapse(sessionId: string, messageId: string) {
    const state = sessionStates.value.get(sessionId)
    if (state) {
      const msg = state.messages.find(m => m.id === messageId)
      if (msg) {
        msg.collapsed = !msg.collapsed
      }
    }
  }

  // 设置计划
  function setPlans(sessionId: string, plans: Plan[]) {
    const state = sessionStates.value.get(sessionId)
    if (state) {
      state.plans = plans
    }
  }

  // 清除会话状态
  function clearSession(sessionId: string) {
    sessionStates.value.delete(sessionId)
    if (currentSessionId.value === sessionId) {
      currentSessionId.value = ''
    }
  }

  // 处理 WebSocket 消息
  function handleWebSocketMessage(sessionId: string, data: WebSocketMessage) {
    if (data.error) {
      addMessage(sessionId, { type: 'error', content: data.error })
      return
    }

    if (data.phase) {
      switch (data.phase) {
        case 'start':
          addMessage(sessionId, { type: 'system', content: data.message || 'Agent 开始执行' })
          break
        case 'done':
          addMessage(sessionId, { type: 'agent', content: data.final_answer || data.message || '任务完成' })
          break
        case 'cancelled':
          addMessage(sessionId, { type: 'system', content: data.message || 'Agent 已终止' })
          break
      }
    }

    if (data.type === 'trace' && data.data) {
      const { phase, content } = data.data
      let msgType: SessionMessage['type'] = 'thinking'
      
      if (phase === 'plan' || phase === 'plan_result') {
        msgType = 'plan'
      } else if (phase === 'act') {
        msgType = 'tool'
      } else if (phase === 'observe') {
        msgType = 'tool'
      }

      addMessage(sessionId, { 
        type: msgType, 
        content: `[${phase}] ${content}`,
        metadata: { phase, rawContent: content }
      })
    }

    if (data.status) {
      const state = sessionStates.value.get(sessionId)
      if (state && state.agentState) {
        state.agentState.status = data.status
      }
    }
  }

  return {
    sessionStates,
    currentSessionId,
    currentState,
    currentSession,
    currentAgentState,
    currentMessages,
    currentPlans,
    isConnected,
    isRunning,
    isAwaitingApproval,
    initSession,
    switchSession,
    setWebSocket,
    setConnected,
    setAgentState,
    addMessage,
    toggleMessageCollapse,
    setPlans,
    clearSession,
    handleWebSocketMessage,
  }
})