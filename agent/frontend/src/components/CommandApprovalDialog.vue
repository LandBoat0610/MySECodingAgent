<template>
  <div class="command-dialog">
    <div class="command-dialog-header">
      <span>命令确认</span>
      <span class="command-badge">等待授权</span>
    </div>
    <div class="command-dialog-body">
      <div class="command-label">命令</div>
      <pre class="command-code">{{ approval.command }}</pre>
      <div class="command-label">作用</div>
      <div class="command-purpose">{{ approval.purpose }}</div>
      <div class="command-label">反馈或修改建议</div>
      <textarea
        v-model="feedback"
        class="command-feedback"
        placeholder="例如：不要启动服务，只运行 pytest -q；或者说明拒绝原因。"
        :disabled="loading"
      ></textarea>
    </div>
    <div class="command-dialog-footer">
      <button class="btn btn-approve" :disabled="loading" @click="handleAction('approve')">
        允许执行
      </button>
      <button class="btn btn-revise" :disabled="loading" @click="handleAction('revise')">
        修改命令
      </button>
      <button class="btn btn-reject" :disabled="loading" @click="handleAction('reject')">
        拒绝执行
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useAgentStore } from '../stores/agent.js'

const store = useAgentStore()
const loading = ref(false)
const feedback = ref('')
const approval = computed(() => store.pendingCommandApproval || {})

async function handleAction(action) {
  if (!approval.value.id) return
  loading.value = true
  try {
    await store.doCommandApproval(approval.value.id, action, feedback.value.trim())
  } catch (e) {
    // handled in store
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.command-dialog {
  margin: 12px;
  border: 1px solid rgba(249, 226, 175, 0.55);
  border-radius: 10px;
  background: rgba(249, 226, 175, 0.06);
  overflow: hidden;
  flex-shrink: 0;
}
.command-dialog-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  font-weight: 700;
  color: var(--warning);
  border-bottom: 1px solid rgba(249, 226, 175, 0.18);
}
.command-badge {
  font-size: 11px;
  color: var(--text-muted);
  font-weight: 600;
}
.command-dialog-body {
  padding: 10px 12px;
}
.command-label {
  font-size: 11px;
  font-weight: 700;
  color: var(--text-muted);
  margin-bottom: 5px;
}
.command-code {
  margin: 0 0 10px;
  padding: 8px 10px;
  border-radius: 6px;
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-word;
}
.command-purpose {
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.45;
  margin-bottom: 10px;
}
.command-feedback {
  width: 100%;
  min-height: 72px;
  resize: vertical;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  background: var(--bg-surface);
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.45;
  padding: 8px 10px;
  outline: none;
  font-family: inherit;
}
.command-feedback:focus {
  border-color: var(--warning);
}
.command-dialog-footer {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  padding: 10px 12px;
  border-top: 1px solid rgba(249, 226, 175, 0.18);
}
.btn-approve {
  background: var(--success);
  color: var(--bg-primary);
}
.btn-revise {
  background: var(--warning);
  color: var(--bg-primary);
}
.btn-reject {
  background: var(--bg-tertiary);
  color: var(--text-secondary);
}
</style>
