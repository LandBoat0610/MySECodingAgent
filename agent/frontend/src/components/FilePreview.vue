<template>
  <div class="file-preview">
    <div class="preview-header">
      <span class="preview-title">{{ selectedFile ? selectedFile.path : 'File Preview' }}</span>
      <span v-if="selectedFile" class="preview-badge">{{ selectedFile.type }}</span>
    </div>
    <div class="preview-body">
      <div v-if="!selectedFile" class="preview-placeholder">
        <span class="placeholder-icon">📄</span>
        <span class="placeholder-text">Select a file from the file tree to preview</span>
        <span class="placeholder-todo">// TODO: File content preview API not yet available</span>
      </div>
      <div v-else class="preview-placeholder">
        <span class="placeholder-icon">📄</span>
        <span class="placeholder-text">{{ selectedFile.path }}</span>
        <span class="placeholder-todo">// TODO: File content preview API not yet available</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const selectedFile = ref(null)

function setSelectedFile(file) {
  selectedFile.value = file
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
  align-items: center;
  justify-content: center;
}

.preview-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
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

.placeholder-todo {
  font-size: 12px;
  padding: 6px 12px;
  background: var(--bg-tertiary);
  border-radius: 6px;
  border: 1px dashed var(--border-color);
  color: var(--warning);
}
</style>
