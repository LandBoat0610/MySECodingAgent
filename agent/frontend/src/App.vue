<template>
  <router-view />
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useAgentStore } from './stores/agent.js'
import ProjectPanel from './components/ProjectPanel.vue'
import FileTreePanel from './components/FileTreePanel.vue'
import FilePreview from './components/FilePreview.vue'
import ChatPanel from './components/ChatPanel.vue'

const store = useAgentStore()
const filePreviewRef = ref(null)

function handleSelectFile(node) {
  if (node.type === 'file') {
    store.fetchFileContent(node.path)
  }
}

onMounted(async () => {
  await store.fetchProjects()
  if (store.selectedProjectId) {
    await store.fetchSessions()
    await store.fetchFileTree()
    if (store.selectedSessionId) {
      await store.restoreSessionState()
    }
  }
})
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

:root {
  --bg-primary: #1e1e2e;
  --bg-secondary: #181825;
  --bg-tertiary: #11111b;
  --bg-surface: #313244;
  --text-primary: #cdd6f4;
  --text-secondary: #a6adc8;
  --text-muted: #6c7086;
  --border-color: #45475a;
  --accent: #89b4fa;
  --accent-hover: #74c7ec;
  --success: #a6e3a1;
  --warning: #f9e2af;
  --danger: #f38ba8;
  --info: #89dceb;
  --scrollbar-bg: #1e1e2e;
  --scrollbar-thumb: #45475a;
}

html, body {
  height: 100%;
  overflow: hidden;
  font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
  font-size: 14px;
  color: var(--text-primary);
  background: var(--bg-primary);
}

#app {
  height: 100%;
}

.app-container {
  display: flex;
  height: 100%;
  overflow: hidden;
}

.left-sidebar {
  width: 280px;
  min-width: 280px;
  background: var(--bg-secondary);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.center-preview {
  flex: 1;
  background: var(--bg-primary);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.right-panel {
  width: 420px;
  min-width: 420px;
  background: var(--bg-secondary);
  border-left: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

::-webkit-scrollbar-track {
  background: var(--scrollbar-bg);
}

::-webkit-scrollbar-thumb {
  background: var(--scrollbar-thumb);
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: var(--text-muted);
}

input, textarea, select, button {
  font-family: inherit;
  font-size: inherit;
}

button {
  cursor: pointer;
  border: none;
  outline: none;
}

input, textarea {
  outline: none;
  border: 1px solid var(--border-color);
  background: var(--bg-tertiary);
  color: var(--text-primary);
  padding: 8px 12px;
  border-radius: 6px;
}

input:focus, textarea:focus {
  border-color: var(--accent);
}
</style>
