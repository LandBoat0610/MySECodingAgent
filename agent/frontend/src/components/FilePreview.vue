<template>
  <div class="file-preview">
    <div class="preview-header">
      <span class="preview-title">{{ store.selectedFile ? store.selectedFile.path : 'File Preview' }}</span>
      <span v-if="store.selectedFile" class="preview-badge">{{ store.selectedFile.type }}</span>
    </div>
    <div class="preview-body">
      <div v-if="!store.selectedFile" class="preview-placeholder">
        <span class="placeholder-icon">📄</span>
        <span class="placeholder-text">Select a file from the file tree to preview</span>
      </div>
      <div v-else-if="store.fileLoading" class="preview-placeholder">
        <span class="placeholder-text">Loading...</span>
      </div>
      <div v-else-if="store.error && !store.fileContent" class="preview-placeholder">
        <span class="placeholder-icon">⚠</span>
        <span class="placeholder-text">{{ store.error }}</span>
      </div>
      <div v-else class="preview-code-panel">
        <div class="preview-line-numbers" aria-hidden="true">
          <span v-for="n in lineNumbers" :key="n">{{ n }}</span>
        </div>
        <pre class="preview-code"><code v-html="highlightedContent"></code></pre>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useAgentStore } from '../stores/agent.js'
import { highlightCode, inferLangFromPath } from '../utils/highlight.js'

const store = useAgentStore()

const lineNumbers = computed(() => {
  const count = (store.fileContent || '').split('\n').length
  return Array.from({ length: count }, (_, i) => i + 1)
})

const fileLang = computed(() => {
  const path = store.selectedFile?.path || ''
  return inferLangFromPath(path)
})

const highlightedContent = computed(() => {
  return highlightCode(store.fileContent || '', fileLang.value)
})

async function setSelectedFile(node) {
  await store.fetchFileContent(node.path)
}

defineExpose({ setSelectedFile })
</script>

<style scoped>
.file-preview {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  background: var(--bg-tertiary);
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}

.preview-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
}

.preview-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  background: var(--bg-surface);
  color: var(--text-muted);
  text-transform: uppercase;
}

.preview-body {
  flex: 1;
  overflow: auto;
  display: flex;
  align-items: flex-start;
  justify-content: flex-start;
  padding: 14px;
  background: #0f111a;
}

.preview-placeholder {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 12px;
  color: var(--text-muted);
}

.placeholder-icon {
  font-size: 48px;
  opacity: 0.5;
}

.placeholder-text {
  font-size: 14px;
}

.preview-code-panel {
  display: flex;
  width: 100%;
  align-items: flex-start;
  background: #111827;
  border: 1px solid rgba(148, 163, 184, 0.16);
  border-radius: 8px;
  overflow: hidden;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.02);
}

.preview-line-numbers {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  padding: 12px 10px;
  background: #0b1020;
  color: #64748b;
  user-select: none;
  font-family: 'Consolas', 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
  min-width: 52px;
  border-right: 1px solid rgba(148, 163, 184, 0.14);
}

.preview-line-numbers span {
  display: block;
  min-height: 1.6em;
}

.preview-code {
  margin: 0;
  flex: 1;
  padding: 12px 16px 72px;
  text-align: left;
  white-space: pre;
  overflow: auto;
  font-family: 'Consolas', 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
  color: #e5e7eb;
  scrollbar-width: thin;
  scrollbar-color: rgba(148, 163, 184, 0.45) transparent;
}

.preview-code::-webkit-scrollbar,
.preview-body::-webkit-scrollbar {
  width: 10px;
  height: 10px;
}

.preview-code::-webkit-scrollbar-thumb,
.preview-body::-webkit-scrollbar-thumb {
  background: rgba(148, 163, 184, 0.4);
  border-radius: 999px;
  border: 2px solid transparent;
  background-clip: content-box;
}

.preview-code::-webkit-scrollbar-track,
.preview-body::-webkit-scrollbar-track {
  background: transparent;
}
</style>
