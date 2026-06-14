<template>
  <div class="filetree-panel">
    <div class="panel-header">
      <button class="panel-title-button" @click="collapsed = !collapsed" :title="collapsed ? 'Expand Files' : 'Collapse Files'">
        <span class="panel-chevron">{{ collapsed ? '▸' : '▾' }}</span>
        <span class="panel-title">Files</span>
      </button>
      <button class="btn-icon" @click="store.fetchFileTree()" title="Refresh">↻</button>
    </div>
    <div v-if="!collapsed" class="filetree-body">
      <EmptyState
        v-if="!store.selectedProjectId"
        icon="📁"
        title="Select a project to view files"
      />
      <EmptyState
        v-else-if="store.fileTree.length === 0"
        icon="📂"
        title="No files in workspace"
      />
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
import { ref } from 'vue'
import { useAgentStore } from '../stores/agent.js'
import FileTreeNode from './FileTreeNode.vue'
import { EmptyState } from './status/index.js'

const store = useAgentStore()
const emit = defineEmits(['select-file'])
const collapsed = ref(false)

function handleSelectFile(node) {
  emit('select-file', node)
}
</script>

<style scoped>
.filetree-panel {
  flex: 0 0 auto;
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
  max-height: 260px;
  padding: 4px 0;
}

.empty-hint {
  padding: 14px;
  text-align: center;
  color: var(--text-muted);
  font-size: 13px;
}
</style>
