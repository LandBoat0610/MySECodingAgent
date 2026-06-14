<template>
  <div class="eval-page">
    <section class="card">
      <h2 class="card-title">Agent 模型配置</h2>
      <p class="card-desc">创建评测任务时会快照当前模型 ID；评测线程会使用该模型快照进行推理。</p>
      <div v-if="cfg.error" class="banner-error">{{ cfg.error }}</div>
      <div class="form-grid single">
        <label class="field">
          <span>模型 ID</span>
          <input v-model="draftModel" type="text" placeholder="例如 gpt-4o-mini" />
        </label>
      </div>
      <div class="actions">
        <button class="btn btn-primary" :disabled="cfg.loading" @click="handleSaveConfig">
          {{ cfg.loading ? '保存中…' : '保存模型配置' }}
        </button>
        <button class="btn btn-ghost" type="button" :disabled="cfg.loading" @click="reloadConfig">重新加载</button>
      </div>
    </section>

    <section class="card">
      <h2 class="card-title">代码测试集</h2>
      <p class="card-desc">
        每条样本至少需要 <code>description</code>（或 <code>task</code>）字段；可选 <code>expected_output</code>、
        <code>test_cases[].input / expected</code>。下方可一键填入最小示例。
      </p>
      <details class="json-sample">
        <summary>最小可运行 JSON 示例（复制或填入粘贴框）</summary>
        <pre class="json-sample-pre">{{ sampleJsonPretty }}</pre>
        <div class="sample-actions">
          <button type="button" class="btn btn-sm btn-primary" @click="fillSampleIntoPaste">填入粘贴框</button>
          <button type="button" class="btn btn-sm btn-ghost" @click="copySampleJson">复制 JSON</button>
        </div>
      </details>
      <div v-if="ev.error" class="banner-error">
        {{ ev.error }}
        <button type="button" class="btn-icon-inline" @click="ev.clearError()">×</button>
      </div>
      <p v-if="toastOk" class="toast-ok">{{ toastOk }}</p>

      <div class="dataset-toolbar">
        <label class="field file-field">
          <span>上传文件</span>
          <input type="file" accept="application/json,.json" @change="onFile" />
        </label>
        <label class="field">
          <span>数据集显示名（可选）</span>
          <input v-model="uploadName" type="text" placeholder="覆盖 JSON 内 name" />
        </label>
        <button class="btn btn-primary" type="button" :disabled="!pickedFile || ev.loading" @click="doUpload">
          上传
        </button>
      </div>

      <div class="json-create">
        <h3 class="sub-title">或粘贴 JSON 创建</h3>
        <label class="field">
          <span>名称（可选）</span>
          <input v-model="jsonName" type="text" placeholder="数据集名称" />
        </label>
        <textarea v-model="jsonPaste" class="json-area" placeholder='{"name":"…","items":[{"description":"…"}]}' rows="10" />
        <div class="paste-actions">
          <button class="btn btn-ghost" type="button" :disabled="ev.loading" @click="doPasteCreate">解析并创建</button>
          <span class="tiny muted">创建成功后粘贴区会清空；名称可用上方输入框或 JSON 顶层 name。</span>
        </div>
      </div>

      <table class="task-table">
        <thead>
          <tr>
            <th>名称</th>
            <th>条数</th>
            <th>创建时间</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="d in ev.datasets" :key="d.id">
            <td>{{ d.name }}</td>
            <td>{{ d.item_count }}</td>
            <td class="muted">{{ formatTime(d.created_at) }}</td>
            <td class="row-actions">
              <button
                class="btn btn-sm btn-ghost danger"
                type="button"
                @click="confirmRemoveDataset(d)"
              >
                删除
              </button>
            </td>
          </tr>
        </tbody>
      </table>
      <label class="cascade-hint">
        <input v-model="datasetDeleteCascade" type="checkbox" />
        <span>删除数据集时，若仍存在非运行中的关联评测任务，则一并删除这些任务（运行中的请先点「取消」）</span>
      </label>
      <div v-if="ev.datasets.length === 0" class="empty">暂无数据集，请先上传或粘贴创建。</div>
    </section>

    <section class="card">
      <h2 class="card-title">新建评测任务</h2>
      <p class="card-desc">
        选择数据集与评测方法：<strong>面向结果</strong>侧重回溯最终答复与评分；
        <strong>面向过程</strong>在评分策略上更强调轨迹完整性；<strong>联合评估</strong>同时检查输出匹配与过程质量，两者均须通过。
        所有方法均持久化完整执行轨迹、Ragas/Judge 模糊指标与安全扫描结果。
      </p>
      <div class="form-grid">
        <label class="field">
          <span>任务名称</span>
          <input v-model="newTaskName" type="text" placeholder="例如 Sprint1 回归评测" />
        </label>
        <label class="field">
          <span>数据集</span>
          <select v-model="newTaskDatasetId">
            <option value="">请选择</option>
            <option v-for="d in ev.datasets" :key="d.id" :value="d.id">{{ d.name }}（{{ d.item_count }} 条）</option>
          </select>
        </label>
      </div>
      <div class="method-row">
        <span class="method-label">评测方法</span>
        <label class="radio"><input v-model="newEvalMethod" type="radio" value="result" /> 面向结果</label>
        <label class="radio"><input v-model="newEvalMethod" type="radio" value="process" /> 面向过程</label>
        <label class="radio"><input v-model="newEvalMethod" type="radio" value="combined" /> 联合评估（结果+过程）</label>
      </div>
      <button class="btn btn-primary" type="button" :disabled="!canCreateTask" @click="createTask">创建任务</button>
    </section>

    <section class="card">
      <h2 class="card-title">评测任务列表</h2>
      <p class="card-desc">启动后由后端依次调用与 IDE 相同的 LangGraph Agent 对每条数据推理；结果写入数据库。进行中列表每 1 秒自动刷新。</p>
      <table class="task-table wide">
        <thead>
          <tr>
            <th>任务</th>
            <th>数据集</th>
            <th>方法</th>
            <th>模型快照</th>
            <th>状态</th>
            <th>进度</th>
            <th>通过/未通过</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="t in ev.tasks" :key="t.id">
            <td>{{ t.name }}</td>
            <td>{{ t.dataset_name || t.dataset_id }}</td>
            <td>{{ methodLabel(t.eval_method) }}</td>
            <td class="mono muted">{{ t.agent_model_snapshot || '—' }}</td>
            <td><span :class="['pill', t.status]">{{ t.status }}</span></td>
            <td class="progress-cell">
              <div class="progress-line">
                <span class="muted">{{ t.completed_items }} / {{ t.total_items }}</span>
                <span v-if="taskIsBusy(t)" class="tiny">{{ taskPercent(t) }}%</span>
              </div>
              <div class="progress-track">
                <div class="progress-fill" :style="{ width: taskPercent(t) + '%' }"></div>
              </div>
              <div v-if="taskIsBusy(t)" class="current-item">
                <span class="phase-dot"></span>
                {{ phaseLabel(t.current_phase) }}
                <template v-if="Number(t.current_item_index) >= 0">
                  · #{{ Number(t.current_item_index) + 1 }}
                  <span v-if="t.current_item_key">({{ t.current_item_key }})</span>
                </template>
              </div>
              <div v-if="taskIsBusy(t) && t.current_item_description" class="current-desc">
                {{ snippet(t.current_item_description) }}
              </div>
            </td>
            <td>{{ t.passed_count }} / {{ t.failed_count }}</td>
            <td class="row-actions">
              <button
                v-if="taskCanStart(t)"
                class="btn btn-sm btn-ghost"
                type="button"
                @click="startRun(t.id)"
              >
                启动
              </button>
              <button
                v-else-if="taskIsBusy(t)"
                class="btn btn-sm btn-ghost"
                type="button"
                @click="cancelRun(t.id)"
              >
                取消
              </button>
              <button
                v-if="t.status === 'pending'"
                class="btn btn-sm btn-ghost"
                type="button"
                @click="openEdit(t)"
              >
                编辑
              </button>
              <button class="btn btn-sm btn-ghost" type="button" @click="openResults(t.id)">明细</button>
              <button
                class="btn btn-sm btn-ghost danger"
                type="button"
                :disabled="taskIsBusy(t)"
                @click="confirmRemoveTask(t)"
              >
                删除
              </button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="ev.tasks.length === 0" class="empty">暂无评测任务</div>
      <p v-if="taskErrBanner" class="banner-error">{{ taskErrBanner }}</p>
    </section>

    <!-- 编辑任务 Modal -->
    <div v-if="editOpen" class="modal-mask" @click.self="editOpen = false">
      <div class="modal modal-sm">
        <div class="modal-head">
          <h3>编辑任务配置</h3>
          <button type="button" class="btn-icon-inline" @click="editOpen = false">×</button>
        </div>
        <div class="modal-body">
          <p class="muted tiny">仅「待运行」状态的任务可修改名称与评测方法。</p>
          <div class="form-grid" style="margin-top:14px">
            <label class="field">
              <span>任务名称</span>
              <input v-model="editName" type="text" />
            </label>
            <label class="field">
              <span>评测方法</span>
              <select v-model="editMethod">
                <option value="result">面向结果</option>
                <option value="process">面向过程</option>
                <option value="combined">联合评估（结果+过程）</option>
              </select>
            </label>
          </div>
          <p v-if="editErr" class="banner-error">{{ editErr }}</p>
          <div class="actions" style="margin-top:14px">
            <button class="btn btn-primary" :disabled="editSaving" @click="doEditSave">
              {{ editSaving ? '保存中…' : '保存' }}
            </button>
            <button class="btn btn-ghost" @click="editOpen = false">取消</button>
          </div>
        </div>
      </div>
    </div>

    <!-- 结果明细 Modal -->
    <div v-if="resultsOpen" class="modal-mask" @click.self="resultsOpen = false">
      <div class="modal">
        <div class="modal-head">
          <h3>执行明细：{{ resultsTaskName }}</h3>
          <button type="button" class="btn-icon-inline" @click="resultsOpen = false">×</button>
        </div>
        <div v-if="resultsLoading" class="modal-body muted">加载中…</div>
        <div v-else class="modal-body scroll">
          <div v-if="currentResultsTask && taskIsBusy(currentResultsTask)" class="live-replay">
            <div class="live-head">
              <div>
                <h4>正在执行</h4>
                <p class="tiny muted">
                  {{ phaseLabel(currentResultsTask.current_phase) }}
                  <template v-if="Number(currentResultsTask.current_item_index) >= 0">
                    · 第 {{ Number(currentResultsTask.current_item_index) + 1 }} / {{ currentResultsTask.total_items }} 条
                  </template>
                  <template v-if="currentResultsTask.current_item_key">
                    · {{ currentResultsTask.current_item_key }}
                  </template>
                </p>
              </div>
              <span class="live-badge">实时</span>
            </div>
            <p v-if="currentResultsTask.current_item_description" class="live-desc">
              {{ currentResultsTask.current_item_description }}
            </p>
            <ol v-if="friendlyTrace(currentResultsTask.current_trace_json).length" class="trace-flow live-flow">
              <li
                v-for="(step, si) in friendlyTrace(currentResultsTask.current_trace_json)"
                :key="'live-st-' + si"
                class="trace-step"
              >
                <div class="step-meta">
                  <span class="phase-pill">{{ step.phaseLabel }}</span>
                  <span class="step-time">{{ step.time }}</span>
                  <span v-if="step.session_status" class="sess">{{ step.session_status }}</span>
                </div>
                <div class="step-title">{{ step.title }}</div>
                <div v-if="step.summary" class="step-body">{{ step.summary }}</div>
                <div v-if="step.detail" class="step-detail">{{ step.detail }}</div>
                <details v-if="step.rawDetail" class="raw-detail">
                  <summary>查看原始信息</summary>
                  <pre>{{ step.rawDetail }}</pre>
                </details>
              </li>
            </ol>
            <p v-else class="muted tiny">Agent 已开始排队，等待第一条执行轨迹。</p>
          </div>

          <table class="task-table compact">
            <thead>
              <tr>
                <th>#</th>
                <th>通过</th>
                <th>Token总量</th>
                <th>工具成功率</th>
                <th>耗时(s)</th>
                <th>推理质量</th>
                <th>安全等级</th>
                <th>摘要</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in resultRows" :key="r.id">
                <td>{{ r.item_index }}</td>
                <td>
                  <span :class="r.passed === true ? 'passed-ok' : r.passed === false ? 'passed-bad' : 'passed-na'">
                    {{ r.passed === true ? '✓' : r.passed === false ? '✗' : '—' }}
                  </span>
                </td>
                <td class="mono small">{{ rmTokens(r) }}</td>
                <td class="mono small">{{ rmToolRate(r) }}</td>
                <td class="mono small">{{ rmResponseTime(r) }}</td>
                <td class="mono small">{{ judgeRQ(r) }}</td>
                <td><span v-if="securityBlock(r)" :class="['band', securityBlock(r).risk_band]">{{ securityBlock(r).risk_band }}</span><span v-else class="muted">—</span></td>
                <td class="mono small">{{ snippet(r.final_answer) }}</td>
                <td class="row-actions tight">
                  <button type="button" class="btn btn-sm btn-ghost" @click="selectedReplay = r">回放</button>
                </td>
              </tr>
            </tbody>
          </table>

          <div v-if="selectedReplay" class="replay-detail">
            <div class="replay-head">
              <h4>条目 #{{ selectedReplay.item_index }} · 过程溯源与多维指标</h4>
              <button type="button" class="btn-icon-inline" title="关闭详情" @click="selectedReplay = null">×</button>
            </div>

            <!-- 显式指标卡片 -->
            <div class="metrics-row">
              <div class="mcard">
                <span class="mlabel">Token 总量</span>
                <strong class="mval">{{ rmTokens(selectedReplay) }}</strong>
              </div>
              <div class="mcard">
                <span class="mlabel">提示/补全</span>
                <strong class="mval mono small">{{ rmTokenDetail(selectedReplay) }}</strong>
              </div>
              <div class="mcard">
                <span class="mlabel">LLM 调用</span>
                <strong class="mval">{{ rmLlmCalls(selectedReplay) }}</strong>
              </div>
              <div class="mcard">
                <span class="mlabel">工具成功率</span>
                <strong class="mval">{{ rmToolRate(selectedReplay) }}</strong>
              </div>
              <div class="mcard">
                <span class="mlabel">平均工具延迟</span>
                <strong class="mval">{{ rmToolLatency(selectedReplay) }}</strong>
              </div>
              <div class="mcard">
                <span class="mlabel">总耗时</span>
                <strong class="mval">{{ rmResponseTime(selectedReplay) }}</strong>
              </div>
            </div>

            <!-- 模糊指标卡片 -->
            <div class="metrics-row" style="margin-top:10px">
              <div class="mcard">
                <span class="mlabel">答复相关性 (Ragas)</span>
                <strong class="mval">{{ ragasAR(selectedReplay) }}</strong>
              </div>
              <div class="mcard">
                <span class="mlabel">忠实度 (Ragas)</span>
                <strong class="mval">{{ ragasFF(selectedReplay) }}</strong>
              </div>
              <div class="mcard">
                <span class="mlabel">推理质量 (Judge)</span>
                <strong class="mval">{{ judgeRQ(selectedReplay) }}</strong>
              </div>
              <div class="mcard">
                <span class="mlabel">幻觉严重度 (Judge)</span>
                <strong class="mval">{{ judgeHS(selectedReplay) }}</strong>
              </div>
            </div>

            <div class="replay-columns" style="margin-top:14px">
              <div class="replay-col">
                <h5 class="sub-head">执行步骤</h5>
                <p class="tiny muted">默认只展示每一步正在做什么、产生了什么结果；需要排查时可展开查看原始信息。</p>
                <ol class="trace-flow">
                  <li v-for="(step, si) in friendlyTrace(selectedReplay.trace_json)" :key="'st-' + si" class="trace-step">
                    <div class="step-meta">
                      <span class="phase-pill">{{ step.phaseLabel }}</span>
                      <span class="step-time">{{ step.time }}</span>
                      <span v-if="step.session_status" class="sess">{{ step.session_status }}</span>
                    </div>
                    <div class="step-title">{{ step.title }}</div>
                    <div v-if="step.summary" class="step-body">{{ step.summary }}</div>
                    <div v-if="step.detail" class="step-detail">{{ step.detail }}</div>
                    <details v-if="step.rawDetail" class="raw-detail">
                      <summary>查看原始信息</summary>
                      <pre>{{ step.rawDetail }}</pre>
                    </details>
                  </li>
                </ol>
                <p v-if="!normalizedTrace(selectedReplay.trace_json).length" class="muted tiny">暂无轨迹数据。</p>
              </div>

              <div class="replay-col">
                <h5 class="sub-head">安全评估（启发式）</h5>
                <div v-if="securityBlock(selectedReplay)" class="sec-card">
                  <div class="sec-row">
                    <span>风险分</span>
                    <strong>{{ securityBlock(selectedReplay).risk_score }} / 10</strong>
                  </div>
                  <div class="sec-row">
                    <span>等级</span>
                    <span :class="['band', securityBlock(selectedReplay).risk_band]">
                      {{ securityBlock(selectedReplay).risk_band }}
                    </span>
                  </div>
                  <p class="sec-summary">{{ securityBlock(selectedReplay).summary }}</p>
                  <ul v-if="securityBlock(selectedReplay).flags?.length" class="flag-list">
                    <li v-for="(f, fi) in securityBlock(selectedReplay).flags" :key="'f-' + fi">
                      <span class="fcat">{{ f.category }}</span>
                      <code>{{ f.id }}</code>
                    </li>
                  </ul>
                </div>
                <p v-else class="muted tiny">无安全扫描结果（旧数据或未写入）。重新运行评测任务后可见。</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useAgentConfigStore } from '../../stores/agentConfig.js'
