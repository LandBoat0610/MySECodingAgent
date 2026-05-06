<template>
  <div class="app-container">
    <aside class="left-sidebar">
      <ProjectPanel />
      <FileTreePanel @select-file="handleSelectFile" />
      <footer class="sidebar-footer">
        <LiveEvalHud />
      </footer>
    </aside>
    <main class="center-preview">
      <FilePreview ref="filePreviewRef" />
    </main>
    <aside class="right-panel">
      <ChatPanel />
    </aside>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useAgentStore } from '../stores/agent.js'
import { useAgentConfigStore } from '../stores/agentConfig.js'
import ProjectPanel from '../components/ProjectPanel.vue'
import FileTreePanel from '../components/FileTreePanel.vue'
import FilePreview from '../components/FilePreview.vue'
import ChatPanel from '../components/ChatPanel.vue'
import LiveEvalHud from '../components/LiveEvalHud.vue'

const store = useAgentStore()
const agentConfigStore = useAgentConfigStore()
const filePreviewRef = ref(null)

function handleSelectFile(node) {
  if (filePreviewRef.value) {
    filePreviewRef.value.setSelectedFile(node)
  }
}

onMounted(async () => {
  await Promise.all([store.fetchProjects(), agentConfigStore.load()])
  if (store.selectedProjectId) {
    await store.fetchSessions()
    await store.fetchFileTree()
    if (store.selectedSessionId) {
      await store.restoreSessionState()
    }
  }
})
</script>

<style scoped>
.sidebar-footer {
  flex-shrink: 0;
  padding: 10px 12px;
  border-top: 1px solid var(--border-color);
  background: var(--bg-tertiary);
  display: flex;
  flex-direction: column;
  gap: 10px;
}
</style>
