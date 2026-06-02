<template>
  <div class="live-eval-panel" :class="{ collapsed }">
    <button type="button" class="panel-toggle" @click="collapsed = !collapsed">
      <span class="panel-title">实时评测</span>
      <span class="panel-chevron">{{ collapsed ? '▸' : '▾' }}</span>
    </button>
    <div v-if="!collapsed" class="panel-body">
      <div class="panel-row">
        <span class="k">本轮耗时</span>
        <span class="v mono">{{ elapsedLabel }}</span>
      </div>
      <div class="panel-row">
        <span class="k">Token（累计）</span>
        <span class="v mono">{{ tokensDisplay }}</span>
      </div>
      <div class="panel-row">
        <span class="k">轨迹步数</span>
        <span class="v mono">{{ store.traceLogs.length }}</span>
      </div>
      <div class="panel-row">
        <span class="k">工具调用</span>
        <span class="v mono">{{ store.livePerf.toolEventsCount }}</span>
      </div>
      <div v-if="store.livePerf.toolSuccessRate != null" class="panel-row">
        <span class="k">工具成功率</span>
        <span class="v mono">{{ toolRatePct }}%</span>
      </div>
      <div v-if="store.livePerf.toolAvgLatencyMs != null" class="panel-row">
        <span class="k">工具平均耗时</span>
        <span class="v mono">{{ store.livePerf.toolAvgLatencyMs }} ms</span>
      </div>
      <p class="panel-hint">
        切换工作区：请点击预览区左下角附近的「IDE｜评测中心」按钮。指标来自 WebSocket 轨迹与会话快照；首轮 LLM 返回 usage 后 Token 开始递增。
      </p>
    </div>
  </div>
</template>

<script setup>
import { computed, onUnmounted, ref, watch } from 'vue'
import { useAgentStore } from '../stores/agent.js'

const store = useAgentStore()
/** 嵌入侧栏时默认展开，便于演示；仍可点击标题折叠节省空间 */
const collapsed = ref(false)
const tick = ref(0)
let timer = null

watch(
  () => store.agentRunning,
  running => {
    clearInterval(timer)
    timer = null
    if (running) {
      collapsed.value = false
      timer = setInterval(() => {
        tick.value++
      }, 250)
    }
  },
  { immediate: true }
)

onUnmounted(() => {
  clearInterval(timer)
})

const elapsedLabel = computed(() => {
  void tick.value
  const t0 = store.agentRunStartedAt
  if (!t0) return '—'
  const ms = Date.now() - t0
  if (ms < 1000) return `${ms} ms`
  const s = (ms / 1000).toFixed(1)
  return `${s} s`
})

const tokensDisplay = computed(() => {
  void tick.value
  const n = store.livePerf.tokensTotal
  return n != null ? String(n) : '—'
})

const toolRatePct = computed(() => {
  const r = store.livePerf.toolSuccessRate
  if (r == null) return '—'
  return Math.round(r * 100)
})
</script>

<style scoped>
.live-eval-panel {
  width: 100%;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  font-size: 14px;
  color: var(--text-primary);
  overflow: hidden;
}

.live-eval-panel.collapsed .panel-body {
  display: none;
}

.panel-toggle {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 10px;
  background: var(--bg-surface);
  border: none;
  cursor: pointer;
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 600;
}

.live-eval-panel.collapsed .panel-toggle {
  border-radius: 10px;
}

.panel-toggle:hover {
  color: var(--accent);
}

.panel-title {
  letter-spacing: 0.03em;
}

.panel-chevron {
  font-size: 11px;
  opacity: 0.75;
}

.panel-body {
  padding: 8px 10px 10px;
}

.panel-row {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  padding: 3px 0;
  border-bottom: 1px solid var(--border-color);
}

.panel-row:last-of-type {
  border-bottom: none;
}

.k {
  color: var(--text-muted);
  flex-shrink: 0;
}

.v {
  color: var(--accent);
  text-align: right;
  min-width: 0;
  word-break: break-all;
}

.mono {
  font-family: ui-monospace, monospace;
  font-size: 12px;
}

.panel-hint {
  margin-top: 8px;
  font-size: 12px;
  line-height: 1.45;
  color: var(--text-muted);
}
</style>
