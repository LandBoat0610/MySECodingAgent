import axios from 'axios'

const api = axios.create({
  baseURL: '/',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' }
})

export function getProjects() {
  return api.get('/projects').then(r => r.data)
}

export function createProject(data) {
  return api.post('/projects', data).then(r => r.data)
}

export function getSessions(projectId) {
  return api.get(`/projects/${projectId}/sessions`).then(r => r.data)
}

export function createSession(projectId, data) {
  return api.post(`/projects/${projectId}/sessions`, data).then(r => r.data)
}

export function getSessionState(projectId, sessionId) {
  return api.get(`/projects/${projectId}/sessions/${sessionId}/state`).then(r => r.data)
}

export function sendChat(projectId, sessionId, message) {
  return api.post(`/projects/${projectId}/sessions/${sessionId}/chat`, { message }).then(r => r.data)
}

export function getPlans(projectId, sessionId) {
  return api.get(`/projects/${projectId}/sessions/${sessionId}/plan`).then(r => r.data)
}

export function planAction(projectId, sessionId, planId, action) {
  return api.post(`/projects/${projectId}/sessions/${sessionId}/plan/${planId}/action`, { action }).then(r => r.data)
}

export function getFileTree(projectId) {
  return api.get(`/projects/${projectId}/files`).then(r => r.data)
}

export function createWebSocket(projectId, sessionId) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  return new WebSocket(`${protocol}//${host}/projects/${projectId}/sessions/${sessionId}/chat/stream`)
}
