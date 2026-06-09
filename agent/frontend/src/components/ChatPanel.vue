<template>
  <div class="chat-panel">
    <!-- 顶部状态栏 -->
    <div class="panel-header">
      <div class="header-left">
        <span class="panel-title">Agent</span>
        <span :class="['status-badge', store.sessionStatus]">{{ statusLabel }}</span>
        <span v-if="cfg.model" class="model-chip" :title="'当前推理模型'">{{ cfg.model }}</span>
        <span v-if="runtimeSummary" class="metrics-chip">
          🪙 {{ runtimeSummary.tokens }} tokens
          <template v-if="runtimeSummary.toolCalls > 0">
            · 🔧 {{ runtimeSummary.toolCalls }} 次
            <template v-if="runtimeSummary.toolOkRate != null"> · {{ runtimeSummary.toolOkRate }}% 成功</template>
          </template>
          <template v-else-if="runtimeSummary.llmCalls"> · 💬 {{ runtimeSummary.llmCalls }} 次调用</template>
        </span>
      </div>
      <div class="header-actions">
        <button
          v-if="store.agentRunning"
          class="btn btn-sm btn-danger"
          @click="handleStopAgent"
        >
          ⏹ 停止
        </button>
      </div>
    </div>

    <!-- 计划确认弹窗 -->
    <PlanDialog v-if="showPlanDialog" />
    <CommandApprovalDialog v-if="showCommandApprovalDialog" />
    <ContinueApprovalDialog v-if="showContinueApprovalDialog" />

    <!-- 消息与轨迹区域 -->
    <div class="chat-messages" ref="messagesContainer" @scroll="handleMessagesScroll">
      <div v-if="store.roundsLoadingOlder" class="history-loader">加载更早的对话…</div>

      <!-- 空状态 -->
      <div v-if="isEmpty" class="chat-empty">
        <div class="empty-icon">🤖</div>
        <div class="empty-title">Agent Platform</div>
        <div class="empty-desc">选择项目后直接发送消息，系统会自动创建对话。</div>
      </div>

      <!-- ══ 多轮模式：每轮独立展示 ══ -->
      <template v-if="isRoundMode">
        <template v-for="(round, rIdx) in allRounds" :key="'round-' + rIdx">

          <!-- 用户消息气泡 -->
          <div class="message user round-user">
            <div class="message-avatar">👤</div>
            <div class="message-body">
              <div class="message-label">
                用户
              </div>
              <div class="message-text md-content" v-html="renderMd(round.userMessage)"></div>
            </div>
          </div>

          <!-- 执行时间线 -->
          <div
            v-if="round.taskListItems.length > 0 || round.displayTrace.length > 0 || (round.isCurrent && store.agentRunning)"
            class="agent-timeline"
            :class="{ 'timeline-completed': !round.isCurrent }"
          >
            <div class="timeline-section-label">
              ⚙️ 执行过程
              <span v-if="!round.isCurrent" class="label-done">· 已完成</span>
            </div>

            <!-- 执行计划卡片 -->
            <div v-if="round.taskListItems.length > 0" class="timeline-card card-plan">
              <div class="card-header" @click="toggleRoundPlan(rIdx)">
                <span class="phase-icon">📋</span>
                <span class="card-title">执行计划</span>
                <span class="card-badge">{{ round.taskListItems.length }} 步</span>
                <span class="toggle-btn">{{ isRoundPlanExpanded(rIdx) ? '▾' : '▸' }}</span>
              </div>
              <div v-if="isRoundPlanExpanded(rIdx)" class="plan-steps">
                <div
                  v-for="(step, sIdx) in round.taskListItems"
                  :key="sIdx"
                  :class="['plan-step', getRoundStepStatus(round, sIdx)]"
                >
                  <span class="step-icon">{{ getRoundStepIcon(round, sIdx) }}</span>
                  <span class="step-text">{{ step }}</span>
                </div>
              </div>
            </div>

            <!-- 轨迹条目 -->
            <template v-for="(item, iIdx) in round.displayTrace" :key="'ti-' + iIdx">

              <!-- 推理分隔线 -->
              <div v-if="item.phase === 'reason'" class="step-divider">
                <span class="divider-dot"></span>
                <span class="divider-label">▶ {{ parseReasonLabel(item.content, round.taskListItems) }}</span>
                <span class="divider-time">{{ item.time }}</span>
              </div>

              <!-- 规划器消息 -->
              <div v-else-if="item.phase === 'planner'" class="timeline-card card-planner">
                <div class="card-header">
                  <span class="phase-icon">🗺️</span>
                  <span class="card-title">{{ item.content }}</span>
                  <span class="card-time">{{ item.time }}</span>
                </div>
              </div>

              <!-- 工具调用卡片 -->
              <div v-else-if="item.phase === 'act'" class="timeline-card card-act">
                <div class="card-header clickable" @click="toggleRoundItem(rIdx, iIdx)">
                  <span class="phase-icon">🔧</span>
                  <span class="card-title tool-name">{{ parseActTitle(item.content) }}</span>
                  <span class="card-badge act-badge">工具调用</span>
                  <span class="card-time">{{ item.time }}</span>
                  <span class="toggle-btn">{{ isRoundItemExpanded(rIdx, iIdx) ? '▾' : '▸' }}</span>
                </div>
                <div v-if="isRoundItemExpanded(rIdx, iIdx)" class="card-body">
                  <div class="args-label">参数：</div>
                  <pre class="code-block">{{ parseActArgs(item.content) }}</pre>
                  <template v-if="item.attachedObserve">
                    <div class="args-label command-result-label">执行结果：</div>
                    <div
                      class="observe-output command-attached-result"
                      :class="{ 'result-error': observeIsError(item.attachedObserve.content) }"
                    >
                      {{ parseObserveOutput(item.attachedObserve.content) }}
                    </div>
                  </template>
                </div>
              </div>

              <!-- 工具结果卡片 -->
              <div
                v-else-if="item.phase === 'observe'"
                class="timeline-card card-observe"
                :class="{ 'card-error': observeIsError(item.content) }"
              >
                <div class="card-header clickable" @click="toggleRoundItem(rIdx, iIdx)">
                  <span class="phase-icon">{{ observeIsError(item.content) ? '⚠️' : '👁️' }}</span>
                  <span class="card-title">执行结果</span>
                  <span :class="['card-badge', observeIsError(item.content) ? 'badge-error' : 'badge-ok']">
                    {{ observeIsError(item.content) ? '错误' : '成功' }}
                  </span>
                  <span class="card-time">{{ item.time }}</span>
                  <span class="toggle-btn">{{ isRoundItemExpanded(rIdx, iIdx) ? '▾' : '▸' }}</span>
                </div>
                <div v-if="isRoundItemExpanded(rIdx, iIdx)" class="card-body">
                  <ToolResultCard
                    :toolName="getObserveToolName(round.displayTrace, iIdx)"
                    :content="item.content"
                  />
                  <RagSources
                    v-if="extractRagSources(item).length > 0"
                    :sources="extractRagSources(item)"
                  />
                </div>
              </div>

              <!-- 步骤完成 -->
              <div v-else-if="item.phase === 'finish_step'" class="timeline-card card-finish">
                <div class="card-header clickable" @click="toggleRoundItem(rIdx, iIdx)">
                  <span class="phase-icon">✅</span>
                  <span class="card-title">步骤完成</span>
                  <span class="card-time">{{ item.time }}</span>
                  <span class="toggle-btn">{{ isRoundItemExpanded(rIdx, iIdx) ? '▾' : '▸' }}</span>
                </div>
                <div v-if="isRoundItemExpanded(rIdx, iIdx)" class="card-body">
                  <div class="finish-text md-content" v-html="renderMd(item.content)"></div>
                </div>
                <div v-else class="card-inline-preview">{{ item.content.slice(0, 100) }}{{ item.content.length > 100 ? '…' : '' }}</div>
              </div>

              <!-- 结果检查 -->
              <div v-else-if="item.phase === 'check_result'" class="timeline-card card-check">
                <div class="card-header">
                  <span class="phase-icon">{{ parseCheckResult(item.content).failed ? '❌' : '✔️' }}</span>
                  <span class="card-title">结果检查</span>
                  <span :class="['card-badge', parseCheckResult(item.content).failed ? 'badge-error' : 'badge-ok']">
                    {{ parseCheckResult(item.content).failed ? '需修复' : '通过' }}
                  </span>
                  <span class="check-reason">{{ parseCheckResult(item.content).reason }}</span>
                  <span class="card-time">{{ item.time }}</span>
                </div>
              </div>

              <!-- 代码修复 -->
              <div
                v-else-if="item.phase === 'modify_code' || item.phase === 'repair_written'"
                class="timeline-card card-repair"
              >
                <div class="card-header clickable" @click="toggleRoundItem(rIdx, iIdx)">
                  <span class="phase-icon">🛠️</span>
                  <span class="card-title">{{ item.phase === 'modify_code' ? '代码修复中…' : '修复已写入' }}</span>
                  <span class="card-badge badge-repair">自我修正</span>
                  <span class="card-time">{{ item.time }}</span>
                  <span class="toggle-btn">{{ isRoundItemExpanded(rIdx, iIdx) ? '▾' : '▸' }}</span>
                </div>
                <div v-if="isRoundItemExpanded(rIdx, iIdx)" class="card-body">
                  <div class="repair-text md-content" v-html="renderMd(item.content)"></div>
                </div>
              </div>

              <!-- 已取消 -->
              <div v-else-if="item.phase === 'cancelled'" class="timeline-card card-cancelled">
                <div class="card-header">
                  <span class="phase-icon">⛔</span>
                  <span class="card-title">执行已取消</span>
                  <span class="card-time">{{ item.time }}</span>
                </div>
              </div>

            </template>

            <!-- 当前轮运行中动态指示 -->
            <div v-if="round.isCurrent && store.agentRunning" class="running-indicator">
              <span class="dot"></span><span class="dot"></span><span class="dot"></span>
              <span class="running-text">Agent 处理中…</span>
            </div>
          </div>

          <!-- 轮次分隔线（历史轮之间） -->
          <div v-if="!round.isCurrent && rIdx < allRounds.length - 1" class="round-separator"></div>

          <!-- 最终结果 -->
          <div v-if="round.finalAnswer" class="message assistant round-answer">
            <div class="message-avatar">🤖</div>
            <div class="message-body">
              <div class="message-label">最终结果</div>
              <div class="message-text md-content" v-html="renderMd(cleanFinalAnswer(round.finalAnswer))"></div>
            </div>
          </div>

        </template>
      </template>

      <!-- ══ 兼容模式：从 DB 恢复的历史会话 ══ -->
      <template v-else-if="isLegacyMode">
        <!-- 所有历史消息 -->
        <div
          v-for="(msg, idx) in filteredMessages"
          :key="'lm-' + idx"
          :class="['message', msg.role]"
        >
          <div class="message-avatar">{{ msg.role === 'user' ? '👤' : '🤖' }}</div>
          <div class="message-body">
            <div class="message-label">{{ msg.role === 'user' ? '用户' : 'Agent 回复' }}</div>
            <div class="message-text md-content" v-html="renderMd(msg.content)"></div>
          </div>
        </div>

        <!-- 快照轨迹 -->
        <div v-if="legacyTaskList.length > 0 || legacyTrace.length > 0 || store.agentRunning" class="agent-timeline">
          <div class="timeline-section-label">⚙️ 执行过程</div>

          <div v-if="legacyTaskList.length > 0" class="timeline-card card-plan">
            <div class="card-header" @click="toggleLegacyPlan()">
              <span class="phase-icon">📋</span>
              <span class="card-title">执行计划</span>
              <span class="card-badge">{{ legacyTaskList.length }} 步</span>
              <span class="toggle-btn">{{ legacyPlanExpanded ? '▾' : '▸' }}</span>
            </div>
            <div v-if="legacyPlanExpanded" class="plan-steps">
              <div
                v-for="(step, i) in legacyTaskList"
                :key="i"
                :class="['plan-step', getLegacyStepStatus(i)]"
              >
                <span class="step-icon">{{ getLegacyStepIcon(i) }}</span>
                <span class="step-text">{{ step }}</span>
              </div>
            </div>
          </div>

          <template v-for="(item, iIdx) in legacyTrace" :key="'lt-' + iIdx">
            <div v-if="item.phase === 'reason'" class="step-divider">
              <span class="divider-dot"></span>
              <span class="divider-label">▶ {{ parseReasonLabel(item.content, legacyTaskList) }}</span>
              <span class="divider-time">{{ item.time }}</span>
            </div>
            <div v-else-if="item.phase === 'planner'" class="timeline-card card-planner">
              <div class="card-header">
                <span class="phase-icon">🗺️</span>
                <span class="card-title">{{ item.content }}</span>
                <span class="card-time">{{ item.time }}</span>
              </div>
            </div>
            <div v-else-if="item.phase === 'act'" class="timeline-card card-act">
              <div class="card-header clickable" @click="toggleLegacyItem(iIdx)">
                <span class="phase-icon">🔧</span>
                <span class="card-title tool-name">{{ parseActTitle(item.content) }}</span>
                <span class="card-badge act-badge">工具调用</span>
                <span class="card-time">{{ item.time }}</span>
                <span class="toggle-btn">{{ legacyExpanded[iIdx] ? '▾' : '▸' }}</span>
              </div>
              <div v-if="legacyExpanded[iIdx]" class="card-body">
                <div class="args-label">参数：</div>
                <pre class="code-block">{{ parseActArgs(item.content) }}</pre>
                <template v-if="item.attachedObserve">
                  <div class="args-label command-result-label">执行结果：</div>
                  <div
                    class="observe-output command-attached-result"
                    :class="{ 'result-error': observeIsError(item.attachedObserve.content) }"
                  >
                    {{ parseObserveOutput(item.attachedObserve.content) }}
                  </div>
                </template>
              </div>
            </div>
            <div v-else-if="item.phase === 'observe'" class="timeline-card card-observe" :class="{ 'card-error': observeIsError(item.content) }">
              <div class="card-header clickable" @click="toggleLegacyItem(iIdx)">
                <span class="phase-icon">{{ observeIsError(item.content) ? '⚠️' : '👁️' }}</span>
                <span class="card-title">执行结果</span>
                <span :class="['card-badge', observeIsError(item.content) ? 'badge-error' : 'badge-ok']">{{ observeIsError(item.content) ? '错误' : '成功' }}</span>
                <span class="card-time">{{ item.time }}</span>
                <span class="toggle-btn">{{ legacyExpanded[iIdx] ? '▾' : '▸' }}</span>
              </div>
              <div v-if="legacyExpanded[iIdx]" class="card-body">
                <ToolResultCard
                  :toolName="getObserveToolName(legacyTrace, iIdx)"
                  :content="item.content"
                />
                <RagSources
                  v-if="extractRagSources(item).length > 0"
                  :sources="extractRagSources(item)"
                />
              </div>
            </div>
            <div v-else-if="item.phase === 'finish_step'" class="timeline-card card-finish">
              <div class="card-header clickable" @click="toggleLegacyItem(iIdx)">
                <span class="phase-icon">✅</span>
                <span class="card-title">步骤完成</span>
                <span class="card-time">{{ item.time }}</span>
                <span class="toggle-btn">{{ legacyExpanded[iIdx] ? '▾' : '▸' }}</span>
              </div>
              <div v-if="legacyExpanded[iIdx]" class="card-body">
                <div class="finish-text md-content" v-html="renderMd(item.content)"></div>
              </div>
              <div v-else class="card-inline-preview">{{ item.content.slice(0, 100) }}{{ item.content.length > 100 ? '…' : '' }}</div>
            </div>
            <div v-else-if="item.phase === 'check_result'" class="timeline-card card-check">
              <div class="card-header">
                <span class="phase-icon">{{ parseCheckResult(item.content).failed ? '❌' : '✔️' }}</span>
                <span class="card-title">结果检查</span>
                <span :class="['card-badge', parseCheckResult(item.content).failed ? 'badge-error' : 'badge-ok']">{{ parseCheckResult(item.content).failed ? '需修复' : '通过' }}</span>
                <span class="check-reason">{{ parseCheckResult(item.content).reason }}</span>
                <span class="card-time">{{ item.time }}</span>
              </div>
            </div>
            <div v-else-if="item.phase === 'modify_code' || item.phase === 'repair_written'" class="timeline-card card-repair">
              <div class="card-header clickable" @click="toggleLegacyItem(iIdx)">
                <span class="phase-icon">🛠️</span>
                <span class="card-title">{{ item.phase === 'modify_code' ? '代码修复中…' : '修复已写入' }}</span>
                <span class="card-badge badge-repair">自我修正</span>
                <span class="card-time">{{ item.time }}</span>
                <span class="toggle-btn">{{ legacyExpanded[iIdx] ? '▾' : '▸' }}</span>
              </div>
              <div v-if="legacyExpanded[iIdx]" class="card-body">
                <div class="repair-text md-content" v-html="renderMd(item.content)"></div>
              </div>
            </div>
            <div v-else-if="item.phase === 'cancelled'" class="timeline-card card-cancelled">
              <div class="card-header">
                <span class="phase-icon">⛔</span>
                <span class="card-title">执行已取消</span>
                <span class="card-time">{{ item.time }}</span>
              </div>
            </div>
          </template>

          <div v-if="store.agentRunning" class="running-indicator">
            <span class="dot"></span><span class="dot"></span><span class="dot"></span>
            <span class="running-text">Agent 处理中…</span>
          </div>
        </div>

      </template>

    </div>

    <!-- 输入区域 -->
    <div class="chat-input-area">
      <textarea
        v-model="inputMessage"
        class="chat-input"
        placeholder="描述你的任务，按 Enter 发送…"
        rows="2"
        @keydown.enter.exact.prevent="handleSend"
        :disabled="!store.selectedProjectId || store.agentRunning"
      ></textarea>
      <button
        class="btn btn-primary send-btn"
        @click="handleSend"
        :disabled="!store.selectedProjectId || !inputMessage.trim() || store.agentRunning"
      >
        发送
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, reactive } from 'vue'
import { useAgentStore } from '../stores/agent.js'
import { useAgentConfigStore } from '../stores/agentConfig.js'
import PlanDialog from './PlanDialog.vue'
import CommandApprovalDialog from './CommandApprovalDialog.vue'
import ContinueApprovalDialog from './ContinueApprovalDialog.vue'
import ToolResultCard from './ToolResultCard.vue'
import DiffViewer from './DiffViewer.vue'
import RagSources from './RagSources.vue'
import { marked } from 'marked'
import { markedHighlight } from '../utils/highlight.js'

