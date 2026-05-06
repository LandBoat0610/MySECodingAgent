<template>
  <div class="eval-shell">
    <header class="eval-topbar">
      <div class="eval-topbar-inner">
        <div class="eval-brand">
          <RouterLink :to="{ name: 'ide' }" class="back-to-ide">← IDE</RouterLink>
          <span class="eval-title">评测中心</span>
        </div>
        <nav class="eval-tabs">
          <RouterLink
            v-for="tab in tabs"
            :key="tab.name"
            :to="{ name: tab.name }"
            class="eval-tab"
            active-class="eval-tab-active"
          >
            {{ tab.label }}
          </RouterLink>
        </nav>
      </div>
    </header>
    <main class="eval-main">
      <div class="eval-main-inner">
        <RouterView />
      </div>
    </main>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { RouterLink, RouterView } from 'vue-router'
import { useAgentConfigStore } from '../stores/agentConfig.js'

const tabs = [
  { name: 'eval-tasks', label: '任务管理' },
  { name: 'eval-metrics', label: '指标看板' },
  { name: 'eval-compare', label: '对比分析' },
  { name: 'eval-charts', label: '图表可视化' }
]

const agentConfigStore = useAgentConfigStore()

onMounted(() => {
  agentConfigStore.load()
})
</script>

<style scoped>
.eval-shell {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  background: var(--bg-primary);
}

.eval-topbar {
  flex-shrink: 0;
  padding: 12px 20px;
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border-color);
}

.eval-topbar-inner {
  max-width: 1100px;
  margin-left: auto;
  margin-right: auto;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.eval-brand {
  display: flex;
  align-items: center;
  gap: 14px;
}

.back-to-ide {
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 13px;
  padding: 6px 10px;
  border-radius: 6px;
}

.back-to-ide:hover {
  color: var(--accent);
  background: var(--bg-surface);
}

.eval-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.eval-tabs {
  display: flex;
  gap: 6px;
}

.eval-tab {
  padding: 8px 16px;
  border-radius: 8px;
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 13px;
  font-weight: 500;
}

.eval-tab:hover {
  color: var(--text-primary);
  background: var(--bg-surface);
}

.eval-tab-active {
  color: var(--accent);
  background: var(--bg-tertiary);
}

.eval-main {
  flex: 1;
  overflow-x: hidden;
  overflow-y: auto;
  padding: 20px 24px;
}

.eval-main-inner {
  width: 100%;
  max-width: 1100px;
  margin-left: auto;
  margin-right: auto;
}
</style>