import { useEvaluationStore } from '../../stores/evaluation.js'

const cfg = useAgentConfigStore()
const ev = useEvaluationStore()

const SAMPLE_DATASET_DOC = {
  name: '端到端演示数据集',
  items: [
    {
      id: 'demo-q1',
      description:
        '请只用一行回答：17 加 25 等于多少？只输出数字，不要其它文字。',
      expected_output: '42',
      test_cases: []
    }
  ]
}
const sampleJsonPretty = JSON.stringify(SAMPLE_DATASET_DOC, null, 2)

const datasetDeleteCascade = ref(false)
const toastOk = ref('')
let toastTimer = null
function flashOk(msg) {
  toastOk.value = msg
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    toastOk.value = ''
    toastTimer = null
  }, 2600)
}

function fillSampleIntoPaste() {
  taskErrBanner.value = null
  jsonPaste.value = sampleJsonPretty
  jsonName.value = SAMPLE_DATASET_DOC.name
  flashOk('已填入粘贴框，可点「解析并创建」')
}

async function copySampleJson() {
  taskErrBanner.value = null
  try {
    await navigator.clipboard.writeText(sampleJsonPretty)
    flashOk('JSON 已复制到剪贴板')
  } catch {
    taskErrBanner.value = '复制失败：请手动选中上方 JSON 全文复制'
  }
}

