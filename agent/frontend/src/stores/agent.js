import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  getProjects,
  createProject,
  getSessions,
  createSession,
  getSessionState,
  sendChat,
  getPlans,
  planAction,
  getFileTree,
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
  const wsReconnecting = ref(false)
  const loading = ref(false)
  const error = ref(null)

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
      if (selectedProjectId.value && !projects.value.find(p => p.id === selectedProjectId.value)) {
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
    fetchSessions()
    fetchFileTree()
  }

  async function fetchSessions() {
    if (!selectedProjectId.value) return
    clearError()
    try {
      sessions.value = await getSessions(selectedProjectId.value)
      if (selectedSessionId.value && !sessions.value.find(s => s.id === selectedSessionId.value)) {
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

      if (['running', 'awaiting_approval', 'approved'].includes(stateResp.status)) {
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
      try { wsConnection.value.close() } catch (e) { /* ignore */ }
      wsConnection.value = null
    }

    agentRunning.value = true
    const ws = createWebSocket(selectedProjectId.value, selectedSessionId.value)
    wsConnection.value = ws

    ws.onopen = () => {
      console.log('WebSocket connected')
      wsReconnecting.value = false
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)

        if (data.error) {
          setError(data.error)
          agentRunning.value = false
          return
        }

        if (data.type === 'trace' && data.data) {
          traceLogs.value.push(data.data)
        }

        if (data.phase === 'start') {
          agentRunning.value = true
          traceLogs.value = []
        }

        if (data.phase === 'done') {
          agentRunning.value = false
          finalAnswer.value = data.final_answer || ''
          sessionStatus.value = data.status || 'completed'
          fetchPlans()
          restoreSessionState()
        }

        if (data.phase === 'cancelled') {
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
      agentRunning.value = false
      if (sessionStatus.value === 'running' && !wsReconnecting.value) {
        wsReconnecting.value = true
        setTimeout(() => {
          wsReconnecting.value = false
          restoreSessionState()
        }, 2000)
      }
    }

    ws.onerror = (err) => {
      console.error('WebSocket error:', err)
      agentRunning.value = false
    }
  }

  function disconnectWebSocket() {
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
      return resp
    } catch (e) {
      setError(e)
      throw e
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
    wsReconnecting,
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
    addAssistantMessage,
    clearError
  }
})
