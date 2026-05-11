<template>
  <div class="workspace-switcher" role="toolbar" aria-label="工作区切换">
    <button
      type="button"
      class="seg seg-left"
      :class="{ active: isIde }"
      :aria-pressed="isIde"
      @click="goIde"
    >
      IDE
    </button>
    <button
      type="button"
      class="seg seg-right"
      :class="{ active: !isIde }"
      :aria-pressed="!isIde"
      @click="goEval"
    >
      评测中心
    </button>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const isIde = computed(() => route.name === 'ide')

function goIde() {
  if (!isIde.value) {
    router.push({ name: 'ide' })
  }
}

function goEval() {
  if (isIde.value) {
    router.push({ name: 'eval-tasks' })
  }
}
</script>

<style scoped>
.workspace-switcher {
  position: fixed;
  left: 296px;
  bottom: 16px;
  z-index: 300;
  display: flex;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid var(--border-color);
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.35);
  background: var(--bg-secondary);
}

.seg {
  padding: 10px 18px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  background: var(--bg-secondary);
  border: none;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.seg:hover {
  color: var(--text-primary);
  background: var(--bg-surface);
}

.seg.active {
  background: var(--bg-tertiary);
  color: var(--accent);
}

.seg-left {
  border-right: 1px solid var(--border-color);
}
</style>
