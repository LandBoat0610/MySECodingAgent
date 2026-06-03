<template>
  <div class="diff-viewer">
    <div v-if="!diffContent" class="diff-empty">
      <span class="empty-icon">📄</span>
      <span class="empty-text">暂无差异内容</span>
    </div>
    <div v-else class="diff-content">
      <div class="diff-header">
        <span class="diff-icon" :class="{ 'diff-patch': isPatch }">
          {{ isPatch ? '🧩' : '📊' }}
        </span>
        <span class="diff-title">{{ isPatch ? '补丁 (Patch)' : 'Git Diff' }}</span>
        <span class="diff-stats" v-if="diffStats">
          <span class="stat-add">+{{ diffStats.additions }}</span>
          <span class="stat-del">-{{ diffStats.deletions }}</span>
          <span class="stat-file">{{ diffStats.files }} 个文件</span>
        </span>
      </div>
      <div class="diff-lines">
        <div
          v-for="(line, idx) in parsedLines"
          :key="idx"
          :class="['diff-line', line.type]"
        >
          <span class="line-num-old" v-if="line.oldNum">{{ line.oldNum }}</span>
          <span class="line-num-new" v-else></span>
          <span class="line-num-new" v-if="line.newNum">{{ line.newNum }}</span>
          <span class="line-num-new" v-else></span>
          <span class="line-prefix">{{ line.prefix }}</span>
          <span v-if="line.html" class="line-text" v-html="line.html"></span>
          <span v-else class="line-text">{{ line.text }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { highlightCode, inferLangFromPath } from '../utils/highlight.js'

const props = defineProps({
  content: { type: String, default: '' },
  isPatch: { type: Boolean, default: false },
  /** 被 diff 的源文件路径，用于推断代码语言以高亮 */
  filePath: { type: String, default: '' }
})

const fileLang = computed(() => inferLangFromPath(props.filePath || ''))

const diffContent = computed(() => (props.content || '').trim())

const diffStats = computed(() => {
  if (!diffContent.value) return null
  const lines = diffContent.value.split('\n')
  let additions = 0
  let deletions = 0
  const fileSet = new Set()
  for (const line of lines) {
    if (line.startsWith('+') && !line.startsWith('+++')) additions++
    if (line.startsWith('-') && !line.startsWith('---')) deletions++
    const fm = line.match(/^diff --git a\/(.+?) b\//)
    if (fm) fileSet.add(fm[1])
  }
  if (additions === 0 && deletions === 0 && fileSet.size === 0) return null
  return { additions, deletions, files: fileSet.size || 1 }
})

const parsedLines = computed(() => {
  if (!diffContent.value) return []
  const lines = diffContent.value.split('\n')
  let oldNum = 0
  let newNum = 0

  return lines.map(line => {
    if (line.startsWith('@@')) {
      const m = line.match(/@@ -(\d+),\d+ \+(\d+),\d+ @@/)
      if (m) {
        oldNum = parseInt(m[1]) - 1
        newNum = parseInt(m[2]) - 1
      }
      return { type: 'hunk-header', oldNum: null, newNum: null, prefix: '', text: line, html: null }
    }
    if (line.startsWith('+') && !line.startsWith('+++')) {
      newNum++
      const code = line.slice(1)
      return { type: 'add', oldNum: null, newNum: newNum, prefix: '+', text: code, html: highlightLine(code) }
    }
    if (line.startsWith('-') && !line.startsWith('---')) {
      oldNum++
      const code = line.slice(1)
      return { type: 'del', oldNum: oldNum, newNum: null, prefix: '-', text: code, html: highlightLine(code) }
    }
    if (line.startsWith('diff ') || line.startsWith('index ') ||
        line.startsWith('--- ') || line.startsWith('+++ ')) {
      return { type: 'meta', oldNum: null, newNum: null, prefix: '', text: line, html: null }
    }
    oldNum++
    newNum++
    return { type: 'context', oldNum: oldNum, newNum: newNum, prefix: ' ', text: line, html: highlightLine(line) }
  })
})

/** 对单行代码进行高亮（用于上下文/增/删行） */
function highlightLine(text) {
  if (!text || !fileLang.value) return null
  try {
    const result = highlightCode(text, fileLang.value)
    // 移除 highlight.js 添加的外层 <code> 标签包装
    if (result) return result
  } catch { /* ignore */ }
  return null
}
</script>

<style scoped>
.diff-viewer {
  background: #0d1117;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 8px;
  overflow: hidden;
  font-family: var(--font-code);
  font-size: 12px;
  line-height: 1.55;
  max-height: 480px;
  overflow-y: auto;
}

.diff-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 24px;
  color: var(--text-muted);
}

.diff-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #161b22;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
  position: sticky;
  top: 0;
  z-index: 2;
}

.diff-icon { font-size: 14px; }
.diff-title {
  font-weight: 600;
  color: var(--text-secondary);
  font-size: 12px;
}

.diff-stats {
  margin-left: auto;
  display: flex;
  gap: 8px;
  font-size: 11px;
}

.stat-add { color: #3fb950; }
.stat-del { color: #f85149; }
.stat-file { color: var(--text-muted); }

.diff-lines {
  /* scroll handled by parent */
}

.diff-line {
  display: flex;
  min-height: 1.55em;
  white-space: pre;
}

.diff-line.add {
  background: rgba(63, 185, 80, 0.12);
}

.diff-line.del {
  background: rgba(248, 81, 73, 0.12);
}

.diff-line.hunk-header {
  background: rgba(56, 139, 253, 0.1);
  color: #58a6ff;
}

.diff-line.meta {
  color: #8b949e;
  font-weight: 600;
}

.line-num-old,
.line-num-new {
  display: inline-block;
  width: 44px;
  min-width: 44px;
  text-align: right;
  padding-right: 8px;
  color: #484f58;
  user-select: none;
  flex-shrink: 0;
}

.diff-line.add .line-num-new { color: #3fb950; }
.diff-line.del .line-num-old { color: #f85149; }

.line-prefix {
  width: 16px;
  min-width: 16px;
  text-align: center;
  flex-shrink: 0;
}

.diff-line.add .line-prefix { color: #3fb950; }
.diff-line.del .line-prefix { color: #f85149; }

.line-text {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Scrollbar */
.diff-viewer::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}
.diff-viewer::-webkit-scrollbar-thumb {
  background: rgba(148, 163, 184, 0.35);
  border-radius: 4px;
}
.diff-viewer::-webkit-scrollbar-track {
  background: transparent;
}
</style>
