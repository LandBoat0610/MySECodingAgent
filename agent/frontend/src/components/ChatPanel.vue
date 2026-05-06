<template>
  <div class="chat-panel">
    <div class="panel-header">
      <div class="header-left">
        <span class="panel-title">Agent</span>
        <span :class="['status-badge', store.sessionStatus]">{{ store.sessionStatus }}</span>
        <span v-if="cfg.model" class="model-chip" :title="'后端推理模型（与评测中心共享）'">{{ cfg.model }}</span>
        <span
          v-if="runtimeSummary"
          class="metrics-chip"
          :title="'本会话累计 Token（OpenAI usage）；工具调用次数与成功率'"
        >
          tokens {{ runtimeSummary.tokens }}
          <template v-if="runtimeSummary.toolCalls > 0">
            · 工具 {{ runtimeSummary.toolCalls }}
            <template v-if="runtimeSummary.toolOkRate != null"> · 成功率 {{ runtimeSummary.toolOkRate }}%</template>
          </template>
          <template v-else-if="runtimeSummary.llmCalls"> · LLM 调用 {{ runtimeSummary.llmCalls }}</template>
        </span>
      </div>
      <div class="header-actions">
        <button
          v-if="store.agentRunning"
          class="btn btn-sm btn-danger"
          @click="handleStopAgent"
        >
          Stop
        </button>
      </div>
    </div>

    <PlanDialog v-if="showPlanDialog" />

    <div class="chat-messages" ref="messagesContainer">
      <div v-if="store.chatMessages.length === 0 && store.traceLogs.length === 0" class="chat-empty">
        <div class="empty-icon">🤖</div>
        <div class="empty-title">Agent Platform</div>
        <div class="empty-desc">
          Select a project and session, then send a message to start working with the agent.
        </div>
      </div>

      <div v-for="(msg, idx) in store.chatMessages" :key="'msg-' + idx" :class="['message', msg.role]">
        <div class="message-avatar">{{ msg.role === 'user' ? '👤' : '🤖' }}</div>
        <div class="message-content">
          <div class="message-text">{{ msg.content }}</div>
          <div v-if="msg.tool_calls" class="message-tool-calls">
            <div v-for="(tc, tci) in msg.tool_calls" :key="tci" class="tool-call-item">
              🔧 {{ tc.function?.name || 'tool' }}
            </div>
          </div>
        </div>
      </div>

      <div v-if="store.traceLogs.length > 0" class="trace-section">
        <div class="trace-header" @click="showTrace = !showTrace">
          <span>📋 Execution Trace ({{ store.traceLogs.length }} steps)</span>
          <span class="trace-toggle">{{ showTrace ? '▾' : '▸' }}</span>
        </div>
        <div v-if="showTrace" class="trace-body">
          <div v-for="(trace, idx) in store.traceLogs" :key="'trace-' + idx" class="trace-item">
            <span :class="['trace-phase', trace.phase]">{{ trace.phase }}</span>
            <span class="trace-time">{{ trace.time }}</span>
            <span class="trace-content">{{ trace.content }}</span>
          </div>
        </div>
      </div>

      <div v-if="store.finalAnswer" class="final-answer">
        <div class="final-answer-header">📝 Final Result</div>
        <div class="final-answer-content">{{ store.finalAnswer }}</div>
      </div>

      <div v-if="store.agentRunning" class="typing-indicator">
        <span class="dot"></span><span class="dot"></span><span class="dot"></span>
      </div>
    </div>

    <div class="chat-input-area">
      <textarea
        v-model="inputMessage"
        class="chat-input"
        placeholder="Describe your task..."
        rows="2"
        @keydown.enter.exact.prevent="handleSend"
        :disabled="!store.selectedSessionId || store.agentRunning"
      ></textarea>
      <button
        class="btn btn-primary send-btn"
        @click="handleSend"
        :disabled="!store.selectedSessionId || !inputMessage.trim() || store.agentRunning"
      >
        Send
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted } from 'vue'
import { useAgentStore } from '../stores/agent.js'
import { useAgentConfigStore } from '../stores/agentConfig.js'
import PlanDialog from './PlanDialog.vue'

const store = useAgentStore()
const cfg = useAgentConfigStore()

onMounted(() => {
  if (!cfg.model) cfg.load()
})
const inputMessage = ref('')
const messagesContainer = ref(null)
const showTrace = ref(true)

const showPlanDialog = computed(() => {
  return store.sessionStatus === 'awaiting_approval' && store.pendingPlans.length > 0
})

const runtimeSummary = computed(() => {
  const rm = store.stateSnapshot?.runtime_metrics
  if (!rm) return null
  const t = rm.tokens?.total ?? 0
  const tc = rm.tool_calls?.length ?? 0
  const ok = (rm.tool_calls || []).filter(e => e.ok).length
  const rate = tc ? Math.round((ok / tc) * 100) : null
  const llm = rm.llm_calls ?? 0
  if (t === 0 && tc === 0 && llm === 0) return null
  return { tokens: t, toolCalls: tc, toolOkRate: rate, llmCalls: llm }
})

watch(() => store.chatMessages.length, async () => {
  await nextTick()
  scrollToBottom()
})

watch(() => store.traceLogs.length, async () => {
  await nextTick()
  scrollToBottom()
})

