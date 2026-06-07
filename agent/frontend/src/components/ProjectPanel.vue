<template>
  <div class="project-panel">
    <div class="panel-header">
      <button class="panel-title-button" @click="projectsCollapsed = !projectsCollapsed" :title="projectsCollapsed ? 'Expand Projects' : 'Collapse Projects'">
        <span class="panel-chevron">{{ projectsCollapsed ? '▸' : '▾' }}</span>
        <span class="panel-title">Projects</span>
      </button>
      <button class="btn-icon" @click="showNewProject = !showNewProject" title="New Project">+</button>
    </div>

    <div v-if="!projectsCollapsed && showNewProject" class="new-project-form">
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

    <div v-if="!projectsCollapsed" class="project-list">
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
      <EmptyState
        v-if="store.projects.length === 0 && !store.loading"
        icon="📁"
        title="No projects"
        desc="Create one above."
      />
    </div>

    <div v-if="store.selectedProjectId" class="session-section">
      <div class="panel-header">
        <button class="panel-title-button" @click="sessionsCollapsed = !sessionsCollapsed" :title="sessionsCollapsed ? 'Expand Sessions' : 'Collapse Sessions'">
          <span class="panel-chevron">{{ sessionsCollapsed ? '▸' : '▾' }}</span>
          <span class="panel-title">Sessions</span>
        </button>
        <div class="header-actions">
          <button class="btn-icon" @click="toggleSessionSearch" title="Search Sessions">⌕</button>
        </div>
      </div>

      <div v-if="!sessionsCollapsed && showSessionSearch" class="session-search">
        <input v-model="store.sessionSearch" placeholder="Search sessions..." />
        <button class="btn-icon" @click="closeSessionSearch" title="Close Search">×</button>
      </div>

      <div v-if="!sessionsCollapsed" class="session-list">
        <div
          v-for="session in store.filteredSessions"
          :key="session.id"
          :class="['session-item', { active: store.selectedSessionId === session.id }]"
          @click="store.selectSession(session.id)"
        >
          <span :class="['status-dot', session.status]"></span>
          <div class="session-info">
            <input
              v-if="editingSessionId === session.id"
              v-model="editingTitle"
              class="session-edit-input"
              @click.stop
              @keyup.enter.stop="saveSessionTitle(session)"
              @keyup.esc.stop="cancelEditSession"
              @blur="saveSessionTitle(session)"
            />
            <span v-else class="session-title">
              <span v-if="session.pinned" class="pin-mark">★</span>{{ session.title }}
            </span>
            <span class="session-meta">{{ session.status }} · {{ formatDate(session.created_at) }}</span>
          </div>
          <div class="session-actions">
            <button class="btn-mini" @click.stop="store.doTogglePinSession(session.id)" :title="session.pinned ? 'Unpin' : 'Pin'">
              {{ session.pinned ? '★' : '☆' }}
            </button>
            <button class="btn-mini" @click.stop="startEditSession(session)" title="Rename">✎</button>
            <button class="btn-mini" @click.stop="handleClearSession(session)" title="Clear">⌫</button>
            <button class="btn-mini danger" @click.stop="handleDeleteSession(session)" title="Delete">×</button>
          </div>
        </div>
        <EmptyState
          v-if="store.sessions.length === 0"
          icon="💬"
          title="No sessions"
          desc="Create one above."
        />
        <EmptyState
          v-else-if="store.filteredSessions.length === 0"
          icon="🔍"
          title="No matching sessions"
        />
      </div>
    </div>

    <div v-if="store.selectedProjectId" class="tool-section">
      <div class="panel-header">
        <button class="panel-title-button" @click="toolsCollapsed = !toolsCollapsed" :title="toolsCollapsed ? 'Expand Tools' : 'Collapse Tools'">
          <span class="panel-chevron">{{ toolsCollapsed ? '▸' : '▾' }}</span>
          <span class="panel-title">Tools</span>
        </button>
        <button class="btn-icon" @click="store.fetchToolSettings()" title="Refresh">↻</button>
      </div>
      <div v-if="!toolsCollapsed" class="tool-list">
        <label v-for="tool in store.toolSettings" :key="tool.name" class="tool-item">
          <span class="tool-name">{{ toolLabel(tool.name) }}</span>
          <input
            type="checkbox"
            :checked="tool.enabled"
            @change="store.setToolEnabled(tool.name, $event.target.checked)"
          />
        </label>
        <div v-if="!store.toolSettings.length && !store.toolSettingsLoading" class="empty-hint">
          No tools loaded.
        </div>
      </div>
    </div>

    <div v-if="store.selectedProjectId" class="skill-section">
      <div class="panel-header">
        <button class="panel-title-button" @click="skillsCollapsed = !skillsCollapsed" :title="skillsCollapsed ? 'Expand Skills' : 'Collapse Skills'">
          <span class="panel-chevron">{{ skillsCollapsed ? '▸' : '▾' }}</span>
          <span class="panel-title">Skills</span>
        </button>
        <button class="btn-icon" @click="startNewSkill" title="Add Skill">+</button>
      </div>
      <div v-if="!skillsCollapsed" class="skill-list">
        <form v-if="editingSkillId === '__new__'" class="skill-form" @submit.prevent="saveSkill">
          <input v-model="skillName" placeholder="Skill name..." />
          <textarea v-model="skillContent" rows="4" placeholder="Skill instructions..."></textarea>
          <div class="form-actions">
            <button class="btn btn-sm btn-primary" :disabled="!skillName.trim() || !skillContent.trim()">Save</button>
            <button type="button" class="btn btn-sm btn-ghost" @click="cancelSkillEdit">Cancel</button>
          </div>
        </form>

        <div v-for="skill in store.skills" :key="skill.id" class="skill-item">
          <form v-if="editingSkillId === skill.id" class="skill-form" @submit.prevent="saveSkill">
            <input v-model="skillName" placeholder="Skill name..." />
            <textarea v-model="skillContent" rows="4" placeholder="Skill instructions..."></textarea>
            <div class="form-actions">
              <button class="btn btn-sm btn-primary" :disabled="!skillName.trim() || !skillContent.trim()">Save</button>
              <button type="button" class="btn btn-sm btn-ghost" @click="cancelSkillEdit">Cancel</button>
            </div>
          </form>
          <template v-else>
            <div class="skill-row">
              <label class="skill-toggle">
                <input
                  type="checkbox"
                  :checked="skill.enabled"
                  @change="store.doUpdateSkill(skill.id, { enabled: $event.target.checked })"
                />
                <span class="skill-name">{{ skill.name }}</span>
              </label>
              <div class="skill-actions">
                <button class="btn-mini" @click="startEditSkill(skill)" title="Edit Skill">✎</button>
                <button class="btn-mini danger" @click="handleDeleteSkill(skill)" title="Delete Skill">×</button>
              </div>
            </div>
            <div class="skill-preview">{{ skill.content }}</div>
          </template>
        </div>
        <div v-if="!store.skills.length && !store.skillsLoading && editingSkillId !== '__new__'" class="empty-hint">
          No skills. Add one above.
        </div>
      </div>
    </div>

    <ErrorBanner
      :message="store.error"
      @dismiss="store.clearError()"
    />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useAgentStore } from '../stores/agent.js'