async function confirmRemoveDataset(d) {
  taskErrBanner.value = null
  const cascade = datasetDeleteCascade.value
  const msg = cascade
    ? `确定删除数据集「${d.name}」并删除其关联的全部评测任务（不含运行中的任务）？`
    : `确定删除数据集「${d.name}」？若仍有关联评测任务将拒绝删除（可勾选下方选项后重试）。`
  if (!confirm(msg)) return
  try {
    await ev.removeDataset(d.id, { cascade })
    flashOk('数据集已删除')
  } catch {
    taskErrBanner.value = ev.error || '删除失败'
  }
}

async function confirmRemoveTask(t) {
  taskErrBanner.value = null
  if (!confirm(`确定删除评测任务「${t.name}」及其全部明细结果？不可恢复。`)) return
  try {
    await ev.removeTask(t.id)
    flashOk('评测任务已删除')
  } catch {
    taskErrBanner.value = ev.error || '删除失败'
  }
}

const draftModel = ref('')
const uploadName = ref('')
const pickedFile = ref(null)
const jsonName = ref('')
const jsonPaste = ref('')

const newTaskName = ref('')
const newTaskDatasetId = ref('')
const newEvalMethod = ref('result')

// 编辑任务
const editOpen = ref(false)
const editTaskId = ref('')
const editName = ref('')
const editMethod = ref('result')
const editSaving = ref(false)
const editErr = ref('')

