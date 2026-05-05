<template>
  <div class="filetree-panel">
    <div class="panel-header">
      <span class="panel-title">Files</span>
      <button class="btn-icon" @click="store.fetchFileTree()" title="Refresh">↻</button>
    </div>
    <div class="filetree-body">
      <div v-if="!store.selectedProjectId" class="empty-hint">
        Select a project to view files.
      </div>
      <div v-else-if="store.fileTree.length === 0" class="empty-hint">
        No files in workspace.
      </div>
      <FileTreeNode
        v-for="node in store.fileTree"
        :key="node.path"
        :node="node"
        :depth="0"
        @select="handleSelectFile"
      />
    </div>
  </div>
</template>

<script setup>
import { useAgentStore } from '../stores/agent.js'
import FileTreeNode from './FileTreeNode.vue'

const store = useAgentStore()
const emit = defineEmits(['select-file'])

function handleSelectFile(node) {
  emit('select-file', node)
}
</script>

<style scoped>
.filetree-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
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

.filetree-body {
  overflow-y: auto;
  flex: 1;
  padding: 4px 0;
}

.empty-hint {
  padding: 14px;
  text-align: center;
  color: var(--text-muted);
  font-size: 12px;
}
</style>