import { EmptyState, ErrorBanner } from './status/index.js'
import { showConfirm } from '../composables/useConfirm.js'

const store = useAgentStore()

const showNewProject = ref(false)
const newProjectName = ref('')
const editingSessionId = ref(null)
const editingTitle = ref('')
const projectsCollapsed = ref(false)
const sessionsCollapsed = ref(false)
const toolsCollapsed = ref(false)
const skillsCollapsed = ref(false)
const showSessionSearch = ref(false)
const editingSkillId = ref(null)
const skillName = ref('')
const skillContent = ref('')

onMounted(() => {
  store.fetchToolSettings()
  store.fetchSkills()
})

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

async function handleDeleteProject(project) {
  const ok = await showConfirm({
    title: '删除项目',
    message: `确定删除项目「${project.name}」？此操作将删除该项目下的所有会话和数据，且不可恢复。`,
    variant: 'danger'
  })
  if (!ok) return
  try {
    await store.doDeleteProject(project.id)
  } catch (e) {
    // error handled in store
  }
}

function startEditSession(session) {
  editingSessionId.value = session.id
  editingTitle.value = session.title
}

function cancelEditSession() {
  editingSessionId.value = null
  editingTitle.value = ''
}

function toggleSessionSearch() {
  showSessionSearch.value = !showSessionSearch.value
  if (!showSessionSearch.value) {
    store.sessionSearch = ''
  }
}

function closeSessionSearch() {
  showSessionSearch.value = false
  store.sessionSearch = ''
}

async function saveSessionTitle(session) {
  if (editingSessionId.value !== session.id) return
  const title = editingTitle.value.trim()
  if (!title || title === session.title) {
    cancelEditSession()
    return
  }
  try {
    await store.doRenameSession(session.id, title)
  } catch (e) {
    // error handled in store
  } finally {
    cancelEditSession()
  }
}

async function handleClearSession(session) {
  if (!confirm(`确定清空对话 "${session.title}"？`)) return
  try {
    await store.doClearSession(session.id)
  } catch (e) {
    // error handled in store
  }
}