const resultsOpen = ref(false)
const resultsTaskId = ref('')
const resultsTaskName = ref('')
const resultRows = ref([])
const resultsLoading = ref(false)
const taskErrBanner = ref(null)
const selectedReplay = ref(null)

let pollTimer = null

watch(resultsOpen, open => {
  if (!open) selectedReplay.value = null
})

watch(
  () => cfg.model,
  () => {
    draftModel.value = cfg.model
  },
  { immediate: true }
)

const canCreateTask = computed(
  () => newTaskName.value.trim() && newTaskDatasetId.value && !ev.loading
)

const currentResultsTask = computed(() =>
  ev.tasks.find(t => t.id === resultsTaskId.value) || null
)

function methodLabel(m) {
  if (m === 'process') return '面向过程'
  if (m === 'combined') return '联合评估'
  return '面向结果'
}

function phaseLabel(phase) {
  const map = {
    queued: '排队中',
    running_agent: 'Agent 执行中',
    scoring: '结果评分中',
    item_completed: '单条完成',
    completed: '已完成',
    cancelled: '已取消',
    failed: '失败'
  }
  return map[phase] || phase || '准备中'
}

function taskPercent(t) {
  const total = Number(t.total_items) || 0
  if (!total) return 0
  return Math.min(100, Math.round((Number(t.completed_items) || 0) / total * 100))
}

/** 评测线程仍在收尾（含取消中） */
function taskIsBusy(t) {
  return t.status === 'running' || t.status === 'cancelling'
}

function taskCanStart(t) {
  return ['pending', 'completed', 'failed', 'cancelled'].includes(t.status)
}

function formatTime(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString()
}

function snippet(text) {
  const s = text || ''
  return s.length > 160 ? s.slice(0, 160) + '…' : s
}

function normalizedTrace(raw) {
  if (!raw) return []
  return Array.isArray(raw) ? raw : []
}

function friendlyTrace(raw) {
  return normalizedTrace(raw).map((step, index) => friendlyStep(step, index))
}

function friendlyStep(step, index) {
  const phase = step?.phase || ''
  const content = String(step?.content || '').trim()
  const meta = step?.meta && typeof step.meta === 'object' ? step.meta : {}
  const outline = step?.state_outline && typeof step.state_outline === 'object' ? step.state_outline : {}
  const parsed = parseMaybeJson(content)
  const title = stepTitle(phase, content, meta, parsed, index)
  const summary = stepSummary(phase, content, meta, parsed)
  const detail = stepDetail(step, parsed)
  const rawDetail = rawStepDetail(step)
  return {
    ...step,
    phaseLabel: tracePhaseLabel(phase),
    title,
    summary,
    detail,
    rawDetail,
    state_outline: outline
  }
}

