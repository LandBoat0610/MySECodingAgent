import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  getProjects,
  createProject,
  deleteProject,
  getSessions,
  createSession,
  getSessionState,
  sendChat,
  getPlans,
  planAction,
  getFileTree,
  getFileContent,
  stopSession,
  createWebSocket
} from '../api/index.js'
import { persistProjectId, getPersistedProjectId, persistSessionId, getPersistedSessionId } from '../utils/persistence.js'

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

  const selectedProject = computed(() => projects.value.find(p => p.id === selectedProjectId.value) || null)
  const selectedSession = computed(() => sessions.value.find(s => s.id === selectedSessionId.value) || null)
  const pendingPlans = computed(() => plans.value.filter(p => p.status === 'pending'))

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
    sessionStatus.value = 'idle'
    stateSnapshot.value = null
    selectedFile.value = null
    fileContent.value = ''
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
    await restoreSessionState()
  }

  async function restoreSessionState() {
    if (!selectedProjectId.value || !selectedSessionId.value) return
    try {
      const stateResp = await getSessionState(selectedProjectId.value, selectedSessionId.value)
      sessionStatus.value = stateResp.status
      stateSnapshot.value = stateResp.snapshot

      const msgs = stateResp.snapshot?.messages || []
      chatMessages.value = msgs.map(m => ({
        role: m.role,
        content: m.content,
        tool_calls: m.tool_calls || null
      }))

      await fetchPlans()

      if (['running', 'awaiting_approval', 'approved', 'needs_fix', 'next_step'].includes(stateResp.status)) {
        connectWebSocket()
      }

      if (stateResp.snapshot?.final_answer) {
        finalAnswer.value = stateResp.snapshot.final_answer
      }
      if (stateResp.snapshot?.trace) {
        traceLogs.value = stateResp.snapshot.trace || []
      }
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
          return
        }

        if (data.type === 'trace' && data.data) {
          traceLogs.value.push(data.data)
          if (data.data.session_status) {
            sessionStatus.value = data.data.session_status
            if (data.data.session_status === 'awaiting_approval') {
              fetchPlans()
            }
          }
        }

        if (data.phase === 'start') {
          agentRunning.value = true
          traceLogs.value = []
        }

        if (data.phase === 'done') {
          wsIntentionalClose.value = true
          agentRunning.value = false
          finalAnswer.value = data.final_answer || ''
          sessionStatus.value = data.status || 'completed'
          fetchPlans()
          restoreSessionState()
        }

        if (data.phase === 'cancelled') {
          wsIntentionalClose.value = true
          agentRunning.value = false
          sessionStatus.value = 'stopped'
          fetchPlans()
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
        return
      }
      const activeStates = ['running', 'awaiting_approval', 'approved', 'needs_fix', 'next_step']
      if (activeStates.includes(sessionStatus.value)) {
        wsReconnectAttempts.value++
        if (wsReconnectAttempts.value <= WS_MAX_RECONNECT) {
          setTimeout(() => {
            connectWebSocket()
          }, 2000 * wsReconnectAttempts.value)
        } else {
          agentRunning.value = false
          setError('WebSocket 连接断开，已达到最大重连次数，请手动刷新页面')
        }
      } else {
        agentRunning.value = false
      }
    }

    ws.onerror = (err) => {
      console.error('WebSocket error:', err)
      agentRunning.value = false
    }
  }

  function disconnectWebSocket() {
    wsIntentionalClose.value = true
    if (wsConnection.value) {
      try { wsConnection.value.close() } catch (e) { /* ignore */ }
      wsConnection.value = null
    }
    agentRunning.value = false
  }

  async function doSendChat(message) {
    clearError()
    chatMessages.value.push({ role: 'user', content: message })
    try {
      const resp = await sendChat(selectedProjectId.value, selectedSessionId.value, message)
      sessionStatus.value = resp.status
      connectWebSocket()
      return resp
    } catch (e) {
      chatMessages.value.pop()
      setError(e)
      throw e
    }
  }

  async function doPlanAction(planId, action) {
    clearError()
    try {
      const resp = await planAction(selectedProjectId.value, selectedSessionId.value, planId, action)
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

  return {
    projects,
    selectedProjectId,
    sessions,
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
    selectedProject,
    selectedSession,
    pendingPlans,
    fetchProjects,
    doCreateProject,
    selectProject,
    fetchSessions,
    doCreateSession,
    selectSession,
    restoreSessionState,
    fetchFileTree,
    fetchPlans,
    connectWebSocket,
    disconnectWebSocket,
    doSendChat,
    doPlanAction,
    doStopSession,
    doDeleteProject,
    selectedFile,
    fileContent,
    fileLoading,
    fetchFileContent,
    addAssistantMessage,
    clearError
  }
})
