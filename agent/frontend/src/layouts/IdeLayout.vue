<template>
  <div
    class="app-container"
    :style="{
      '--left-width': `${leftWidth}px`,
      '--right-width': `${rightWidth}px`,
    }"
  >
    <aside class="left-sidebar">
      <ProjectPanel />
      <FileTreePanel @select-file="handleSelectFile" />
      <LiveEvalHud />
    </aside>
    <div class="resize-handle resize-handle-x" title="Resize sidebar" @pointerdown="startResize('left', $event)"></div>
    <main class="center-preview">
      <FilePreview ref="filePreviewRef" />
    </main>
    <div class="resize-handle resize-handle-x" title="Resize chat" @pointerdown="startResize('right', $event)"></div>
    <aside class="right-panel">
      <ChatPanel />
    </aside>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
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
const leftWidth = ref(readSize('ide.leftWidth', 300))
const rightWidth = ref(readSize('ide.rightWidth', 430))

let resizeState = null

function readSize(key, fallback) {
  const value = Number(localStorage.getItem(key))
  return Number.isFinite(value) && value > 0 ? value : fallback
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value))
}

function handleSelectFile(node) {
  if (filePreviewRef.value) {
    filePreviewRef.value.setSelectedFile(node)
  }
}

function startResize(target, event) {
  event.preventDefault()
  const container = event.currentTarget.closest('.app-container')
  const sidebar = container?.querySelector('.left-sidebar')
  resizeState = {
    target,
    startX: event.clientX,
    startLeft: leftWidth.value,
    startRight: rightWidth.value,
    containerWidth: container?.clientWidth || window.innerWidth,
  }
  document.body.classList.add('is-resizing')
  window.addEventListener('pointermove', handleResize)
  window.addEventListener('pointerup', stopResize)
}

function handleResize(event) {
  if (!resizeState) return
  const minLeft = 220
  const minRight = 300
  const minCenter = 360
  const maxLeft = Math.max(minLeft, resizeState.containerWidth - resizeState.startRight - minCenter)
  const maxRight = Math.max(minRight, resizeState.containerWidth - leftWidth.value - minCenter)

  if (resizeState.target === 'left') {
    leftWidth.value = clamp(resizeState.startLeft + event.clientX - resizeState.startX, minLeft, maxLeft)
  } else if (resizeState.target === 'right') {
    rightWidth.value = clamp(resizeState.startRight + resizeState.startX - event.clientX, minRight, maxRight)
  }
}

function stopResize() {
  if (!resizeState) return
  localStorage.setItem('ide.leftWidth', String(leftWidth.value))
  localStorage.setItem('ide.rightWidth', String(rightWidth.value))
  resizeState = null
  document.body.classList.remove('is-resizing')
  window.removeEventListener('pointermove', handleResize)
  window.removeEventListener('pointerup', stopResize)
}

onMounted(async () => {
  await Promise.all([store.fetchProjects(), agentConfigStore.load()])
  if (store.selectedProjectId) {
    await store.fetchSessions()
    await store.fetchFileTree()
    if (store.selectedSessionId) {
      await store.restoreSessionState()
    }
    // 加载跨对话记忆上下文
    store.fetchMemoryContext()
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('pointermove', handleResize)
  window.removeEventListener('pointerup', stopResize)
  document.body.classList.remove('is-resizing')
})
</script>

<style scoped>
.left-sidebar {
  width: var(--left-width);
  min-width: 0;
}

.right-panel {
  width: var(--right-width);
  min-width: 0;
}

.resize-handle {
  flex: 0 0 auto;
  background: transparent;
  position: relative;
  z-index: 4;
}

.resize-handle-x {
  width: 5px;
  margin: 0 -2px;
  cursor: col-resize;
}

.resize-handle::after {
  content: "";
  position: absolute;
  inset: 0;
  background: transparent;
  transition: background 0.12s;
}

.resize-handle-x::after {
  left: 2px;
  right: 2px;
}

.resize-handle:hover::after {
  background: var(--accent);
}

:global(body.is-resizing) {
  cursor: col-resize;
  user-select: none;
}

:global(body.is-resizing *) {
  user-select: none;
}
</style>