function tracePhaseLabel(phase) {
  const map = {
    plan: '制定计划',
    planner: '制定计划',
    reason: '思考',
    act: '调用工具',
    observe: '工具结果',
    verify: '验证',
    repair: '修复',
    finalize: '总结',
    done: '完成',
    error: '异常',
    tool_approval: '等待确认',
    continue_approval: '等待继续'
  }
  return map[phase] || phaseLabel(phase) || '步骤'
}

function stepTitle(phase, content, meta, parsed, index) {
  const toolName = meta.tool || parsed?.tool || extractToolName(content)
  if (phase === 'act' && toolName) return `调用工具：${toolDisplayName(toolName)}`
  if (phase === 'observe' && toolName) return `工具返回：${toolDisplayName(toolName)}`
  if (phase === 'plan' || phase === 'planner') return '生成执行计划'
  if (phase === 'verify') return '检查执行结果'
  if (phase === 'repair') return '尝试修复问题'
  if (phase === 'finalize' || phase === 'done') return '整理最终答复'
  if (phase === 'error') return '执行出现异常'
  if (phase === 'tool_approval') return '等待用户确认命令'
  if (phase === 'continue_approval') return '等待用户确认继续'
  const first = firstMeaningfulLine(content)
  return first ? clampText(first, 42) : `步骤 ${index + 1}`
}

function stepSummary(phase, content, meta, parsed) {
  if (!content && !Object.keys(meta).length) return ''
  if (phase === 'act') {
    return summarizeToolCall(content, meta, parsed)
  }
  if (phase === 'observe') {
    return summarizeToolResult(content, meta, parsed)
  }
  if (phase === 'plan' || phase === 'planner') {
    const items = planItems(content)
    if (items.length) return items.slice(0, 4).join('；')
  }
  if (phase === 'finalize' || phase === 'done') {
    return clampText(stripMarkdownNoise(content), 180)
  }
  return clampText(stripMarkdownNoise(content), 180)
}

function stepDetail(step, parsed) {
  const meta = step?.meta || {}
  const bits = []
  if (meta.tool && meta.ok != null) bits.push(meta.ok ? '工具执行成功' : '工具执行失败')
  if (meta.elapsed_ms != null) bits.push(`耗时 ${Math.round(meta.elapsed_ms)} ms`)
  if (meta.tokens_total != null) bits.push(`Token ${Number(meta.tokens_total).toLocaleString()}`)
  if (parsed?.exit_code != null) bits.push(`退出码 ${parsed.exit_code}`)
  if (parsed?.summary) bits.push(clampText(String(parsed.summary), 80))
  return bits.join(' · ')
}

function rawStepDetail(step) {
  const raw = {}
  if (step?.content) raw.content = step.content
  if (step?.state_outline && Object.keys(step.state_outline).length) raw.state_outline = step.state_outline
  if (step?.meta && Object.keys(step.meta).length) raw.meta = step.meta
  if (!Object.keys(raw).length) return ''
  const text = formatJson(raw)
  return text.length > 6000 ? text.slice(0, 6000) + '\n... 已截断' : text
}

function summarizeToolCall(content, meta, parsed) {
  const tool = meta.tool || parsed?.tool || extractToolName(content)
  const args = parsed?.arguments || parsed?.args || meta.args || meta.arguments || {}
  if (tool === 'execute_bash') {
    const cmd = args.cmd || args.command || extractJsonField(content, 'cmd') || extractJsonField(content, 'command')
    return cmd ? `准备执行命令：${clampText(cmd, 120)}` : '准备执行一条命令'
  }
  if (tool === 'write_file') {
    const path = args.path || extractJsonField(content, 'path')
    return path ? `准备写入文件：${path}` : '准备写入文件'
  }
  if (tool === 'read_file' || tool === 'read_file_range') {
    const path = args.path || extractJsonField(content, 'path')
    return path ? `读取文件：${path}` : '读取文件内容'
  }
  if (tool === 'apply_patch') return '准备应用代码补丁'
  if (tool === 'run_tests') return '准备运行测试'
  if (tool === 'run_lint') return '准备运行代码检查'
  if (tool === 'list_files') return '查看工作区文件结构'
  if (tool === 'search_code') return `搜索代码：${clampText(args.query || args.pattern || '', 80) || '按关键词检索'}`
  if (tool === 'rag_search') return `检索知识库：${clampText(args.query || '', 100) || '查找相关资料'}`
  return tool ? `准备使用 ${toolDisplayName(tool)}` : clampText(stripMarkdownNoise(content), 140)
}

function summarizeToolResult(content, meta, parsed) {
  const tool = meta.tool || parsed?.tool || extractToolName(content)
  const ok = meta.ok ?? parsed?.ok ?? parsed?.success
  const status = ok === false ? '失败' : ok === true ? '成功' : ''
  const output = parsed?.output || parsed?.stdout || parsed?.result || parsed?.content || content
  if (tool === 'execute_bash') {
    const exit = parsed?.exit_code != null ? `，退出码 ${parsed.exit_code}` : ''
    return `命令执行${status || '完成'}${exit}。${clampText(cleanOutput(output), 140)}`
  }
  if (tool === 'run_tests') return `测试运行${status || '完成'}。${clampText(cleanOutput(output), 140)}`
  if (tool === 'write_file') return `文件写入${status || '完成'}。${clampText(cleanOutput(output), 120)}`
  if (tool === 'read_file' || tool === 'read_file_range') return `文件读取完成。${clampText(cleanOutput(output), 120)}`
  if (tool === 'list_files') return `目录查看完成。${clampText(cleanOutput(output), 120)}`
  if (tool === 'rag_search') return `知识库检索完成。${clampText(cleanOutput(output), 140)}`
  return `${status ? `执行${status}。` : ''}${clampText(cleanOutput(output), 160)}`
}

