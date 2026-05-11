const KEYS = {
  PROJECT_ID: 'agent_selected_project_id',
  SESSION_ID: 'agent_selected_session_id'
}

export function persistProjectId(id) {
  if (id) {
    localStorage.setItem(KEYS.PROJECT_ID, id)
  } else {
    localStorage.removeItem(KEYS.PROJECT_ID)
  }
}

export function getPersistedProjectId() {
  const val = localStorage.getItem(KEYS.PROJECT_ID)
  return val || null
}

export function persistSessionId(id) {
  if (id) {
    localStorage.setItem(KEYS.SESSION_ID, id)
  } else {
    localStorage.removeItem(KEYS.SESSION_ID)
  }
}

export function getPersistedSessionId() {
  const val = localStorage.getItem(KEYS.SESSION_ID)
  return val || null
}

export function clearPersistence() {
  localStorage.removeItem(KEYS.PROJECT_ID)
  localStorage.removeItem(KEYS.SESSION_ID)
}
