<template>
  <div class="project-panel">
    <div class="panel-header">
      <span class="panel-title">Projects</span>
      <button class="btn-icon" @click="showNewProject = !showNewProject" title="New Project">+</button>
    </div>

    <div v-if="showNewProject" class="new-project-form">
      <input
        v-model="newProjectName"
        placeholder="Project name..."
        @keyup.enter="handleCreateProject"
      />
      <div class="form-actions">
        <button class="btn btn-sm btn-primary" @click="handleCreateProject" :disabled="!newProjectName.trim()">Create</button>
        <button class="btn btn-sm btn-ghost" @click="showNewProject = false">Cancel</button>
      </div>
    </div>

    <div class="project-list">
      <div
        v-for="project in store.projects"
        :key="project.id"
        :class="['project-item', { active: store.selectedProjectId === project.id }]"
      >
        <span class="project-select" @click="store.selectProject(project.id)">
          <span class="project-icon">📁</span>
          <span class="project-name">{{ project.name }}</span>
        </span>
        <button class="btn-delete" @click.stop="handleDeleteProject(project)" title="Delete">×</button>
      </div>
      <div v-if="store.projects.length === 0 && !store.loading" class="empty-hint">
        No projects. Create one above.
      </div>
    </div>

    <div v-if="store.selectedProjectId" class="session-section">
      <div class="panel-header">
        <span class="panel-title">Sessions</span>
        <button class="btn-icon" @click="showNewSession = !showNewSession" title="New Session">+</button>
      </div>

      <div v-if="showNewSession" class="new-session-form">
        <input
          v-model="newSessionTitle"
          placeholder="Session title..."
          @keyup.enter="handleCreateSession"
        />
        <div class="form-actions">
          <button class="btn btn-sm btn-primary" @click="handleCreateSession" :disabled="!newSessionTitle.trim()">Create</button>
          <button class="btn btn-sm btn-ghost" @click="showNewSession = false">Cancel</button>
        </div>
      </div>

      <div class="session-list">
        <div
          v-for="session in store.sessions"
          :key="session.id"
          :class="['session-item', { active: store.selectedSessionId === session.id }]"
          @click="store.selectSession(session.id)"
        >
          <span :class="['status-dot', session.status]"></span>
          <div class="session-info">
            <span class="session-title">{{ session.title }}</span>
            <span class="session-meta">{{ session.status }} · {{ formatDate(session.created_at) }}</span>
          </div>
        </div>
        <div v-if="store.sessions.length === 0" class="empty-hint">
          No sessions. Create one above.
        </div>
      </div>
    </div>

    <div v-if="store.error" class="error-banner">
      {{ store.error }}
      <button class="btn-icon" @click="store.clearError()">×</button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useAgentStore } from '../stores/agent.js'

const store = useAgentStore()

const showNewProject = ref(false)
const newProjectName = ref('')
const showNewSession = ref(false)
const newSessionTitle = ref('')

async function handleCreateProject() {
  if (!newProjectName.value.trim()) return
  try {
    await store.doCreateProject({ name: newProjectName.value.trim() })
    newProjectName.value = ''
    showNewProject.value = false
  } catch (e) {
    // error handled in store
  }
}

async function handleCreateSession() {
  if (!newSessionTitle.value.trim()) return
  try {
    await store.doCreateSession(newSessionTitle.value.trim())
    newSessionTitle.value = ''
    showNewSession.value = false
  } catch (e) {
    // error handled in store
  }
}

async function handleDeleteProject(project) {
  if (!confirm(`确定删除项目 "${project.name}"？此操作将删除该项目下的所有会话和数据，且不可恢复。`)) return
  try {
    await store.doDeleteProject(project.id)
  } catch (e) {
    // error handled in store
  }
}

function formatDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleString()
}
</script>

<style scoped>
.project-panel {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-bottom: 1px solid var(--border-color);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: var(--bg-tertiary);
  flex-shrink: 0;
}

.panel-title {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-secondary);
}

.btn-icon {
  width: 24px;
  height: 24px;
  border-radius: 4px;
  background: transparent;
  color: var(--text-secondary);
  font-size: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.btn-icon:hover {
  background: var(--bg-surface);
  color: var(--text-primary);
}

.new-project-form, .new-session-form {
  padding: 10px 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  border-bottom: 1px solid var(--border-color);
}

.form-actions {
  display: flex;
  gap: 8px;
}

.btn {
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
}

.btn-sm {
  padding: 4px 10px;
  font-size: 12px;
}

.btn-primary {
  background: var(--accent);
  color: #1e1e2e;
}

.btn-primary:hover {
  background: var(--accent-hover);
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-ghost {
  background: var(--bg-surface);
  color: var(--text-secondary);
}

.btn-ghost:hover {
  color: var(--text-primary);
}

.project-list {
  overflow-y: auto;
  flex-shrink: 0;
  max-height: 200px;
}

.project-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 14px;
  border-left: 3px solid transparent;
  transition: background 0.15s;
}

.project-item:hover {
  background: var(--bg-surface);
}

.project-item.active {
  background: var(--bg-surface);
  border-left-color: var(--accent);
}

.project-select {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  flex: 1;
  overflow: hidden;
}

.btn-delete {
  opacity: 0;
  width: 20px;
  height: 20px;
  border-radius: 4px;
  background: transparent;
  color: var(--text-muted);
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.15s;
}

.project-item:hover .btn-delete {
  opacity: 1;
}

.btn-delete:hover {
  background: var(--danger);
  color: var(--bg-primary);
}

.project-icon {
  font-size: 14px;
}

.project-name {
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-section {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  flex: 1;
}

.session-list {
  overflow-y: auto;
  flex: 1;
}

.session-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  cursor: pointer;
  border-left: 3px solid transparent;
  transition: background 0.15s;
}

.session-item:hover {
  background: var(--bg-surface);
}

.session-item.active {
  background: var(--bg-surface);
  border-left-color: var(--accent);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  background: var(--text-muted);
}

.status-dot.idle { background: var(--text-muted); }
.status-dot.running { background: var(--warning); }
.status-dot.awaiting_approval { background: var(--info); }
.status-dot.completed { background: var(--success); }
.status-dot.stopped { background: var(--danger); }
.status-dot.approved { background: var(--accent); }

.session-info {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.session-title {
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-meta {
  font-size: 11px;
  color: var(--text-muted);
}

.empty-hint {
  padding: 14px;
  text-align: center;
  color: var(--text-muted);
  font-size: 12px;
}

.error-banner {
  padding: 8px 14px;
  background: var(--danger);
  color: #1e1e2e;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.error-banner .btn-icon {
  color: #1e1e2e;
}
</style>