function toolDisplayName(tool) {
  const names = {
    execute_bash: '执行命令',
    list_files: '列出文件',
    read_file: '读取文件',
    read_file_range: '分段读取文件',
    write_file: '写入文件',
    search_code: '搜索代码',
    web_search: '联网搜索',
    fetch_url: '抓取网页',
    apply_patch: '应用补丁',
    get_git_diff: '查看 Git 差异',
    run_tests: '运行测试',
    run_lint: '代码检查',
    rag_search: '知识库检索'
  }
  return names[tool] || tool
}

function parseMaybeJson(text) {
  if (!text || typeof text !== 'string') return null
  const trimmed = text.trim()
  if (!trimmed.startsWith('{') && !trimmed.startsWith('[')) return null
  try {
    return JSON.parse(trimmed)
  } catch {
    return null
  }
}

function extractToolName(text) {
  const m = String(text || '').match(/(?:工具|tool|function)[:：\s`"]+([a-zA-Z_][\w-]*)/)
  return m?.[1] || ''
}

function extractJsonField(text, field) {
  const re = new RegExp(`"${field}"\\s*:\\s*"([^"]+)"`)
  return String(text || '').match(re)?.[1] || ''
}

function planItems(text) {
  return String(text || '')
    .split('\n')
    .map(line => line.replace(/^\s*(?:[-*]|\d+[.)、])\s*/, '').trim())
    .filter(line => line && !line.startsWith('【') && line.length <= 100)
}

function firstMeaningfulLine(text) {
  return String(text || '')
    .split('\n')
    .map(line => line.trim())
    .find(line => line && !line.startsWith('{') && !line.startsWith('```')) || ''
}

