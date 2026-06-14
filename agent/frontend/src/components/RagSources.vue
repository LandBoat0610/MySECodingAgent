<template>
  <div class="rag-sources" v-if="sources.length > 0">
    <div class="rag-header" @click="expanded = !expanded">
      <span class="rag-icon">📚</span>
      <span class="rag-title">知识来源 (RAG)</span>
      <span class="rag-count">{{ sources.length }} 条</span>
      <span class="toggle-btn">{{ expanded ? '▾' : '▸' }}</span>
    </div>
    <div v-if="expanded" class="rag-body">
      <div v-for="(src, idx) in sources" :key="idx" class="rag-item">
        <div class="rag-item-header">
          <span class="rag-item-icon">{{ src.type === 'file' ? '📄' : src.type === 'url' ? '🔗' : '📌' }}</span>
          <span class="rag-item-title">{{ src.title || src.source || '来源 ' + (idx + 1) }}</span>
          <span v-if="src.score != null" class="rag-score">{{ (src.score * 100).toFixed(0) }}%</span>
        </div>
        <div v-if="src.snippet || src.content" class="rag-item-content">
          {{ (src.snippet || src.content || '').slice(0, 300) }}
        </div>
        <div v-if="src.source" class="rag-item-source">
          <code>{{ src.source }}</code>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

defineProps({
  sources: {
    type: Array,
    default: () => []
  }
})

const expanded = ref(true)
</script>

<style scoped>
.rag-sources {
  margin: 6px 0;
  border: 1px solid rgba(137,180,250,0.15);
  border-radius: 8px;
  overflow: hidden;
}

.rag-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: rgba(137,180,250,0.06);
  cursor: pointer;
  user-select: none;
}

.rag-header:hover {
  background: rgba(137,180,250,0.1);
}

.rag-icon { font-size: 14px; }
.rag-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}

.rag-count {
  font-size: 10px;
  color: var(--text-muted);
  padding: 1px 6px;
  background: var(--bg-surface);
  border-radius: 8px;
}

.toggle-btn { margin-left: auto; color: var(--text-muted); font-size: 12px; }

.rag-body {
  padding: 8px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 320px;
  overflow-y: auto;
}

.rag-item {
  padding: 8px;
  background: rgba(148,163,184,0.04);
  border-radius: 6px;
  border: 1px solid rgba(148,163,184,0.08);
}

.rag-item-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}

.rag-item-icon { font-size: 13px; }
.rag-item-title {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-primary);
}

.rag-score {
  margin-left: auto;
  font-size: 10px;
  font-weight: 600;
  color: var(--accent);
  padding: 1px 6px;
  background: rgba(137,180,250,0.12);
  border-radius: 6px;
}

.rag-item-content {
  font-size: 11px;
  line-height: 1.45;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.rag-item-source {
  font-size: 10px;
  color: var(--text-muted);
}
.rag-item-source code {
  font-family: ui-monospace, monospace;
  font-size: 10px;
}
</style>
