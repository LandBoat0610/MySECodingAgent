import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Project, Session, Plan, AgentState } from '@/types'

export const useAgentStore = defineStore('agent', () => {
  // State
  const projects = ref<Project[]>([])
  const currentProject = ref<Project | null>(null)
  const sessions = ref<Session[]>([])
  const currentSession = ref<Session | null>(null)
  const plans = ref<Plan[]>([])
  const agentState = ref<AgentState | null>(null)
  const isConnected = ref(false)
  const messages = ref<Array<{type: string, content: string, timestamp: number}>>([])

  // Getters
  const hasProjects = computed(() => projects.value.length > 0)
  const hasSessions = computed(() => sessions.value.length > 0)
  const isRunning = computed(() => agentState.value?.status === 'running')
  const isAwaitingApproval = computed(() => agentState.value?.status === 'awaiting_approval')

  // Actions
  function setProjects(data: Project[]) {
    projects.value = data
  }

  function setCurrentProject(project: Project | null) {
    currentProject.value = project
  }

  function setSessions(data: Session[]) {
    sessions.value = data
  }

  function setCurrentSession(session: Session | null) {
    currentSession.value = session
  }

  function setPlans(data: Plan[]) {
    plans.value = data
  }

  function setAgentState(state: AgentState | null) {
    agentState.value = state
  }

  function addMessage(type: string, content: string) {
    messages.value.push({
      type,
      content,
      timestamp: Date.now(),
    })
  }

  function clearMessages() {
    messages.value = []
  }

  function setConnected(status: boolean) {
    isConnected.value = status
  }

  return {
    projects,
    currentProject,
    sessions,
    currentSession,
    plans,
    agentState,
    isConnected,
    messages,
    hasProjects,
    hasSessions,
    isRunning,
    isAwaitingApproval,
    setProjects,
    setCurrentProject,
    setSessions,
    setCurrentSession,
    setPlans,
    setAgentState,
    addMessage,
    clearMessages,
    setConnected,
  }
})