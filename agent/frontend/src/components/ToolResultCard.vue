<template>
  <div class="tool-result-card">
    <!-- 通用：状态摘要栏 -->
    <div class="result-status-bar" :class="resultClass">
      <span class="status-icon">{{ statusIcon }}</span>
      <span class="status-label">{{ statusLabel }}</span>
      <span class="status-summary" v-if="parsed.summary">{{ parsed.summary }}</span>
      <span class="status-path" v-if="parsed.path">{{ parsed.path }}</span>
    </div>

    <!-- execute_bash / run_tests / run_lint：stdout/stderr -->
    <div v-if="hasStdio" class="result-stdio">
      <div v-if="parsed.stdout" class="stdio-block stdout">
        <div class="stdio-label">📤 stdout</div>
        <pre class="stdio-content">{{ parsed.stdout }}</pre>
      </div>
      <div v-if="parsed.stderr" class="stdio-block stderr">
        <div class="stdio-label">📥 stderr</div>
        <pre class="stdio-content">{{ parsed.stderr }}</pre>
      </div>
    </div>

    <!-- list_files：文件列表 -->
    <div v-if="toolName === 'list_files' && fileEntries.length > 0" class="result-files">
      <div class="section-label">📁 目录内容 ({{ fileEntries.length }} 项)</div>
      <div class="file-entries">
        <div v-for="entry in fileEntries" :key="entry.path" :class="['file-entry', entry.type]">
          <span class="entry-icon">{{ entry.type === 'dir' ? '📁' : '📄' }}</span>
          <span class="entry-name">{{ entry.name }}</span>
          <span class="entry-type">{{ entry.type }}</span>
        </div>
      </div>
    </div>

    <!-- web_search：搜索结果 -->
    <div v-if="toolName === 'web_search' && searchResults.length > 0" class="result-search">
      <div class="section-label">🔍 搜索结果 ({{ searchResults.length }} 条)</div>
      <div v-for="(r, i) in searchResults" :key="i" class="search-item">
        <div class="search-title">
          <a :href="r.url" target="_blank" rel="noopener">{{ r.title }}</a>
        </div>
        <div class="search-url">{{ r.url }}</div>
        <div class="search-snippet">{{ r.snippet }}</div>
      </div>
    </div>

    <!-- search_code：代码搜索结果 -->
    <div v-if="toolName === 'search_code' && codeMatches.length > 0" class="result-code-search">
      <div class="section-label">🔎 代码匹配 ({{ codeMatches.length }} 条)</div>
      <div v-for="(m, i) in codeMatches" :key="i" class="code-match">
        <span class="match-file">{{ m.file }}</span>:<span class="match-line-num">{{ m.line }}</span>
        <pre class="match-text">{{ m.text }}</pre>
      </div>
    </div>

    <!-- get_git_diff / apply_patch：Diff 展示 -->
    <div v-if="showDiffViewer" class="result-diff">
      <DiffViewer :content="diffContent" :isPatch="toolName === 'apply_patch'" />
    </div>

    <!-- fetch_url：网页抓取内容 -->
    <div v-if="toolName === 'fetch_url' && parsed.output" class="result-fetch">
      <div class="section-label">🌐 页面内容</div>
      <div class="fetch-content md-content" v-html="renderedFetchContent"></div>
    </div>

    <!-- read_file / read_file_range：文件内容 -->
    <div v-if="isFileRead && parsed.output" class="result-file-read">
      <div class="section-label">📄 文件内容</div>
      <pre class="file-content"><code v-html="highlightedFileContent"></code></pre>
    </div>

    <!-- write_file：写入确认 -->
    <div v-if="toolName === 'write_file' && parsed.output" class="result-write">
      <span class="write-icon">✅</span>
      <span class="write-msg">{{ parsed.output }}</span>
    </div>

    <!-- 通用 output（兜底） -->
    <div v-if="showGenericOutput" class="result-generic">
      <pre class="generic-content">{{ parsed.output }}</pre>
    </div>

    <!-- modified_files -->
    <div v-if="modifiedFiles.length > 0" class="result-modified">
      <div class="section-label">📝 修改的文件 ({{ modifiedFiles.length }})</div>
      <div v-for="f in modifiedFiles" :key="f" class="modified-file">📄 {{ f }}</div>
    </div>

    <!-- error -->
    <div v-if="isError" class="result-error-detail">
      <span class="error-type">{{ parsed.error_type }}</span>
      <span v-if="parsed.returncode != null" class="error-code">exit={{ parsed.returncode }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { marked } from 'marked'
import DiffViewer from './DiffViewer.vue'
import { highlightCode, inferLangFromPath, markedHighlight } from '../utils/highlight.js'

marked.setOptions({ gfm: true, breaks: true, highlight: markedHighlight })

const props = defineProps({
  /** 工具名称 */
  toolName: { type: String, default: '' },
  /** observe 阶段原始 content 字符串（JSON） */
  content: { type: String, default: '' }
})

// ── 解析 ──────────────────────────────────────────────────
const parsed = computed(() => {
  try {
    return JSON.parse(props.content || '{}')
  } catch {
    return { output: props.content || '', summary: '' }
  }
})

const isError = computed(() => parsed.value.status === 'error')
const resultClass = computed(() => isError.value ? 'error' : 'success')
const statusIcon = computed(() => isError.value ? '❌' : '✅')
const statusLabel = computed(() => isError.value ? '失败' : '成功')

const hasStdio = computed(() => !!(parsed.value.stdout || parsed.value.stderr))

// ── list_files ────────────────────────────────────────────
const fileEntries = computed(() => {
  if (props.toolName !== 'list_files') return []
  try {
    const inner = typeof parsed.value.output === 'string'
      ? JSON.parse(parsed.value.output) : parsed.value.output
    return inner?.entries || []
  } catch { return [] }
})

// ── web_search ────────────────────────────────────────────
const searchResults = computed(() => {
  if (props.toolName !== 'web_search') return []
  try {
    const inner = typeof parsed.value.output === 'string'
      ? JSON.parse(parsed.value.output) : parsed.value.output
    return inner?.results || []
  } catch { return [] }
})

// ── search_code ───────────────────────────────────────────
const codeMatches = computed(() => {
  if (props.toolName !== 'search_code') return []
  try {
    const inner = typeof parsed.value.output === 'string'
      ? JSON.parse(parsed.value.output) : parsed.value.output
    return inner?.matches || []
  } catch { return [] }
})

// ── diff ──────────────────────────────────────────────────
const showDiffViewer = computed(() =>
  (props.toolName === 'get_git_diff' || props.toolName === 'apply_patch') &&
  !!parsed.value.output
)

const diffContent = computed(() => parsed.value.output || '')

// ── file read ─────────────────────────────────────────────
const isFileRead = computed(() =>
  (props.toolName === 'read_file' || props.toolName === 'read_file_range') &&
  parsed.value.output &&
  !hasStdio.value &&
  !showDiffViewer.value
)

const fileReadLang = computed(() => {
  const p = parsed.value.path || ''
  return inferLangFromPath(p)
})

const highlightedFileContent = computed(() => {
  if (!isFileRead.value) return ''
  return highlightCode(parsed.value.output || '', fileReadLang.value)
})

// ── fetch_url ─────────────────────────────────────────────
const renderedFetchContent = computed(() => {
  if (props.toolName !== 'fetch_url' || !parsed.value.output) return ''
  try {
    return marked.parse(String(parsed.value.output).slice(0, 3000))
  } catch { return String(parsed.value.output).slice(0, 3000) }
})

// ── 通用 output ───────────────────────────────────────────
const showGenericOutput = computed(() => {
  if (!parsed.value.output) return false
  // 只在没有专门渲染时显示通用 output
  if (hasStdio.value) return false
  if (fileEntries.value.length > 0) return false
  if (searchResults.value.length > 0) return false
  if (codeMatches.value.length > 0) return false
  if (showDiffViewer.value) return false
  if (props.toolName === 'fetch_url') return false
  if (isFileRead.value) return false
  if (props.toolName === 'write_file') return false
  // execute_bash 已有 stdio，不额外显示
  if (props.toolName === 'execute_bash') return false
  return true
})

// ── modified_files ────────────────────────────────────────
const modifiedFiles = computed(() => parsed.value.modified_files || [])

const statusSummary = computed(() => parsed.value.summary || '')
</script>

<style scoped>
.tool-result-card {
  font-size: 12px;
}

/* ── 状态摘要栏 ─────────────────────────────────────────── */
.result-status-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: 6px;
  margin-bottom: 6px;
  font-weight: 500;
}
.result-status-bar.success { background: rgba(166,227,161,0.1); color: var(--success); }
.result-status-bar.error   { background: rgba(243,139,168,0.1); color: var(--danger); }