function stripMarkdownNoise(text) {
  return String(text || '')
    .replace(/```[\s\S]*?```/g, '[代码片段已折叠]')
    .replace(/`([^`]{1,80})`/g, '$1')
    .replace(/\*\*/g, '')
    .trim()
}

function cleanOutput(text) {
  return stripMarkdownNoise(String(text || ''))
    .replace(/\s+/g, ' ')
    .trim()
}

function clampText(text, max = 160) {
  const s = String(text || '').trim()
  return s.length > max ? s.slice(0, max) + '…' : s
}

function formatJson(obj) {
  try {
    return JSON.stringify(obj, null, 2)
  } catch {
    return String(obj)
  }
}

function securityBlock(row) {
  const s = row?.security_json
  if (!s || typeof s !== 'object') return null
  if (s.risk_score == null && !(s.flags && s.flags.length)) return null
  return s
}

function startPoll() {
  stopPoll()
  pollTimer = setInterval(async () => {
    if (ev.tasks.some(t => t.status === 'running' || t.status === 'cancelling')) {
      taskErrBanner.value = null
      await ev.loadTasks()
      if (resultsOpen.value && resultsTaskId.value) {
        try {
          resultRows.value = await ev.fetchResults(resultsTaskId.value)
        } catch {
          // Keep the current rows visible if a transient refresh fails.
        }
      }
    }
  }, 1000)
}

function stopPoll() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

onMounted(async () => {
  await Promise.all([ev.loadAll(), cfg.load()])
  startPoll()
})

onUnmounted(() => {
  stopPoll()
  if (toastTimer) clearTimeout(toastTimer)
})

async function reloadConfig() {
  await cfg.load()
}

async function handleSaveConfig() {
  await cfg.save({
    model: draftModel.value.trim() || undefined
  })
}

function onFile(e) {
  const f = e.target.files?.[0]
  pickedFile.value = f || null
}

async function doUpload() {
  taskErrBanner.value = null
  if (!pickedFile.value) return
  try {
    await ev.uploadDataset(pickedFile.value, uploadName.value)
    pickedFile.value = null
    uploadName.value = ''
    flashOk('数据集已从文件导入')
  } catch (e) {
    taskErrBanner.value = ev.error || '上传失败'
  }
}

async function doPasteCreate() {
  taskErrBanner.value = null
  try {
    const parsed = JSON.parse(jsonPaste.value || '{}')
    const items = parsed.items
    if (!Array.isArray(items) || items.length === 0) {
      taskErrBanner.value = 'JSON 须包含非空 items 数组'
      return
    }
    const name = jsonName.value.trim() || parsed.name || ''
    await ev.createDatasetFromJson(name, items)
    jsonPaste.value = ''
    flashOk('数据集已创建，可在下方「新建评测任务」中选择')
  } catch (e) {
    taskErrBanner.value = '解析 JSON 失败或服务器拒绝'
  }
}

async function createTask() {
  taskErrBanner.value = null
  try {
    await ev.addTask({
      name: newTaskName.value.trim(),
      dataset_id: newTaskDatasetId.value,
      eval_method: newEvalMethod.value
    })
    newTaskName.value = ''
    flashOk('评测任务已创建，可在列表中「启动」')
  } catch (e) {
    taskErrBanner.value = ev.error || '创建失败'
  }
}

async function startRun(id) {
  taskErrBanner.value = null
  try {
    await ev.runTask(id)
    startPoll()
  } catch (e) {
    taskErrBanner.value = ev.error || '启动失败'
  }
}

async function cancelRun(id) {
  taskErrBanner.value = null
  try {
    await ev.stopTask(id)
    flashOk('已请求取消，后台收尾完成后状态将变为 cancelled')
    startPoll()
  } catch (e) {
    taskErrBanner.value = ev.error || '取消失败'
  }
}

async function openResults(taskId) {
  resultsTaskId.value = taskId
  const t = ev.tasks.find(x => x.id === taskId)
  resultsTaskName.value = t?.name || taskId
  resultsOpen.value = true
  selectedReplay.value = null
  resultsLoading.value = true
  resultRows.value = []
  try {
    resultRows.value = await ev.fetchResults(taskId)
  } catch (e) {
    resultRows.value = []
  } finally {
    resultsLoading.value = false
  }
}

function openEdit(t) {
  editTaskId.value = t.id
  editName.value = t.name
  editMethod.value = t.eval_method || 'result'
  editErr.value = ''
  editOpen.value = true
}

async function doEditSave() {
  editErr.value = ''
  editSaving.value = true
  try {
    await ev.editTask(editTaskId.value, {
      name: editName.value.trim() || undefined,
      eval_method: editMethod.value
    })
    editOpen.value = false
    flashOk('任务配置已更新')
  } catch (e) {
    editErr.value = ev.error || e?.response?.data?.detail || '保存失败'
  } finally {
    editSaving.value = false
  }
}

// 运行时指标辅助函数
function _rm(r) {
  return r?.runtime_metrics_json || {}
}

function rmTokens(r) {
  const v = _rm(r).tokens_total
  return v != null ? v.toLocaleString() : '—'
}

function rmTokenDetail(r) {
  const rm = _rm(r)
  const p = rm.tokens_prompt
  const c = rm.tokens_completion
  if (p == null && c == null) return '—'
  return `${(p || 0).toLocaleString()} / ${(c || 0).toLocaleString()}`
}

function rmLlmCalls(r) {
  const v = _rm(r).llm_calls
  return v != null ? v : '—'
}

function rmToolRate(r) {
  const v = _rm(r).tool_success_rate
  if (v == null) return '—'
  return (v * 100).toFixed(0) + '%'
}

function rmToolLatency(r) {
  const v = _rm(r).tool_avg_latency_ms
  if (v == null) return '—'
  return v.toFixed(0) + ' ms'
}

function rmResponseTime(r) {
  const sa = r?.started_at
  const fa = r?.finished_at
  if (!sa || !fa) return '—'
  try {
    const ms = new Date(fa) - new Date(sa)
    return (ms / 1000).toFixed(1) + ' s'
  } catch {
    return '—'
  }
}

function ragasAR(r) {
  const v = r?.ragas_json?.answer_relevancy
  return v != null ? v.toFixed(3) : '—'
}

function ragasFF(r) {
  const v = r?.ragas_json?.faithfulness
  return v != null ? v.toFixed(3) : '—'
}

function judgeRQ(r) {
  const v = r?.judge_json?.reasoning_quality
  return v != null ? v + '/10' : '—'
}

function judgeHS(r) {
  const v = r?.judge_json?.hallucination_severity
  return v != null ? v + '/10' : '—'
}
</script>

<style scoped>
.eval-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
  max-width: 1100px;
}

.card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 20px 22px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 8px;
}

.card-desc {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 16px;
  line-height: 1.55;
}

.card-desc code {
  font-size: 11px;
  color: var(--accent);
}

.sub-title {
  font-size: 13px;
  font-weight: 600;
  margin: 12px 0 8px;
}

.banner-error {
  background: color-mix(in srgb, var(--danger) 22%, transparent);
  color: var(--danger);
  padding: 10px 12px;
  border-radius: 8px;
  font-size: 13px;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.btn-icon-inline {
  background: transparent;
  color: inherit;
  font-size: 18px;
  line-height: 1;
  padding: 0 4px;
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}

.form-grid.single {
  grid-template-columns: minmax(260px, 560px);
}

@media (max-width: 720px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary);
}

.field input,
.field select,
.json-area {
  width: 100%;
}

.json-area {
  font-family: ui-monospace, monospace;
  font-size: 12px;
  margin-bottom: 8px;
}

.dataset-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: flex-end;
  margin-bottom: 16px;
}

.file-field input[type='file'] {
  font-size: 12px;
}

.json-create {
  margin-bottom: 18px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border-color);
}

.json-sample {
  margin-bottom: 16px;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  padding: 12px 14px;
  background: var(--bg-primary);
}

.json-sample summary {
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
}

.json-sample-pre {
  margin: 12px 0;
  padding: 12px;
  border-radius: 8px;
  background: var(--bg-tertiary);
  font-size: 11px;
  overflow: auto;
  max-height: 260px;
  line-height: 1.45;
}

.sample-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.paste-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin-top: 8px;
}

.toast-ok {
  font-size: 13px;
  color: var(--success);
  margin: 8px 0 4px;
}

.cascade-hint {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 12px;
  line-height: 1.45;
}

.cascade-hint input {
  margin-top: 3px;
}

.method-row {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}

.method-label {
  font-size: 12px;
  color: var(--text-muted);
}

.radio {
  font-size: 13px;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 6px;
}

.actions {
  display: flex;
  gap: 10px;
}

.task-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.task-table.wide {
  font-size: 12px;
}

.task-table.compact {
  font-size: 12px;
}

.task-table th,
.task-table td {
  text-align: left;
  padding: 10px 12px;
  border-bottom: 1px solid var(--border-color);
  vertical-align: top;
}

.task-table th {
  color: var(--text-muted);
  font-weight: 600;
  font-size: 11px;
  text-transform: uppercase;
}

.mono {
  font-family: ui-monospace, monospace;
}

.small {
  font-size: 11px;
}

.muted {
  color: var(--text-muted);
}

.progress-cell {
  min-width: 190px;
}

.progress-line {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
  margin-bottom: 5px;
}

.progress-track {
  height: 6px;
  border-radius: 999px;
  overflow: hidden;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--accent), var(--success));
  transition: width 180ms ease;
}

.current-item {
  margin-top: 6px;
  color: var(--text-secondary);
  font-size: 11px;
  line-height: 1.35;
}

.current-desc {
  max-width: 260px;
  margin-top: 3px;
  color: var(--text-muted);
  font-size: 11px;
  line-height: 1.35;
}

.phase-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  margin-right: 5px;
  border-radius: 999px;
  background: var(--warning);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--warning) 18%, transparent);
}

.live-replay {
  margin-bottom: 16px;
  padding: 14px;
  border: 1px solid color-mix(in srgb, var(--accent) 35%, var(--border-color));
  border-radius: 10px;
  background: color-mix(in srgb, var(--accent) 7%, var(--bg-primary));
}

.live-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 10px;
}

.live-head h4 {
  margin: 0 0 4px;
  font-size: 14px;
}

.live-badge {
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  color: var(--accent);
  background: color-mix(in srgb, var(--accent) 18%, transparent);
}

.live-desc {
  margin-bottom: 12px;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.45;
}

.live-flow {
  max-height: 360px;
  overflow: auto;
  padding-right: 6px;
}

.row-actions {
  display: flex;
  gap: 6px;
  justify-content: flex-end;
  flex-wrap: wrap;
}

.pill {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
}

.pill.pending {
  background: var(--bg-surface);
  color: var(--text-secondary);
}
.pill.running {
  background: color-mix(in srgb, var(--warning) 35%, transparent);
  color: var(--warning);
}
.pill.cancelling {
  background: color-mix(in srgb, var(--accent) 28%, transparent);
  color: var(--accent);
}
.pill.completed {
  background: color-mix(in srgb, var(--success) 35%, transparent);
  color: var(--success);
}
.pill.failed {
  background: color-mix(in srgb, var(--danger) 35%, transparent);
  color: var(--danger);
}
.pill.cancelled {
  background: var(--bg-surface);
  color: var(--text-muted);
}

.empty {
  text-align: center;
  color: var(--text-muted);
  padding: 16px;
  font-size: 13px;
}

.btn {
  padding: 8px 16px;
  border-radius: 8px;
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

.btn-primary:hover:not(:disabled) {
  background: var(--accent-hover);
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-ghost {
  background: var(--bg-surface);
  color: var(--text-secondary);
}

.btn-ghost:hover {
  color: var(--text-primary);
}

.btn-ghost.danger:hover {
  color: var(--danger);
}

.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
  padding: 20px;
}

.modal {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  max-width: 1040px;
  width: 100%;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
}

.modal-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border-color);
}

.modal-head h3 {
  font-size: 15px;
}

.modal-body {
  padding: 12px 16px 16px;
}

.modal-body.scroll {
  overflow: auto;
}

.row-actions.tight {
  justify-content: flex-start;
}

.replay-detail {
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid var(--border-color);
}

.replay-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.replay-head h4 {
  font-size: 14px;
  font-weight: 600;
}

.replay-columns {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px;
}

@media (max-width: 800px) {
  .replay-columns {
    grid-template-columns: 1fr;
  }
}

.sub-head {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 6px;
}

.tiny {
  font-size: 11px;
  line-height: 1.45;
}

.trace-flow {
  list-style: decimal;
  padding-left: 1.25rem;
  margin: 8px 0 0;
  font-size: 12px;
}

.trace-flow li {
  margin-bottom: 12px;
  padding-left: 4px;
}

.trace-step {
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 10px 12px;
}

.step-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 4px;
}

.phase-pill {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  padding: 2px 8px;
  border-radius: 6px;
  background: var(--bg-tertiary);
  color: var(--accent);
}

.step-time {
  font-family: ui-monospace, monospace;
  font-size: 10px;
  color: var(--text-muted);
}

.sess {
  font-size: 10px;
  color: var(--info);
}

.step-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 5px;
}

.outline {
  margin: 4px 0;
  padding: 8px;
  border-radius: 8px;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  font-size: 10px;
  overflow: auto;
  max-height: 140px;
}

.step-body {
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.55;
}

.step-detail {
  margin-top: 6px;
  color: var(--text-muted);
  font-size: 11px;
  line-height: 1.45;
}

.mini-meta {
  margin-top: 4px;
  font-size: 10px;
  font-family: ui-monospace, monospace;
  color: var(--text-muted);
}

.raw-detail {
  margin-top: 8px;
  color: var(--text-muted);
  font-size: 11px;
}

.raw-detail summary {
  cursor: pointer;
  user-select: none;
}

.raw-detail pre {
  margin: 8px 0 0;
  padding: 8px;
  border-radius: 8px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  overflow: auto;
  max-height: 220px;
  white-space: pre-wrap;
}

.sec-card {
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  padding: 12px;
  font-size: 12px;
}

.sec-row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}

.sec-summary {
  margin: 10px 0;
  line-height: 1.5;
  color: var(--text-secondary);
}

.band {
  text-transform: uppercase;
  font-size: 10px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 6px;
}

.band.low {
  background: color-mix(in srgb, var(--success) 28%, transparent);
  color: var(--success);
}

.band.medium {
  background: color-mix(in srgb, var(--warning) 28%, transparent);
  color: var(--warning);
}

.band.high {
  background: color-mix(in srgb, var(--danger) 28%, transparent);
  color: var(--danger);
}

.flag-list {
  list-style: none;
  padding: 0;
  margin: 8px 0 0;
  font-size: 11px;
}

.flag-list li {
  display: flex;
  gap: 8px;
  padding: 4px 0;
  border-bottom: 1px solid var(--border-color);
}

.fcat {
  color: var(--text-muted);
  min-width: 110px;
}

.modal-sm {
  max-width: 560px !important;
}

.metrics-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.mcard {
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 10px 14px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 120px;
  flex: 1;
}

.mlabel {
  font-size: 10px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.mval {
  font-size: 15px;
  color: var(--text-primary);
}

.passed-ok {
  color: var(--success);
  font-weight: 700;
}

.passed-bad {
  color: var(--danger);
  font-weight: 700;
}

.passed-na {
  color: var(--text-muted);
}
</style>
