const KEYS = {
  PROJECT_ID: 'agent_selected_project_id',
  SESSION_ID: 'agent_selected_session_id'
}

export function persistProjectId(id) {
  localStorage.setItem(KEYS.PROJECT_ID, id)
}

export function getPersistedProjectId() {
  return localStorage.getItem(KEYS.PROJECT_ID) || null
}

export function persistSessionId(id) {
  localStorage.setItem(KEYS.SESSION_ID, id)
}

export function getPersistedSessionId() {
  return localStorage.getItem(KEYS.SESSION_ID) || null
}

export function clearPersistence() {
  localStorage.removeItem(KEYS.PROJECT_ID)
  localStorage.removeItem(KEYS.SESSION_ID)
}