async function handleDeleteSession(session) {
  if (!confirm(`确定删除对话 "${session.title}"？此操作不可恢复。`)) return
  try {
    await store.doDeleteSession(session.id)
  } catch (e) {
    // error handled in store
  }
}

function startNewSkill() {
  editingSkillId.value = '__new__'
  skillName.value = ''
  skillContent.value = ''
  skillsCollapsed.value = false
}

function startEditSkill(skill) {
  editingSkillId.value = skill.id
  skillName.value = skill.name
  skillContent.value = skill.content
}

function cancelSkillEdit() {
  editingSkillId.value = null
  skillName.value = ''
  skillContent.value = ''
}

async function saveSkill() {
  const payload = {
    name: skillName.value.trim(),
    content: skillContent.value.trim(),
  }
  if (!payload.name || !payload.content) return
  try {
    if (editingSkillId.value === '__new__') {
      await store.doCreateSkill({ ...payload, enabled: true })
    } else {
      await store.doUpdateSkill(editingSkillId.value, payload)
    }
    cancelSkillEdit()
  } catch (e) {
    // error handled in store
  }
}

async function handleDeleteSkill(skill) {
  if (!confirm(`确定删除 Skill "${skill.name}"？`)) return
  try {
    await store.doDeleteSkill(skill.id)
  } catch (e) {
    // error handled in store
  }
}

function toolLabel(name) {
  const labels = {
    execute_bash: 'Bash',
    read_file: 'Read File',
    write_file: 'Write File',
    web_search: 'Web Search',
    fetch_url: 'Fetch URL',
  }
  return labels[name] || name
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
  border-bottom: 1px solid var(--border-color);
  flex: 0 0 auto;
  min-height: 0;
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
  font-size: 13px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-secondary);
}

.panel-title-button {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  background: transparent;
  color: var(--text-secondary);
}

.panel-title-button:hover {
  color: var(--text-primary);
}

.panel-chevron {
  width: 10px;
  font-size: 11px;
  color: var(--text-muted);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 2px;
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

.new-project-form, .new-session-form, .session-search {
  padding: 10px 14px;
  display: flex;
  gap: 8px;
  border-bottom: 1px solid var(--border-color);
}

.new-project-form, .new-session-form {
  flex-direction: column;
}

.session-search {
  align-items: center;
}

.session-search input {
  min-width: 0;
  flex: 1;
}

.form-actions {
  display: flex;
  gap: 8px;
}

.btn {
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
}

.btn-sm {
  padding: 4px 10px;
  font-size: 13px;
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
  max-height: 160px;
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
  font-size: 15px;
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
  font-size: 15px;
}

.project-name {
  font-size: 14px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-section {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  flex: 0 0 auto;
  min-height: 0;
}

.session-list {
  overflow-y: auto;
  max-height: 220px;
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

.session-item:hover .session-actions {
  opacity: 1;
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
  flex: 1;
  min-width: 0;
}

.session-title {
  font-size: 14px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pin-mark {
  color: var(--accent);
  margin-right: 4px;
}

.session-edit-input {
  height: 22px;
  font-size: 12px;
  padding: 2px 6px;
}

.session-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  opacity: 0;
  transition: opacity 0.15s;
}

.btn-mini {
  width: 20px;
  height: 20px;
  border-radius: 4px;
  background: transparent;
  color: var(--text-muted);
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.btn-mini:hover {
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

.btn-mini.danger:hover {
  background: var(--danger);
  color: var(--bg-primary);
}

.session-meta {
  font-size: 12px;
  color: var(--text-muted);
}

.empty-hint {
  padding: 14px;
  text-align: center;
  color: var(--text-muted);
  font-size: 13px;
}

.error-banner {
  padding: 8px 14px;
  background: var(--danger);
  color: #1e1e2e;
  font-size: 13px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.error-banner .btn-icon {
  color: #1e1e2e;
}

.tool-section,
.skill-section {
  border-top: 1px solid var(--border-color);
  flex: 0 0 auto;
  min-height: 0;
}

.tool-list,
.skill-list {
  padding: 8px 14px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 220px;
  overflow-y: auto;
}

.tool-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  color: var(--text-secondary);
  font-size: 12px;
}

.tool-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.skill-item {
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 8px;
  background: rgba(49, 50, 68, 0.35);
}

.skill-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.skill-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.skill-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.skill-actions {
  display: flex;
  align-items: center;
  gap: 2px;
}

.skill-preview {
  margin-top: 6px;
  color: var(--text-muted);
  font-size: 11px;
  line-height: 1.4;
  max-height: 48px;
  overflow: hidden;
  white-space: pre-wrap;
}

.skill-form {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.skill-form textarea {
  width: 100%;
  resize: vertical;
  min-height: 72px;
}
</style>