.status-summary {
  color: var(--text-secondary);
  font-weight: 400;
  margin-left: 4px;
}

.status-path {
  margin-left: auto;
  color: var(--text-muted);
  font-family: ui-monospace, monospace;
  font-size: 11px;
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ── stdio ──────────────────────────────────────────────── */
.result-stdio { margin-top: 4px; }
.stdio-block {
  border-radius: 6px;
  overflow: hidden;
  margin-bottom: 4px;
}
.stdio-block.stdout { background: rgba(166,227,161,0.05); border: 1px solid rgba(166,227,161,0.15); }
.stdio-block.stderr { background: rgba(243,139,168,0.05); border: 1px solid rgba(243,139,168,0.15); }

.stdio-label {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  padding: 4px 8px;
  background: rgba(0,0,0,0.2);
}
.stdio-content {
  margin: 0;
  padding: 8px;
  font-family: var(--font-code);
  font-size: 11px;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-all;
  color: var(--text-primary);
}

/* ── 文件列表 ───────────────────────────────────────────── */
.section-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 6px;
}

.result-files {
  margin-top: 6px;
  max-height: 240px;
  overflow-y: auto;
}

.file-entries {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.file-entry {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-family: ui-monospace, monospace;
}
.file-entry.dir { background: rgba(137,180,250,0.06); }
.file-entry .entry-icon { font-size: 13px; }
.file-entry .entry-type {
  margin-left: auto;
  font-size: 10px;
  color: var(--text-muted);
  text-transform: uppercase;
}

/* ── 搜索结果 ───────────────────────────────────────────── */
.result-search {
  margin-top: 6px;
  max-height: 320px;
  overflow-y: auto;
}

.search-item {
  padding: 6px 8px;
  border-bottom: 1px solid rgba(148,163,184,0.08);
}
.search-item:last-child { border-bottom: none; }

.search-title a {
  color: var(--accent);
  font-weight: 500;
  font-size: 12px;
  text-decoration: none;
}
.search-title a:hover { text-decoration: underline; }

.search-url {
  font-size: 10px;
  color: var(--success);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.search-snippet {
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: 2px;
}

/* ── 代码搜索 ───────────────────────────────────────────── */
.result-code-search {
  margin-top: 6px;
  max-height: 280px;
  overflow-y: auto;
}

.code-match {
  padding: 4px 8px;
  font-family: ui-monospace, monospace;
  font-size: 11px;
  border-bottom: 1px solid rgba(148,163,184,0.06);
}

.match-file { color: var(--accent); }
.match-line-num { color: var(--text-muted); margin-left: 2px; }
.match-text {
  margin: 2px 0 0;
  padding: 4px 8px;
  background: #0d1117;
  border-radius: 4px;
  font-size: 11px;
  white-space: pre-wrap;
  color: var(--text-primary);
}

/* ── Diff ───────────────────────────────────────────────── */
.result-diff { margin-top: 6px; }

/* ── fetch ──────────────────────────────────────────────── */
.result-fetch {
  margin-top: 6px;
  max-height: 320px;
  overflow-y: auto;
}
.fetch-content {
  font-size: 12px;
  line-height: 1.55;
  color: var(--text-secondary);
}

/* ── file read ──────────────────────────────────────────── */
.result-file-read {
  margin-top: 6px;
  max-height: 360px;
  overflow-y: auto;
}
.file-content {
  margin: 0;
  padding: 10px;
  background: #0d1117;
  border-radius: 6px;
  font-size: 11px;
  line-height: 1.5;
  white-space: pre-wrap;
  color: var(--text-primary);
}

/* ── write ──────────────────────────────────────────────── */
.result-write {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: rgba(166,227,161,0.08);
  border-radius: 6px;
  color: var(--success);
  margin-top: 4px;
}

/* ── modified files ─────────────────────────────────────── */
.result-modified {
  margin-top: 6px;
  padding: 6px 8px;
  background: rgba(137,180,250,0.06);
  border-radius: 6px;
}

.modified-file {
  font-size: 11px;
  font-family: ui-monospace, monospace;
  color: var(--text-secondary);
  padding: 1px 0;
}

/* ── error ──────────────────────────────────────────────── */
.result-error-detail {
  margin-top: 4px;
  display: flex;
  gap: 8px;
  font-size: 11px;
  color: var(--danger);
}
.error-type { font-weight: 600; }
.error-code { color: var(--text-muted); }

/* ── generic ────────────────────────────────────────────── */
.result-generic {
  margin-top: 6px;
}
.generic-content {
  margin: 0;
  padding: 8px;
  background: #0d1117;
  border-radius: 6px;
  font-size: 11px;
  line-height: 1.45;
  white-space: pre-wrap;
  color: var(--text-primary);
  max-height: 300px;
  overflow-y: auto;
}
</style>