async function handleSend() {
  if (!inputMessage.value.trim() || !store.selectedSessionId || store.agentRunning) return
  const msg = inputMessage.value.trim()
  inputMessage.value = ''
  try {
    await store.doSendChat(msg)
  } catch (e) {
    inputMessage.value = msg
  }
  await nextTick()
  scrollToBottom()
}

async function handleStopAgent() {
  await store.doStopSession()
}

function scrollToBottom() {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}
</script>

<style scoped>
.chat-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: var(--bg-tertiary);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  min-width: 0;
}

.model-chip {
  font-size: 11px;
  font-family: ui-monospace, monospace;
  padding: 2px 8px;
  border-radius: 6px;
  background: var(--bg-surface);
  color: var(--accent);
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.metrics-chip {
  font-size: 11px;
  font-family: ui-monospace, monospace;
  padding: 2px 8px;
  border-radius: 6px;
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  max-width: min(420px, 100%);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.panel-title {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-secondary);
}

.status-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  text-transform: lowercase;
}

.status-badge.idle { background: var(--bg-surface); color: var(--text-muted); }
.status-badge.running { background: rgba(249, 226, 175, 0.2); color: var(--warning); }
.status-badge.awaiting_approval { background: rgba(137, 220, 235, 0.2); color: var(--info); }
.status-badge.completed { background: rgba(166, 227, 161, 0.2); color: var(--success); }
.status-badge.stopped { background: rgba(243, 139, 168, 0.2); color: var(--danger); }
.status-badge.approved { background: rgba(137, 180, 250, 0.2); color: var(--accent); }

.header-actions {
  display: flex;
  gap: 6px;
}

.btn {
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
}

.btn-sm {
  padding: 4px 10px;
  font-size: 12px;
}

.btn-primary {
  background: var(--accent);
  color: #1e1e2e;
}

.btn-primary:hover {
  background: var(--accent-hover);
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-danger {
  background: var(--danger);
  color: #1e1e2e;
}

.btn-danger:hover {
  background: #eba0ac;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.chat-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 40px 20px;
  color: var(--text-muted);
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 12px;
}

.empty-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.empty-desc {
  font-size: 12px;
  line-height: 1.5;
}

.message {
  display: flex;
  gap: 8px;
  padding: 8px;
  border-radius: 8px;
}

.message.user {
  background: var(--bg-tertiary);
}

.message.assistant {
  background: rgba(137, 180, 250, 0.05);
  border: 1px solid rgba(137, 180, 250, 0.1);
}

.message-avatar {
  font-size: 16px;
  flex-shrink: 0;
  width: 24px;
}

.message-content {
  flex: 1;
  min-width: 0;
}

.message-text {
  font-size: 13px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}

.message-tool-calls {
  margin-top: 6px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.tool-call-item {
  font-size: 11px;
  padding: 4px 8px;
  background: var(--bg-surface);
  border-radius: 4px;
  color: var(--info);
}

.trace-section {
  border-top: 1px solid var(--border-color);
  padding-top: 8px;
  margin-top: 4px;
}

.trace-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 8px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  cursor: pointer;
  border-radius: 4px;
}

.trace-header:hover {
  background: var(--bg-surface);
}

.trace-toggle {
  font-size: 10px;
  color: var(--text-muted);
}

.trace-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 4px 0;
  max-height: 250px;
  overflow-y: auto;
}

.trace-item {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 4px 8px;
  font-size: 11px;
  border-radius: 4px;
}

.trace-item:hover {
  background: var(--bg-surface);
}

.trace-phase {
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  flex-shrink: 0;
  background: var(--bg-surface);
  color: var(--text-muted);
}

.trace-phase.plan, .trace-phase.plan_result, .trace-phase.planner { color: var(--info); }
.trace-phase.reason { color: var(--accent); }
.trace-phase.act { color: var(--warning); }
.trace-phase.observe { color: var(--success); }
.trace-phase.final { color: var(--success); }
.trace-phase.cancelled { color: var(--danger); }
.trace-phase.check_result { color: var(--text-secondary); }
.trace-phase.modify_code, .trace-phase.repair_written { color: var(--warning); }

.trace-time {
  font-size: 10px;
  color: var(--text-muted);
  flex-shrink: 0;
}

.trace-content {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.final-answer {
  padding: 10px 12px;
  background: rgba(166, 227, 161, 0.08);
  border: 1px solid rgba(166, 227, 161, 0.2);
  border-radius: 8px;
}

.final-answer-header {
  font-size: 12px;
  font-weight: 600;
  color: var(--success);
  margin-bottom: 6px;
}

.final-answer-content {
  font-size: 13px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}

.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 8px 12px;
}

.typing-indicator .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-muted);
  animation: typing-bounce 1.4s ease-in-out infinite;
}

.typing-indicator .dot:nth-child(2) { animation-delay: 0.2s; }
.typing-indicator .dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing-bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
  30% { transform: translateY(-6px); opacity: 1; }
}

.chat-input-area {
  padding: 10px 14px;
  border-top: 1px solid var(--border-color);
  display: flex;
  gap: 8px;
  align-items: flex-end;
  flex-shrink: 0;
}

.chat-input {
  flex: 1;
  resize: none;
  min-height: 40px;
  max-height: 120px;
  font-size: 13px;
  line-height: 1.4;
}

.chat-input:disabled {
  opacity: 0.5;
}

.send-btn {
  flex-shrink: 0;
  padding: 8px 16px;
  height: 40px;
}
</style>
