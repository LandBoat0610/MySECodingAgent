import axios from 'axios'
import type {
  Project,
  Session,
  Plan,
  FileTreeNode,
  ChatRequest,
  ChatResponse,
  PlanActionRequest,
  PlanActionResponse,
  AgentState,
} from '@/types'

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
})

// 项目 API
export const projectApi = {
  getProjects(): Promise<Project[]> {
    return api.get('/projects').then(res => res.data)
  },

  createProject(data: { name: string; description?: string; workspace_path?: string | null }): Promise<Project> {
    return api.post('/projects', data).then(res => res.data)
  },
}

// 会话 API
export const sessionApi = {
  getSessions(projectId: string): Promise<Session[]> {
    return api.get(`/projects/${projectId}/sessions`).then(res => res.data)
  },

  createSession(projectId: string, data: { title?: string }): Promise<Session> {
    return api.post(`/projects/${projectId}/sessions`, data).then(res => res.data)
  },

  getSessionState(projectId: string, sessionId: string): Promise<{ session_id: string; project_id: string; status: string; snapshot: AgentState }> {
    return api.get(`/projects/${projectId}/sessions/${sessionId}/state`).then(res => res.data)
  },
}

// 对话 API
export const chatApi = {
  sendMessage(projectId: string, sessionId: string, data: ChatRequest): Promise<ChatResponse> {
    return api.post(`/projects/${projectId}/sessions/${sessionId}/chat`, data).then(res => res.data)
  },
}

// 计划 API
export const planApi = {
  getPlans(projectId: string, sessionId: string): Promise<Plan[]> {
    return api.get(`/projects/${projectId}/sessions/${sessionId}/plan`).then(res => res.data)
  },

  submitAction(projectId: string, sessionId: string, planId: string, data: PlanActionRequest): Promise<PlanActionResponse> {
    return api.post(`/projects/${projectId}/sessions/${sessionId}/plan/${planId}/action`, data).then(res => res.data)
  },
}

// 文件 API
export const fileApi = {
  getFileTree(projectId: string): Promise<FileTreeNode[]> {
    return api.get(`/projects/${projectId}/files`).then(res => res.data)
  },
}

// WebSocket 连接 - 直接连接后端服务
export function createWebSocketConnection(projectId: string, sessionId: string): WebSocket {
  // 开发环境直接连接后端，生产环境使用相对路径
  const isDev = import.meta.env.DEV
  if (isDev) {
    const wsUrl = `ws://127.0.0.1:8000/projects/${projectId}/sessions/${sessionId}/chat/stream`
    return new WebSocket(wsUrl)
  }
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsUrl = `${protocol}//${window.location.host}/api/projects/${projectId}/sessions/${sessionId}/chat/stream`
  return new WebSocket(wsUrl)
}

export default api