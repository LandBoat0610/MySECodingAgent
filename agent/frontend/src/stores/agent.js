import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  getProjects,
  createProject,
  deleteProject,
  getSessions,
  createSession,
  updateSession,
  deleteSession,
  clearSession,
  getSessionState,
  sendChat,
  getPlans,
  getRounds,
  planAction,
  commandApproval,
  continueApproval,
  getFileTree,
  getFileContent,
  stopSession,
  createWebSocket,
  getToolSettings,
  updateToolSettings,
  getSkills,
  createSkill,
  updateSkill,
  deleteSkill,
  getMemoryContext,
  getProjectMemory,
  getProjectHistory,
  getUserPreferences,
} from '../api/index.js'
import { persistProjectId, getPersistedProjectId, persistSessionId, getPersistedSessionId } from '../utils/persistence.js'

const ROUND_PAGE_SIZE = 8

export const useAgentStore = defineStore('agent', () => {
  const projects = ref([])
  const selectedProjectId = ref(getPersistedProjectId())
  const sessions = ref([])
  const selectedSessionId = ref(getPersistedSessionId())
  const sessionStatus = ref('idle')
  const stateSnapshot = ref(null)
  const fileTree = ref([])
  const plans = ref([])
  const traceLogs = ref([])
  const chatMessages = ref([])
  const finalAnswer = ref('')
  const ragSources = ref([])        // RAG 知识来源
  const memorySummary = ref('')     // 记忆摘要
  const agentRunning = ref(false)
  const wsConnection = ref(null)
  const loading = ref(false)
  const error = ref(null)
  const wsReconnectAttempts = ref(0)
  const WS_MAX_RECONNECT = 5
  const wsIntentionalClose = ref(false)
  const selectedFile = ref(null)
  const fileContent = ref('')
  const fileLoading = ref(false)
  const sessionSearch = ref('')
  const toolSettings = ref([])
  const toolSettingsLoading = ref(false)
  const skills = ref([])
  const skillsLoading = ref(false)

  /** 多轮对话追踪 */
  const completedRounds = ref([])     // [{userMessage, traceLogs, plans, finalAnswer}]
  const currentRoundUserMsg = ref('') // 当前轮次用户输入
  const prevRoundPlanIds = ref(new Set()) // 上一轮已归档的 plan ID 集合
  const roundsCursor = ref(null)
  const roundsHasMore = ref(false)
  const roundsLoadingOlder = ref(false)

  /** 跨对话记忆与上下文工程 */
  const sessionSummary = ref('')       // 当前会话摘要
  const projectMemory = ref('')        // 项目记忆文本
  const userPreferences = ref('')      // 用户偏好文本
  const relevantHistory = ref([])      // 历史对话列表
  const contextBudget = ref(12000)     // 上下文预算
  const memoryLoading = ref(false)     // 记忆加载状态

  /** WebSocket「本轮」开始时间戳（毫秒），用于 IDE 实时评测悬浮层耗时 */
  const agentRunStartedAt = ref(null)
  /** 由轨迹 meta / 会话快照合并的运行时指标摘要 */
  const livePerf = ref({
    tokensTotal: 0,
    toolEventsCount: 0,
    toolSuccessRate: null,
    toolAvgLatencyMs: null
  })

  const selectedProject = computed(() => projects.value.find(p => p.id === selectedProjectId.value) || null)
  const selectedSession = computed(() => sessions.value.find(s => s.id === selectedSessionId.value) || null)
  const filteredSessions = computed(() => {
    const q = sessionSearch.value.trim().toLowerCase()
    if (!q) return sessions.value
    return sessions.value.filter(s => String(s.title || '').toLowerCase().includes(q))
  })
  const pendingPlans = computed(() => plans.value.filter(p => p.status === 'pending'))
  const pendingCommandApproval = computed(() => {
    const pending = stateSnapshot.value?.pending_tool_approval
    return pending && pending.status === 'pending' ? pending : null
  })
  const pendingLoopApproval = computed(() => {
    const pending = stateSnapshot.value?.pending_loop_approval
    return pending && pending.status === 'pending' ? pending : null
  })

  function setError(err) {
    error.value = typeof err === 'string' ? err : (err.response?.data?.detail || err.message || 'Unknown error')
    console.error(error.value)
  }

  function clearError() {
    error.value = null
  }

  async function fetchProjects() {
    loading.value = true
    clearError()
    try {
      projects.value = await getProjects()
      if (selectedProjectId.value && projects.value.length > 0 && !projects.value.find(p => p.id === selectedProjectId.value)) {
        selectedProjectId.value = null
        persistProjectId(null)
      }
    } catch (e) {
      setError(e)
    } finally {
      loading.value = false
    }
  }

  async function doCreateProject(data) {
    clearError()
    const project = await createProject(data)
    projects.value.unshift(project)
    selectProject(project.id)
    return project
  }

  function syncLivePerfFromSnapshot() {
    const rm = stateSnapshot.value?.runtime_metrics
    if (!rm || typeof rm !== 'object') return
    const ev = rm.tool_calls || []
    const ok = ev.filter(e => e && e.ok).length
    livePerf.value = {
      tokensTotal: rm.tokens?.total ?? livePerf.value.tokensTotal,
      toolEventsCount: ev.length,
      toolSuccessRate: ev.length ? ok / ev.length : null,
      toolAvgLatencyMs: ev.length
        ? Math.round(ev.reduce((s, x) => s + (Number(x.latency_ms) || 0), 0) / ev.length)
        : null
    }
  }

  function resetLivePerfForNewRun() {
    livePerf.value = {
      tokensTotal: 0,
      toolEventsCount: 0,
      toolSuccessRate: null,
      toolAvgLatencyMs: null
    }
  }

  function resetRoundPaging() {
    roundsCursor.value = null
    roundsHasMore.value = false
    roundsLoadingOlder.value = false
  }

  function selectProject(projectId) {
    disconnectWebSocket()
    selectedProjectId.value = projectId
    persistProjectId(projectId)
    selectedSessionId.value = null
    persistSessionId(null)
    sessions.value = []
    fileTree.value = []
    plans.value = []
    traceLogs.value = []
    chatMessages.value = []
    finalAnswer.value = ''
    ragSources.value = []
    memorySummary.value = ''
    sessionStatus.value = 'idle'
    stateSnapshot.value = null
    selectedFile.value = null
    fileContent.value = ''
    agentRunStartedAt.value = null
    completedRounds.value = []
    currentRoundUserMsg.value = ''
    prevRoundPlanIds.value = new Set()
    resetRoundPaging()
    resetLivePerfForNewRun()
    fetchSessions()
    fetchFileTree()
  }

  async function fetchSessions() {
    if (!selectedProjectId.value) return
    clearError()
    try {
      sessions.value = await getSessions(selectedProjectId.value)
      if (selectedSessionId.value && sessions.value.length > 0 && !sessions.value.find(s => s.id === selectedSessionId.value)) {
        selectedSessionId.value = null
        persistSessionId(null)
      }
    } catch (e) {
      setError(e)
    }
  }

  async function doCreateSession(title) {
    clearError()
    const session = await createSession(selectedProjectId.value, { title })
    sessions.value.unshift(session)
    selectSession(session.id)
    return session
  }

  async function doRenameSession(sessionId, title) {
    if (!selectedProjectId.value) return null
    clearError()
    try {
      const updated = await updateSession(selectedProjectId.value, sessionId, { title })
      const idx = sessions.value.findIndex(s => s.id === sessionId)
      if (idx >= 0) sessions.value[idx] = updated
      return updated
    } catch (e) {
      setError(e)
      throw e
    }
  }

  async function doTogglePinSession(sessionId) {
    if (!selectedProjectId.value) return null
    const session = sessions.value.find(s => s.id === sessionId)
    if (!session) return null
    clearError()
    try {
      const updated = await updateSession(selectedProjectId.value, sessionId, { pinned: !session.pinned })
      const idx = sessions.value.findIndex(s => s.id === sessionId)
      if (idx >= 0) sessions.value[idx] = updated
      sessions.value = [...sessions.value].sort(
        (a, b) => Number(b.pinned) - Number(a.pinned) || new Date(b.created_at) - new Date(a.created_at)
      )
      return updated
    } catch (e) {
      setError(e)
      throw e
    }
  }

  async function doDeleteSession(sessionId) {
    if (!selectedProjectId.value) return
    clearError()
    try {
      await deleteSession(selectedProjectId.value, sessionId)
      if (selectedSessionId.value === sessionId) {
        startNewSession()
      }
      sessions.value = sessions.value.filter(s => s.id !== sessionId)
    } catch (e) {
      setError(e)
      throw e
    }
  }

  async function doClearSession(sessionId) {
    if (!selectedProjectId.value) return
    clearError()
    try {
      await clearSession(selectedProjectId.value, sessionId)
      const session = sessions.value.find(s => s.id === sessionId)
      if (session) session.status = 'idle'
      if (selectedSessionId.value === sessionId) {
        plans.value = []
        traceLogs.value = []
        chatMessages.value = []
        finalAnswer.value = ''
        stateSnapshot.value = null
        sessionStatus.value = 'idle'
        agentRunning.value = false
        completedRounds.value = []
        currentRoundUserMsg.value = ''
        prevRoundPlanIds.value = new Set()
        resetRoundPaging()
        resetLivePerfForNewRun()
      }
    } catch (e) {
      setError(e)
      throw e
    }
  }

  function startNewSession() {
    disconnectWebSocket()
    selectedSessionId.value = null
    persistSessionId(null)
    plans.value = []
    traceLogs.value = []
    chatMessages.value = []
    finalAnswer.value = ''
    ragSources.value = []
    memorySummary.value = ''
    stateSnapshot.value = null
    sessionStatus.value = 'idle'
    agentRunning.value = false
    agentRunStartedAt.value = null
    completedRounds.value = []
    currentRoundUserMsg.value = ''
    prevRoundPlanIds.value = new Set()
    resetRoundPaging()
    resetLivePerfForNewRun()
  }

  async function selectSession(sessionId) {
    disconnectWebSocket()
    selectedSessionId.value = sessionId
    persistSessionId(sessionId)
    plans.value = []
    traceLogs.value = []
    chatMessages.value = []
    finalAnswer.value = ''
    stateSnapshot.value = null
    agentRunning.value = false
    agentRunStartedAt.value = null
    completedRounds.value = []
    currentRoundUserMsg.value = ''
    prevRoundPlanIds.value = new Set()
    resetRoundPaging()
    resetLivePerfForNewRun()
    await restoreSessionState()
  }

  async function restoreSessionState() {
    if (!selectedProjectId.value || !selectedSessionId.value) return
    try {
      const stateResp = await getSessionState(selectedProjectId.value, selectedSessionId.value)
      sessionStatus.value = stateResp.status
      stateSnapshot.value = stateResp.snapshot

      const msgs = stateResp.snapshot?.messages || []
      chatMessages.value = msgs
        .filter(m => {
          if (m.role === 'system') return false
          if (m.role === 'tool') return false
          if (m.role === 'user' && m.content?.startsWith('Current step:')) return false
          if (m.role === 'assistant' && !m.content?.trim()) return false
          return true
        })
        .map(m => ({
          role: m.role,
          content: m.content,
          tool_calls: m.tool_calls || null
        }))

      await fetchRounds()
      if (completedRounds.value.length === 0 && !currentRoundUserMsg.value) {
        await fetchPlans()
      }

      if (['running', 'awaiting_approval', 'awaiting_tool_approval', 'awaiting_continue_approval', 'approved', 'needs_fix', 'next_step'].includes(stateResp.status)) {
        connectWebSocket()
      }

      if (stateResp.snapshot?.final_answer) {
        finalAnswer.value = stateResp.snapshot.final_answer
      }
      // 只在 Agent 未运行时才用快照覆盖实时轨迹，避免重连后内容突变
      if (!agentRunning.value && stateResp.snapshot?.trace) {
        traceLogs.value = stateResp.snapshot.trace || []
      }
      syncLivePerfFromSnapshot()
    } catch (e) {
      setError(e)
    }
  }

  async function fetchFileTree() {
    if (!selectedProjectId.value) return
    try {
      fileTree.value = await getFileTree(selectedProjectId.value)
    } catch (e) {
      setError(e)
    }
  }

  async function fetchPlans() {
    if (!selectedProjectId.value || !selectedSessionId.value) return
    try {
      plans.value = await getPlans(selectedProjectId.value, selectedSessionId.value)
    } catch (e) {
      setError(e)
    }
  }

  function mapRound(r) {
    return {
      id: r.id,
      createdAt: r.created_at,
      userMessage: r.user_message,
      traceLogs: r.trace_json || [],
      plans: r.plans || [],
      finalAnswer: r.final_answer || '',
      status: r.status,
    }
  }

  function applyRoundPage(mapped, appendOlder = false) {
    const activeStatuses = new Set(['running', 'awaiting_approval', 'awaiting_tool_approval', 'awaiting_continue_approval', 'approved', 'needs_fix', 'next_step'])
    const last = mapped[mapped.length - 1]
    const hasActiveRound = last && activeStatuses.has(last.status)

    if (appendOlder) {
      completedRounds.value = [...mapped, ...completedRounds.value]
      if (mapped.length > 0) roundsCursor.value = mapped[0].createdAt
      roundsHasMore.value = mapped.length >= ROUND_PAGE_SIZE
      prevRoundPlanIds.value = new Set(completedRounds.value.flatMap(r => (r.plans || []).map(p => p.id)))
      return
    }

    completedRounds.value = hasActiveRound ? mapped.slice(0, -1) : mapped
    if (hasActiveRound) {
      currentRoundUserMsg.value = last.userMessage
      traceLogs.value = last.traceLogs
      plans.value = last.plans
      finalAnswer.value = last.finalAnswer
    } else {
      currentRoundUserMsg.value = ''
      traceLogs.value = []
      plans.value = []
      finalAnswer.value = ''
    }
    roundsCursor.value = mapped[0]?.createdAt || null
    roundsHasMore.value = mapped.length >= ROUND_PAGE_SIZE
    prevRoundPlanIds.value = new Set(completedRounds.value.flatMap(r => (r.plans || []).map(p => p.id)))
  }

  async function fetchRounds(options = {}) {
    if (!selectedProjectId.value || !selectedSessionId.value) return
    try {
      const appendOlder = !!options.appendOlder
      const rounds = await getRounds(selectedProjectId.value, selectedSessionId.value, {
        limit: ROUND_PAGE_SIZE,
        before: appendOlder ? roundsCursor.value : '',
      })
      applyRoundPage((rounds || []).map(mapRound), appendOlder)
    } catch (e) {
      setError(e)
    }
  }

  async function loadOlderRounds() {
    if (!roundsHasMore.value || roundsLoadingOlder.value || !roundsCursor.value) return false
    roundsLoadingOlder.value = true
    try {
      await fetchRounds({ appendOlder: true })
      return true
    } finally {
      roundsLoadingOlder.value = false
    }
  }

  /** 跨对话记忆：加载记忆上下文 */
  async function fetchMemoryContext() {
    if (!selectedProjectId.value) return
    memoryLoading.value = true
    try {
      const ctx = await getMemoryContext(
        selectedProjectId.value,
        selectedSessionId.value || ''
      )
      sessionSummary.value = ctx.session_summary || ''
      projectMemory.value = ctx.project_memory || ''
      userPreferences.value = ctx.user_preferences || ''
      relevantHistory.value = ctx.relevant_history || []
      contextBudget.value = ctx.context_budget || 12000
    } catch (e) {
      console.warn('Failed to load memory context:', e)
    } finally {
      memoryLoading.value = false
    }
  }

  function connectWebSocket() {
    if (!selectedProjectId.value || !selectedSessionId.value) return

    if (wsConnection.value) {
      wsIntentionalClose.value = true
      try { wsConnection.value.close() } catch (e) { /* ignore */ }
      wsConnection.value = null
    }

    wsIntentionalClose.value = false
    agentRunning.value = true
    wsReconnectAttempts.value = 0
    const ws = createWebSocket(selectedProjectId.value, selectedSessionId.value)
    wsConnection.value = ws

    ws.onopen = () => {
      console.log('WebSocket connected')
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)

        if (data.error) {
          if (data.code === 'AGENT_STOPPING') {
            sessionStatus.value = 'stopping'
          }
          setError(data.error)
          agentRunning.value = false
          agentRunStartedAt.value = null
          return
        }

        if (data.type === 'trace' && data.data) {
          traceLogs.value.push(data.data)
          const meta = data.data.meta || {}
          // 提取 RAG 来源
          if (meta.rag_sources && Array.isArray(meta.rag_sources)) {
            ragSources.value = [...ragSources.value, ...meta.rag_sources]
          }
          // 提取记忆摘要
          if (meta.memory_summary) {
            memorySummary.value = meta.memory_summary
          }
          if (
            meta.tokens_total != null ||
            meta.tool_events_count != null ||
            meta.tool_success_rate != null ||
            meta.tool_avg_latency_ms != null
          ) {
            livePerf.value = {
              tokensTotal: meta.tokens_total ?? livePerf.value.tokensTotal,
              toolEventsCount: meta.tool_events_count ?? livePerf.value.toolEventsCount,
              toolSuccessRate:
                meta.tool_success_rate != null ? meta.tool_success_rate : livePerf.value.toolSuccessRate,
              toolAvgLatencyMs:
                meta.tool_avg_latency_ms != null
                  ? meta.tool_avg_latency_ms
                  : livePerf.value.toolAvgLatencyMs
            }
          }
          if (data.data.phase === 'tool_approval' && meta.pending_tool_approval) {
            stateSnapshot.value = {
              ...(stateSnapshot.value || {}),
              status: data.data.session_status || 'awaiting_tool_approval',
              pending_tool_approval: meta.pending_tool_approval,
            }
            sessionStatus.value = data.data.session_status || 'awaiting_tool_approval'
          }
          if (data.data.session_status) {
            sessionStatus.value = data.data.session_status
            if (data.data.session_status === 'awaiting_approval') {
              fetchPlans()
            }
            if (data.data.session_status === 'awaiting_tool_approval') {
              restoreSessionState()
            }
            if (data.data.session_status === 'awaiting_continue_approval') {
              restoreSessionState()
            }
          }
          // Agent 完成一个步骤后刷新文件树（及时展示新建/修改的文件）
          if (data.data.phase === 'finish_step') {
            fetchFileTree()
          }
        }

        if (data.phase === 'start') {
          agentRunning.value = true
          // 不在此处清空 traceLogs，避免重连后覆盖已有轨迹
          // 清空动作统一由 doSendChat 在发送新任务时负责
          if (!agentRunStartedAt.value) {
            agentRunStartedAt.value = Date.now()
            resetLivePerfForNewRun()
          }
        }

        if (data.phase === 'done') {
          wsIntentionalClose.value = true
          agentRunning.value = false
          agentRunStartedAt.value = null
          finalAnswer.value = data.final_answer || ''
          sessionStatus.value = data.status || 'completed'
          fetchPlans()
          restoreSessionState()
          fetchSessions()
          // Agent 结束后：刷新文件树，并刷新当前打开的文件内容
          fetchFileTree()
          if (selectedFile.value) {
            fetchFileContent(selectedFile.value.path)
          }
        }

        if (data.phase === 'cancelled') {
          wsIntentionalClose.value = true
          agentRunning.value = false
          agentRunStartedAt.value = null
          sessionStatus.value = 'stopped'
          fetchPlans()
          restoreSessionState()
          fetchSessions()
        }
      } catch (e) {
        console.error('WebSocket message parse error:', e)
      }
    }

    ws.onclose = () => {
      console.log('WebSocket disconnected')
      wsConnection.value = null
      if (wsIntentionalClose.value) {
        wsIntentionalClose.value = false
        agentRunning.value = false
        agentRunStartedAt.value = null
        return
      }
      const activeStates = ['running', 'awaiting_approval', 'awaiting_tool_approval', 'awaiting_continue_approval', 'approved', 'needs_fix', 'next_step']
      if (activeStates.includes(sessionStatus.value)) {
        wsReconnectAttempts.value++
        if (wsReconnectAttempts.value <= WS_MAX_RECONNECT) {
          setTimeout(() => {
            connectWebSocket()
          }, 2000 * wsReconnectAttempts.value)
        } else {
          agentRunning.value = false
          agentRunStartedAt.value = null
          setError('WebSocket 连接断开，已达到最大重连次数，请手动刷新页面')
        }
      } else {
        agentRunning.value = false
        agentRunStartedAt.value = null
      }
    }

    ws.onerror = (err) => {
      console.error('WebSocket error:', err)
      agentRunning.value = false
      agentRunStartedAt.value = null
    }
  }

  function disconnectWebSocket() {
    wsIntentionalClose.value = true
    if (wsConnection.value) {
      try { wsConnection.value.close() } catch (e) { /* ignore */ }
      wsConnection.value = null
    }
    agentRunning.value = false
    agentRunStartedAt.value = null
  }

  async function doSendChat(message) {
    clearError()
    if (!selectedProjectId.value) {
      const e = new Error('请先选择或创建一个项目')
      setError(e)
      throw e
    }
    if (!selectedSessionId.value || sessionStatus.value === 'stopped') {
      const session = await createSession(selectedProjectId.value, { initial_message: message })
      sessions.value.unshift(session)
      selectedSessionId.value = session.id
      persistSessionId(session.id)
      sessionStatus.value = session.status || 'idle'
    }
    // 将当前轮归档到历史（如果本轮已有用户消息）
    if (currentRoundUserMsg.value) {
      completedRounds.value.push({
        userMessage: currentRoundUserMsg.value,
        traceLogs: [...traceLogs.value],
        plans: [...plans.value].filter(p => !prevRoundPlanIds.value.has(p.id)),
        finalAnswer: finalAnswer.value,
      })
    }
    // 记录上一轮的 plan ID 集合，新一轮的 taskList 只显示更新后的 plan
    prevRoundPlanIds.value = new Set(plans.value.map(p => p.id))
    // 重置当前轮状态
    traceLogs.value = []
    finalAnswer.value = ''
    plans.value = []
    stateSnapshot.value = null   // 清空旧快照，防止前端读到上一轮的 task_list / status
    currentRoundUserMsg.value = message
    agentRunStartedAt.value = null
    resetLivePerfForNewRun()
    chatMessages.value.push({ role: 'user', content: message })
    try {
      const resp = await sendChat(selectedProjectId.value, selectedSessionId.value, message)
      sessionStatus.value = resp.status
      connectWebSocket()
      return resp
    } catch (e) {
      chatMessages.value.pop()
      currentRoundUserMsg.value = ''
      setError(e)
      throw e
    }
  }

  async function doPlanAction(planId, action, feedback = '') {
    clearError()
    try {
      const resp = await planAction(selectedProjectId.value, selectedSessionId.value, planId, action, feedback)
      const plan = plans.value.find(p => p.id === planId)
      if (plan) {
        plan.status = resp.status
      }
      if (action === 'agree' || action === 'refine') {
        sessionStatus.value = 'running'
        connectWebSocket()
      } else if (action === 'stop') {
        sessionStatus.value = 'stopped'
        agentRunning.value = false
        disconnectWebSocket()
      } else if (action === 'skip') {
        sessionStatus.value = 'skipped'
        agentRunning.value = false
      }
      return resp
    } catch (e) {
      setError(e)
      throw e
    }
  }

  async function doCommandApproval(approvalId, action, feedback = '') {
    clearError()
    try {
      const resp = await commandApproval(selectedProjectId.value, selectedSessionId.value, approvalId, action, feedback)
      if (stateSnapshot.value?.pending_tool_approval?.id === approvalId) {
        stateSnapshot.value.pending_tool_approval.status = resp.status
        stateSnapshot.value.pending_tool_approval.feedback = feedback
      }
      sessionStatus.value = 'running'
      connectWebSocket()
      return resp
    } catch (e) {
      setError(e)
      throw e
    }
  }

  async function doContinueApproval(approvalId, action) {
    clearError()
    try {
      const resp = await continueApproval(selectedProjectId.value, selectedSessionId.value, approvalId, action)
      if (stateSnapshot.value?.pending_loop_approval?.id === approvalId) {
        stateSnapshot.value.pending_loop_approval.status = resp.status
      }
      sessionStatus.value = action === 'continue' ? 'running' : 'stopped'
      if (action === 'continue') {
        connectWebSocket()
      } else {
        agentRunning.value = false
        disconnectWebSocket()
      }
      return resp
    } catch (e) {
      setError(e)
      throw e
    }
  }

  async function doStopSession() {
    clearError()
    try {
      await stopSession(selectedProjectId.value, selectedSessionId.value)
      sessionStatus.value = 'stopped'
      agentRunning.value = false
      disconnectWebSocket()
    } catch (e) {
      setError(e)
    }
  }

  async function doDeleteProject(projectId) {
    clearError()
    try {
      await deleteProject(projectId)
      if (selectedProjectId.value === projectId) {
        disconnectWebSocket()
        selectedProjectId.value = null
        persistProjectId(null)
        selectedSessionId.value = null
        persistSessionId(null)
        sessions.value = []
        fileTree.value = []
        plans.value = []
        traceLogs.value = []
        chatMessages.value = []
        finalAnswer.value = ''
        sessionStatus.value = 'idle'
        stateSnapshot.value = null
        selectedFile.value = null
        fileContent.value = ''
      }
      projects.value = projects.value.filter(p => p.id !== projectId)
    } catch (e) {
      setError(e)
      throw e
    }
  }

  async function fetchFileContent(filePath) {
    if (!selectedProjectId.value) return
    fileLoading.value = true
    clearError()
    try {
      const resp = await getFileContent(selectedProjectId.value, filePath)
      selectedFile.value = { path: filePath, type: 'file' }
      fileContent.value = resp.content
    } catch (e) {
      selectedFile.value = { path: filePath, type: 'file' }
      fileContent.value = ''
      if (e.response?.data?.detail) {
        setError(e.response.data.detail)
      } else {
        setError(e)
      }
    } finally {
      fileLoading.value = false
    }
  }

  function addAssistantMessage(content) {
    chatMessages.value.push({ role: 'assistant', content })
  }

  async function fetchToolSettings() {
    clearError()
    toolSettingsLoading.value = true
    try {
      const resp = await getToolSettings()
      toolSettings.value = resp.tools || []
    } catch (e) {
      setError(e)
    } finally {
      toolSettingsLoading.value = false
    }
  }

  async function setToolEnabled(name, enabled) {
    clearError()
    const prev = toolSettings.value.map(t => ({ ...t }))
    toolSettings.value = toolSettings.value.map(t => t.name === name ? { ...t, enabled } : t)
    try {
      const resp = await updateToolSettings({ tools: { [name]: enabled } })
      toolSettings.value = resp.tools || toolSettings.value
    } catch (e) {
      toolSettings.value = prev
      setError(e)
      throw e
    }
  }

  async function fetchSkills() {
    clearError()
    skillsLoading.value = true
    try {
      const resp = await getSkills()
      skills.value = resp.skills || []
    } catch (e) {
      setError(e)
    } finally {
      skillsLoading.value = false
    }
  }

  async function doCreateSkill(data) {
    clearError()
    try {
      const skill = await createSkill(data)
      skills.value.push(skill)
      return skill
    } catch (e) {
      setError(e)
      throw e
    }
  }

  async function doUpdateSkill(skillId, data) {
    clearError()
    try {
      const updated = await updateSkill(skillId, data)
      const idx = skills.value.findIndex(s => s.id === skillId)
      if (idx >= 0) skills.value[idx] = updated
      return updated
    } catch (e) {
      setError(e)
      throw e
    }
  }

  async function doDeleteSkill(skillId) {
    clearError()
    try {
      await deleteSkill(skillId)
      skills.value = skills.value.filter(s => s.id !== skillId)
    } catch (e) {
      setError(e)
      throw e
    }
  }

  return {
    projects,
    selectedProjectId,
    sessions,
    filteredSessions,
    sessionSearch,
    selectedSessionId,
    sessionStatus,
    stateSnapshot,
    fileTree,
    plans,
    traceLogs,
    chatMessages,
    finalAnswer,
    agentRunning,
    wsConnection,
    loading,
    error,
    agentRunStartedAt,
    livePerf,
    toolSettings,
    toolSettingsLoading,
    skills,
    skillsLoading,
    selectedProject,
    selectedSession,
    pendingPlans,
    pendingCommandApproval,
    pendingLoopApproval,
    fetchProjects,
    doCreateProject,
    selectProject,
    fetchSessions,
    doRenameSession,
    doTogglePinSession,
    doDeleteSession,
    doClearSession,
    doCreateSession,
    startNewSession,
    selectSession,
    restoreSessionState,
    fetchFileTree,
    fetchPlans,
    fetchRounds,
    loadOlderRounds,
    connectWebSocket,
    disconnectWebSocket,
    doSendChat,
    doPlanAction,
    doCommandApproval,
    doContinueApproval,
    doStopSession,
    doDeleteProject,
    selectedFile,
    fileContent,
    fileLoading,
    fetchFileContent,
    fetchToolSettings,
    setToolEnabled,
    fetchSkills,
    doCreateSkill,
    doUpdateSkill,
    doDeleteSkill,
    addAssistantMessage,
    clearError,
    completedRounds,
    currentRoundUserMsg,
    prevRoundPlanIds,
    roundsHasMore,
    roundsLoadingOlder,
    // 跨对话记忆
    sessionSummary,
    projectMemory,
    userPreferences,
    relevantHistory,
    contextBudget,
    memoryLoading,
    fetchMemoryContext,
  }
})