marked.setOptions({
  gfm: true,
  breaks: true,
  highlight: markedHighlight
})

function renderMd(text) {
  if (!text) return ''
  try { return marked.parse(String(text)) } catch { return String(text) }
}

const store = useAgentStore()
const cfg = useAgentConfigStore()

onMounted(() => { if (!cfg.model) cfg.load() })

const inputMessage = ref('')
const messagesContainer = ref(null)
const preservingHistoryScroll = ref(false)

// ── 内部阶段黑名单 ────────────────────────────────────────
const HIDDEN_PHASES = new Set([
  'final', 'plan', 'plan_result', 'plan_error',
  'infer_targets', 'infer_targets_result',
  'infer_targets_error', 'infer_targets_prompt_error',
])

// ── 轨迹过滤：去掉内部阶段 + reason 按步骤去重 ──────────
function filterTrace(logs) {
  const seenSteps = new Set()
  return logs.filter(item => {
    if (HIDDEN_PHASES.has(item.phase)) return false
    if (item.phase === 'reason') {
      const m = item.content.match(/Step '(.+)' iteration/)
      const key = m ? m[1] : item.content
      if (seenSteps.has(key)) return false
      seenSteps.add(key)
    }
    return true
  })
}

function getActToolName(item) {
  if (item?.meta?.tool) return item.meta.tool
  const m = String(item?.content || '').match(/^(\w+)\(/)
  return m ? m[1] : ''
}

function attachCommandResults(logs) {
  const items = filterTrace(logs)
  const attachedObserveIndexes = new Set()

  return items
    .map((item, idx) => {
      if (item.phase !== 'act' || getActToolName(item) !== 'execute_bash') return item
      for (let j = idx + 1; j < items.length; j += 1) {
        const next = items[j]
        if (next.phase === 'observe') {
          attachedObserveIndexes.add(j)
          return { ...item, attachedObserve: next }
        }
        if (next.phase === 'act' || next.phase === 'reason' || next.phase === 'finish_step') break
      }
      return item
    })
    .filter((_, idx) => !attachedObserveIndexes.has(idx))
}

const VISIBLE_PLAN_STATUSES = new Set(['pending', 'approved', 'completed'])

function isVisiblePlan(plan) {
  return VISIBLE_PLAN_STATUSES.has(plan.status)
}

// 计划步骤：只过滤，不重排序——后端已保证 rowid ASC 插入顺序
// 二次排序会因 created_at 相同时用随机 UUID 比较而乱序
function sortedTaskList(plans) {
  return plans
    .filter(isVisiblePlan)
    .map(p => p.content)
}

// ── 当前轮 taskList（仅返回本轮新到的计划，不兜底旧快照）────
// 新轮发送后 plans 为空，此处直接返回 []，让用户看到"等待 Agent 规划"
// 待 Agent 生成新计划并 fetchPlans() 后，这里才会有数据
const taskList = computed(() => {
  const scopedPlans = store.currentRoundPlans || store.plans
  const hasRoundScopedPlans = store.currentRoundId && scopedPlans.length > 0
  const active = hasRoundScopedPlans
    ? scopedPlans
    : store.plans.filter(p => !store.prevRoundPlanIds.has(p.id))
  return sortedTaskList(active)
})

// ── 当前轮 displayTrace ───────────────────────────────────
const displayTrace = computed(() => attachCommandResults(store.traceLogs))

// ── 轮次模式 vs 兼容模式 ─────────────────────────────────
const isRoundMode = computed(() =>
  store.completedRounds.length > 0 || !!store.currentRoundUserMsg
)

// 合并历史轮 + 当前轮
const allRounds = computed(() => {
  const rounds = store.completedRounds.map(r => ({
    userMessage: r.userMessage,
    taskListItems: sortedTaskList(r.plans),
    displayTrace: attachCommandResults(r.traceLogs),
    finalAnswer: r.finalAnswer,
    isCurrent: false,
  }))
  if (store.currentRoundUserMsg) {
    rounds.push({
      userMessage: store.currentRoundUserMsg,
      taskListItems: taskList.value,
      displayTrace: displayTrace.value,
      finalAnswer: store.finalAnswer,
      isCurrent: true,
    })
  }
  return rounds
})

// ── 兼容模式（页面刷新后 DB 恢复）────────────────────────
const filteredMessages = computed(() =>
  store.chatMessages.filter(m => {
    if (m.role === 'system') return false
    if (m.role === 'tool') return false
    if (m.role === 'user' && m.content?.startsWith('Current step:')) return false
    if (m.role === 'assistant' && !m.content?.trim()) return false
    return true
  })
)

const legacyTaskList = computed(() => {
  const active = store.plans.filter(isVisiblePlan)
  const items = sortedTaskList(active)
  return items.length > 0 ? items : (store.stateSnapshot?.task_list || [])
})

const legacyTrace = computed(() => attachCommandResults(store.traceLogs))

const isLegacyMode = computed(() =>
  !isRoundMode.value && (
    filteredMessages.value.length > 0 ||
    store.traceLogs.length > 0 ||
    !!store.finalAnswer
  )
)

// ── 空状态 ───────────────────────────────────────────────
const isEmpty = computed(() =>
  !isRoundMode.value && !isLegacyMode.value && !store.agentRunning
)

// ── 状态标签 ─────────────────────────────────────────────
const STATUS_LABELS = {
  idle: '就绪', running: '运行中', awaiting_approval: '等待确认',
  awaiting_tool_approval: '等待命令确认',
  awaiting_continue_approval: '等待继续确认',
  approved: '已批准', completed: '已完成', stopped: '已停止',
  needs_fix: '修复中', next_step: '下一步', skipped: '已跳过',
}
const statusLabel = computed(() => STATUS_LABELS[store.sessionStatus] || store.sessionStatus)

// ── 计划弹窗 ─────────────────────────────────────────────
const showPlanDialog = computed(() =>
  store.sessionStatus === 'awaiting_approval' && store.pendingPlans.length > 0
)
const showCommandApprovalDialog = computed(() =>
  !!store.pendingCommandApproval
)
const showContinueApprovalDialog = computed(() =>
  store.sessionStatus === 'awaiting_continue_approval' && !!store.pendingLoopApproval
)

// ── 运行时指标摘要 ───────────────────────────────────────
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

// ── 多轮展开状态 ─────────────────────────────────────────
const expandedRoundPlans = reactive({})
const expandedRoundItems = reactive({})

function toggleRoundPlan(rIdx) {
  expandedRoundPlans[rIdx] = expandedRoundPlans[rIdx] === false ? true : false
}
function isRoundPlanExpanded(rIdx) {
  return expandedRoundPlans[rIdx] !== false // 默认展开
}
function toggleRoundItem(rIdx, iIdx) {
  const k = `${rIdx}-${iIdx}`
  expandedRoundItems[k] = !expandedRoundItems[k]
}
function isRoundItemExpanded(rIdx, iIdx) {
  return !!expandedRoundItems[`${rIdx}-${iIdx}`]
}

// ── 多轮步骤状态 ─────────────────────────────────────────
function getRoundStepStatus(round, stepIdx) {
  if (!round.isCurrent) return 'done'
  const currentIdx = store.stateSnapshot?.current_task_index ?? 0
  const done = store.sessionStatus === 'completed' || !!store.finalAnswer
  if (done) return 'done'
  if (stepIdx < currentIdx) return 'done'
  if (stepIdx === currentIdx && store.agentRunning) return 'current'
  return 'pending'
}
function getRoundStepIcon(round, stepIdx) {
  const s = getRoundStepStatus(round, stepIdx)
  if (s === 'done') return '✓'
  if (s === 'current') return '▶'
  return '○'
}

// ── 兼容模式展开状态 ─────────────────────────────────────
const legacyPlanExpanded = ref(true)
const legacyExpanded = reactive({})
function toggleLegacyPlan() { legacyPlanExpanded.value = !legacyPlanExpanded.value }
function toggleLegacyItem(idx) { legacyExpanded[idx] = !legacyExpanded[idx] }

async function handleMessagesScroll() {
  const el = messagesContainer.value
  if (!el || el.scrollTop > 80 || !store.roundsHasMore || store.roundsLoadingOlder) return
  const previousHeight = el.scrollHeight
  preservingHistoryScroll.value = true
  const loaded = await store.loadOlderRounds()
  try {
    if (!loaded) return
    await nextTick()
    el.scrollTop = el.scrollHeight - previousHeight + el.scrollTop
  } finally {
    preservingHistoryScroll.value = false
  }
}

function getLegacyStepStatus(idx) {
  const currentIdx = store.stateSnapshot?.current_task_index ?? 0
  const done = store.sessionStatus === 'completed' || !!store.finalAnswer
  if (done) return 'done'
  if (idx < currentIdx) return 'done'
  if (idx === currentIdx && store.agentRunning) return 'current'
  return 'pending'
}
function getLegacyStepIcon(idx) {
  const s = getLegacyStepStatus(idx)
  if (s === 'done') return '✓'
  if (s === 'current') return '▶'
  return '○'
}

// ── 自动展开当前轮最新 act 条目 ──────────────────────────
watch(() => store.traceLogs.length, (newLen, oldLen) => {
  if (newLen <= oldLen) return
  const item = store.traceLogs[newLen - 1]
  if (item?.phase !== 'act') return
  const rIdx = store.completedRounds.length // 当前轮在 allRounds 中的索引
  const dt = displayTrace.value
  if (dt.length > 0 && dt[dt.length - 1]?.phase === 'act') {
    expandedRoundItems[`${rIdx}-${dt.length - 1}`] = true
  }
})

// ── 解析工具 ──────────────────────────────────────────────
function parseReasonLabel(content, taskListItems) {
  const m = content.match(/Step '(.+)' iteration \d+/)
  if (m) {
    const stepText = m[1]
    const idx = (taskListItems || []).indexOf(stepText)
    const prefix = idx >= 0 ? `步骤 ${idx + 1}/${taskListItems.length}：` : '执行步骤：'
    return prefix + stepText
  }
  return content
}

function parseActTitle(content) {
  const m = content.match(/^(\w+)\(/)
  if (!m) return content.slice(0, 50)
  const toolNames = {
    execute_bash: '💻 执行命令',
    list_files: '📂 列出目录',
    read_file_range: '📖 按行读取',
    read_file: '📄 读取文件',
    write_file: '✏️ 写入文件',
    web_search: '🔍 Web 搜索',
    fetch_url: '🌐 抓取网页',
    search_code: '🔎 代码搜索',
    apply_patch: '🧩 应用补丁',
    get_git_diff: '📊 查看差异',
    run_tests: '🧪 运行测试',
    run_lint: '🔬 代码检查',
  }
  return toolNames[m[1]] || m[1]
}

function parseActArgs(content) {
  const m = content.match(/^(\w+)\(([\s\S]*)\)$/)
  if (!m) return content
  try {
    const jsonStr = m[2]
      .replace(/'/g, '"').replace(/True/g, 'true')
      .replace(/False/g, 'false').replace(/None/g, 'null')
    return JSON.stringify(JSON.parse(jsonStr), null, 2)
  } catch { return m[2] }
}

function observeIsError(content) {
  try { return JSON.parse(content)?.status === 'error' } catch { return false }
}

function parseObserveOutput(content) {
  try {
    const obj = JSON.parse(content)
    const out = obj.output ?? content
    return typeof out === 'string' ? out : JSON.stringify(out, null, 2)
  } catch { return content }
}

function parseCheckResult(content) {
  try { return JSON.parse(content) } catch { return { failed: false, reason: content } }
}

// ── 获取 observe 项对应的工具名 ──────────────────────────
function getObserveToolName(traceItems, observeIndex) {
  // 向前查找最近的 act 项
  for (let i = observeIndex - 1; i >= 0; i--) {
    const item = traceItems[i]
    if (item.phase === 'act') {
      const m = String(item.content || '').match(/^(\w+)\(/)
      return m ? m[1] : ''
    }
    // 如果遇到 reason/planner 等，说明不属于同一工具调用
    if (item.phase === 'reason' || item.phase === 'planner' || item.phase === 'finish_step') break
  }
  return ''
}

// ── 提取 RAG 来源 ────────────────────────────────────────
function extractRagSources(traceItem) {
  const meta = traceItem?.meta || {}
  if (meta.rag_sources && Array.isArray(meta.rag_sources)) return meta.rag_sources
  // 也检查 content 中是否包含 rag_sources
  try {
    const obj = JSON.parse(traceItem?.content || '{}')
    if (obj.rag_sources && Array.isArray(obj.rag_sources)) return obj.rag_sources
  } catch { /* ignore */ }
  return []
}

function cleanFinalAnswer(raw) {
  if (!raw) return ''
  // 提取 "Step results:" 到 "Final status:" 之间的内容
  const stepMatch = raw.match(/Step results:\s*([\s\S]*?)\s*Final status:/)
  if (stepMatch) {
    return stepMatch[1].trim()
  }
  // 如果没有 "Step results:" 标记，尝试去掉元数据行后返回
  // 去掉 "Overall task:" 到 "Latest verification:" 之间的元数据块
  const cleaned = raw
    .replace(/^Overall task:[\s\S]*?Latest verification:\s*\{[\s\S]*?\}\s*/m, '')
    .replace(/Final status:\s*\S+\s*$/, '')
    .trim()
  return cleaned || raw.trim()
}

// ── 事件处理 ─────────────────────────────────────────────
async function handleSend() {
  if (!inputMessage.value.trim() || !store.selectedProjectId || store.agentRunning) return
  const msg = inputMessage.value.trim()
  inputMessage.value = ''
  try {
    await store.doSendChat(msg)
  } catch {
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

watch(() => store.traceLogs.length, async () => { await nextTick(); scrollToBottom() })
watch(() => store.completedRounds.length, async () => {
  await nextTick()
  if (!preservingHistoryScroll.value) scrollToBottom()
})
watch(() => store.finalAnswer, async () => { await nextTick(); scrollToBottom() })
</script>

<style scoped>
/* ── 整体布局 ──────────────────────────────────────────── */
.chat-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

/* ── 顶部状态栏 ────────────────────────────────────────── */
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: var(--bg-tertiary);
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  min-width: 0;
}
.panel-title {
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.6px;
  color: var(--text-secondary);
}
.status-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 500;
}
.status-badge.idle       { background: var(--bg-surface); color: var(--text-muted); }
.status-badge.running    { background: rgba(249,226,175,0.2); color: var(--warning); }
.status-badge.awaiting_approval { background: rgba(137,220,235,0.2); color: var(--info); }
.status-badge.completed  { background: rgba(166,227,161,0.2); color: var(--success); }
.status-badge.stopped    { background: rgba(243,139,168,0.2); color: var(--danger); }
.status-badge.approved   { background: rgba(137,180,250,0.2); color: var(--accent); }
.status-badge.needs_fix  { background: rgba(250,179,135,0.2); color: #fab387; }

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
  background: var(--bg-surface);
  color: var(--text-secondary);
}
.header-actions { display: flex; gap: 6px; }
.btn { border-radius: 6px; font-size: 13px; font-weight: 500; cursor: pointer; border: none; }
.btn-sm { padding: 4px 10px; font-size: 12px; }
.btn-primary { background: var(--accent); color: #1e1e2e; padding: 8px 16px; }
.btn-primary:hover { background: var(--accent-hover); }
.btn-primary:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-danger { background: var(--danger); color: #1e1e2e; }
.btn-danger:hover { background: #eba0ac; }

/* ── 消息滚动区 ────────────────────────────────────────── */
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 14px 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* ── 空状态 ────────────────────────────────────────────── */
.chat-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 40px 20px;
  color: var(--text-muted);
  flex: 1;
}
.empty-icon  { font-size: 48px; margin-bottom: 12px; }
.empty-title { font-size: 16px; font-weight: 600; color: var(--text-secondary); margin-bottom: 8px; }
.empty-desc  { font-size: 12px; line-height: 1.5; }

/* ── 用户 / 助手消息气泡 ───────────────────────────────── */
.message {
  display: flex;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
}
.message.user      { background: var(--bg-tertiary); }
.message.assistant { background: rgba(137,180,250,0.06); border: 1px solid rgba(137,180,250,0.12); }

.message-avatar {
  font-size: 18px;
  flex-shrink: 0;
  width: 26px;
  padding-top: 1px;
}
.message-body { flex: 1; min-width: 0; }
.message-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-muted);
  margin-bottom: 4px;
}
.message-text {
  font-size: 13px;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
}

/* ── 执行时间线 ─────────────────────────────────────────── */
.agent-timeline {
  display: flex;
  flex-direction: column;
  gap: 6px;
  border-left: 2px solid var(--border-color);
  padding-left: 12px;
  margin-left: 2px;
}
.agent-timeline.timeline-completed {
  border-left-color: rgba(166,227,161,0.3);
  opacity: 0.85;
}
.timeline-section-label {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.6px;
  color: var(--text-muted);
  padding: 4px 0 2px;
}
.label-done {
  font-weight: 400;
  color: var(--success);
  font-size: 10px;
  text-transform: none;
}

.history-loader {
  align-self: center;
  color: var(--text-muted);
  font-size: 11px;
  padding: 4px 8px;
}

/* ── 轮次分隔线 ─────────────────────────────────────────── */
.round-separator {
  height: 1px;
  background: var(--border-color);
  margin: 6px 0 4px;
  opacity: 0.5;
}

/* ── 卡片通用 ───────────────────────────────────────────── */
.timeline-card {
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--border-color);
  background: var(--bg-surface);
  font-size: 12px;
}
.card-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 10px;
  flex-wrap: wrap;
}
.card-header.clickable { cursor: pointer; }
.card-header.clickable:hover { background: rgba(255,255,255,0.04); }
.phase-icon { font-size: 14px; flex-shrink: 0; }
.card-title { font-weight: 600; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.card-time  { font-size: 10px; color: var(--text-muted); flex-shrink: 0; }
.toggle-btn { font-size: 10px; color: var(--text-muted); flex-shrink: 0; }
.card-badge {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: 600;
  flex-shrink: 0;
  background: var(--bg-tertiary);
  color: var(--text-muted);
}
.card-body {
  padding: 8px 10px;
  border-top: 1px solid var(--border-color);
  background: var(--bg-tertiary);
}
.card-inline-preview {
  padding: 0 10px 7px;
  color: var(--text-muted);
  font-size: 11px;
  font-style: italic;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 颜色主题 */
.card-plan     { border-color: rgba(137,220,235,0.3); }
.card-plan .card-header { background: rgba(137,220,235,0.06); }
.card-plan .card-title  { color: var(--info); }

.card-planner  { border-color: rgba(137,220,235,0.2); }
.card-planner .card-title { color: var(--info); }

.card-act      { border-color: rgba(249,226,175,0.3); }
.card-act .card-header { background: rgba(249,226,175,0.05); }
.tool-name     { color: var(--warning); }
.act-badge     { background: rgba(249,226,175,0.15); color: var(--warning); }

.card-observe  { border-color: rgba(137,220,235,0.2); }
.card-observe.card-error { border-color: rgba(243,139,168,0.3); }
.card-error .card-header { background: rgba(243,139,168,0.05); }

.badge-ok      { background: rgba(166,227,161,0.15); color: var(--success); }
.badge-error   { background: rgba(243,139,168,0.15); color: var(--danger); }
.badge-repair  { background: rgba(250,179,135,0.15); color: #fab387; }

.card-finish   { border-color: rgba(166,227,161,0.3); }
.card-finish .card-header { background: rgba(166,227,161,0.05); }
.card-finish .card-title  { color: var(--success); }

.card-check    { border-color: var(--border-color); }
.check-reason  { font-size: 11px; color: var(--text-muted); flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.card-repair   { border-color: rgba(250,179,135,0.3); }
.card-repair .card-header { background: rgba(250,179,135,0.05); }
.card-repair .card-title  { color: #fab387; }

.card-cancelled { border-color: rgba(243,139,168,0.3); }
.card-cancelled .card-header { background: rgba(243,139,168,0.05); }
.card-cancelled .card-title  { color: var(--danger); }

/* ── 计划步骤 ───────────────────────────────────────────── */
.plan-steps {
  padding: 6px 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  border-top: 1px solid rgba(137,220,235,0.15);
}
.plan-step {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 5px 6px;
  border-radius: 5px;
  font-size: 12px;
  line-height: 1.4;
}
.plan-step.done    { opacity: 0.55; }
.plan-step.current { background: rgba(137,180,250,0.08); }
.step-icon { font-size: 12px; flex-shrink: 0; margin-top: 1px; color: var(--text-muted); }
.plan-step.done .step-icon    { color: var(--success); }
.plan-step.current .step-icon { color: var(--accent); }
.step-text { flex: 1; }

/* ── reason 分隔线 ──────────────────────────────────────── */
.step-divider {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 2px 0;
}
.divider-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--accent);
  flex-shrink: 0;
  margin-left: -16px;
}
.divider-label {
  font-size: 11px;
  color: var(--accent);
  font-weight: 600;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.divider-time {
  font-size: 10px;
  color: var(--text-muted);
  flex-shrink: 0;
}

/* ── 内容区块 ───────────────────────────────────────────── */
.code-block {
  margin: 0;
  font-family: ui-monospace, monospace;
  font-size: 11px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
  color: var(--text-secondary);
  max-height: 200px;
  overflow-y: auto;
}
.args-label { font-size: 10px; color: var(--text-muted); margin-bottom: 4px; }
.command-result-label {
  margin-top: 10px;
}
.command-attached-result {
  padding-top: 8px;
  border-top: 1px solid rgba(249,226,175,0.16);
}
.command-attached-result.result-error {
  color: var(--danger);
}
.observe-output {
  font-size: 11px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--text-secondary);
  max-height: 240px;
  overflow-y: auto;
}
.finish-text, .repair-text {
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}

/* ── 运行中动画 ─────────────────────────────────────────── */
.running-indicator {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 4px;
  color: var(--text-muted);
  font-size: 12px;
}
.running-text { margin-left: 4px; }
.dot {
  width: 7px; height: 7px;
  border-radius: 50%;
  background: var(--accent);
  animation: bounce 1.4s ease-in-out infinite;
}
.dot:nth-child(2) { animation-delay: 0.2s; }
.dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.35; }
  30%           { transform: translateY(-5px); opacity: 1; }
}

/* ── 输入区 ─────────────────────────────────────────────── */
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
.chat-input:disabled { opacity: 0.4; }
.send-btn { flex-shrink: 0; height: 40px; }

/* ── Markdown 渲染 ──────────────────────────────────────── */
.md-content {
  white-space: normal;
}
.md-content :deep(p)          { margin: 0 0 4px; line-height: 1.45; }
.md-content :deep(p:last-child) { margin-bottom: 0; }
.md-content :deep(h1),
.md-content :deep(h2),
.md-content :deep(h3),
.md-content :deep(h4)         { margin: 8px 0 4px; font-weight: 700; line-height: 1.25; color: var(--text-secondary); }
.md-content :deep(h1)         { font-size: 1.2em; }
.md-content :deep(h2)         { font-size: 1.1em; }
.md-content :deep(h3)         { font-size: 1em; }
.md-content :deep(ul),
.md-content :deep(ol)         { margin: 3px 0 5px; padding-left: 1.25em; }
.md-content :deep(li)         { margin: 1px 0; line-height: 1.4; }
.md-content :deep(strong)     { font-weight: 700; color: var(--text-secondary); }
.md-content :deep(em)         { font-style: italic; color: var(--text-muted); }
.md-content :deep(code) {
  font-family: ui-monospace, monospace;
  font-size: 0.88em;
  padding: 1px 5px;
  border-radius: 4px;
  background: var(--bg-surface);
  color: var(--accent);
}
.md-content :deep(pre) {
  margin: 5px 0;
  padding: 8px 10px;
  border-radius: 6px;
  background: var(--bg-surface);
  overflow-x: auto;
  border: 1px solid var(--border-color);
}
.md-content :deep(pre code) {
  padding: 0;
  background: none;
  color: var(--text-secondary);
  font-size: 0.87em;
  line-height: 1.4;
}
.md-content :deep(blockquote) {
  margin: 5px 0;
  padding: 5px 10px;
  border-left: 3px solid var(--accent);
  background: rgba(137,180,250,0.05);
  color: var(--text-muted);
  border-radius: 0 4px 4px 0;
}
.md-content :deep(hr) {
  border: none;
  border-top: 1px solid var(--border-color);
  margin: 7px 0;
}
.md-content :deep(a) {
  color: var(--accent);
  text-decoration: underline;
  text-underline-offset: 2px;
}
.md-content :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 5px 0;
  font-size: 0.9em;
}
.md-content :deep(th),
.md-content :deep(td) {
  padding: 4px 8px;
  border: 1px solid var(--border-color);
  text-align: left;
}
.md-content :deep(th) {
  background: var(--bg-surface);
  font-weight: 600;
}
</style>
