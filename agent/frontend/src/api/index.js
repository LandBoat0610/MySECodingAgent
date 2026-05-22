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

export function updateSession(projectId, sessionId, data) {
  return api.patch(`/projects/${projectId}/sessions/${sessionId}`, data).then(r => r.data)
}

export function deleteSession(projectId, sessionId) {
  return api.delete(`/projects/${projectId}/sessions/${sessionId}`).then(r => r.data)
}

export function clearSession(projectId, sessionId) {
  return api.post(`/projects/${projectId}/sessions/${sessionId}/clear`).then(r => r.data)
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

export function getRounds(projectId, sessionId, options = {}) {
  const params = {}
  if (options.limit) params.limit = options.limit
  if (options.before) params.before = options.before
  return api.get(`/projects/${projectId}/sessions/${sessionId}/rounds`, { params }).then(r => r.data)
}

export function planAction(projectId, sessionId, planId, action, feedback = '') {
  const body = { action }
  if (feedback) body.feedback = feedback
  return api.post(`/projects/${projectId}/sessions/${sessionId}/plan/${planId}/action`, body).then(r => r.data)
}

export function commandApproval(projectId, sessionId, approvalId, action, feedback = '') {
  const body = {
    approval_id: approvalId,
    action
  }
  if (feedback) body.feedback = feedback
  return api.post(`/projects/${projectId}/sessions/${sessionId}/command-approval`, body).then(r => r.data)
}

export function continueApproval(projectId, sessionId, approvalId, action) {
  return api.post(`/projects/${projectId}/sessions/${sessionId}/continue-approval`, {
    approval_id: approvalId,
    action
  }).then(r => r.data)
}

export function deleteProject(projectId) {
  return api.delete(`/projects/${projectId}`).then(r => r.data)
}

export function getFileTree(projectId) {
  return api.get(`/projects/${projectId}/files`).then(r => r.data)
}

export function getFileContent(projectId, path) {
  return api.get(`/projects/${projectId}/files/content`, { params: { path } }).then(r => r.data)
}

export function stopSession(projectId, sessionId) {
  return api.post(`/projects/${projectId}/sessions/${sessionId}/stop`).then(r => r.data)
}

export function createWebSocket(projectId, sessionId) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  return new WebSocket(`${protocol}//${host}/projects/${projectId}/sessions/${sessionId}/chat/stream`)
}

export function getAgentConfig() {
  return api.get('/settings/agent-config').then(r => r.data)
}

export function updateAgentConfig(body) {
  return api.put('/settings/agent-config', body).then(r => r.data)
}

export function getToolSettings() {
  return api.get('/settings/tools').then(r => r.data)
}

export function updateToolSettings(body) {
  return api.put('/settings/tools', body).then(r => r.data)
}

export function getSkills() {
  return api.get('/settings/skills').then(r => r.data)
}

export function createSkill(body) {
  return api.post('/settings/skills', body).then(r => r.data)
}

export function updateSkill(skillId, body) {
  return api.patch(`/settings/skills/${skillId}`, body).then(r => r.data)
}

export function deleteSkill(skillId) {
  return api.delete(`/settings/skills/${skillId}`).then(r => r.data)
}

export function uploadEvalDataset(file, name) {
  const fd = new FormData()
  fd.append('file', file)
  if (name) fd.append('name', name)
  return api.post('/eval/datasets/upload', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000
  }).then(r => r.data)
}

export function createEvalDatasetJson(body) {
  return api.post('/eval/datasets', body, { timeout: 120000 }).then(r => r.data)
}

export function listEvalDatasets() {
  return api.get('/eval/datasets').then(r => r.data)
}

export function deleteEvalDataset(id, opts = {}) {
  const params = {}
  if (opts.cascade) params.cascade = true
  return api.delete(`/eval/datasets/${id}`, { params }).then(r => r.data)
}

export function createEvalTask(body) {
  return api.post('/eval/tasks', body).then(r => r.data)
}

export function listEvalTasks() {
  return api.get('/eval/tasks').then(r => r.data)
}

export function getEvalTask(id) {
  return api.get(`/eval/tasks/${id}`).then(r => r.data)
}

export function patchEvalTask(id, body) {
  return api.patch(`/eval/tasks/${id}`, body).then(r => r.data)
}

export function deleteEvalTask(id) {
  return api.delete(`/eval/tasks/${id}`).then(r => r.data)
}

export function startEvalTask(id) {
  return api.post(`/eval/tasks/${id}/start`).then(r => r.data)
}

export function cancelEvalTask(id) {
  return api.post(`/eval/tasks/${id}/cancel`).then(r => r.data)
}

export function getEvalTaskResults(id) {
  return api.get(`/eval/tasks/${id}/results`).then(r => r.data)
}

export function getEvalTaskAnalytics(taskId) {
  return api.get(`/eval/tasks/${taskId}/analytics`).then(r => r.data)
}

export function getEvalCompareAnalytics(leftTaskId, rightTaskId) {
  return api.get('/eval/analytics/compare', {
    params: { left: leftTaskId, right: rightTaskId }
  }).then(r => r.data)
}
