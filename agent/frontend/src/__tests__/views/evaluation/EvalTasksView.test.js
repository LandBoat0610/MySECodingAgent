/**
 * views/evaluation/EvalTasksView.test.js
 * 测试评测任务管理视图：自动刷新轮询、UI 指示器、组件渲染
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { nextTick } from 'vue'
import EvalTasksView from '../../../views/evaluation/EvalTasksView.vue'
import { useEvaluationStore } from '../../../stores/evaluation.js'
import { useAgentConfigStore } from '../../../stores/agentConfig.js'

// ---- Mock stores (vi.mock hoisted, use inline factories) ----
let mockEval
let mockCfg

vi.mock('../../../stores/evaluation.js', () => ({
    useEvaluationStore: vi.fn(() => mockEval)
}))

vi.mock('../../../stores/agentConfig.js', () => ({
    useAgentConfigStore: vi.fn(() => mockCfg)
}))

vi.mock('../../../components/status/index.js', () => ({
    EmptyState: { name: 'EmptyState', template: '<div class="empty-state"><span class="empty-title">{{ title }}</span></div>', props: ['icon', 'title', 'desc'] },
    ErrorBanner: { name: 'ErrorBanner', template: '<div v-if="message" class="error-banner"><span class="error-text">{{ message }}</span></div>', props: ['message', 'dismissible'], emits: ['dismiss'] },
    LoadingSpinner: { name: 'LoadingSpinner', template: '<div class="loading-spinner" />', props: ['text'] }
}))

// fake timers must be before any async code
vi.useFakeTimers()

function makeEvalStore(overrides = {}) {
    return {
        datasets: [],
        tasks: [],
        loading: false,
        error: null,
        loadAll: vi.fn().mockResolvedValue(undefined),
        loadTasks: vi.fn().mockResolvedValue(undefined),
        loadDatasets: vi.fn().mockResolvedValue(undefined),
        clearError: vi.fn(),
        uploadDataset: vi.fn(),
        createDatasetFromJson: vi.fn(),
        removeDataset: vi.fn(),
        addTask: vi.fn(),
        removeTask: vi.fn(),
        runTask: vi.fn(),
        stopTask: vi.fn(),
        fetchResults: vi.fn(),
        ...overrides
    }
}

function makeCfgStore(overrides = {}) {
    return {
        model: 'gpt-4o-mini',
        versionLabel: 'v1',
        loading: false,
        error: null,
        load: vi.fn().mockResolvedValue(undefined),
        save: vi.fn().mockResolvedValue(undefined),
        ...overrides
    }
}

function mountView() {
    return mount(EvalTasksView, {
        global: {
            stubs: {
                RouterLink: { template: '<a><slot/></a>' }
            }
        }
    })
}

async function flushTimers(ms = 0) {
    await vi.advanceTimersByTimeAsync(ms)
    await nextTick()
}

describe('EvalTasksView.vue', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        vi.clearAllTimers()
        mockEval = makeEvalStore()
        mockCfg = makeCfgStore()
        const pinia = createPinia()
        setActivePinia(pinia)
    })

    afterEach(() => {
        vi.clearAllTimers()
    })

    // ============ 渲染 ============
    describe('rendering', () => {
        it('should render page sections', () => {
            const wrapper = mountView()
            expect(wrapper.find('.eval-page').exists()).toBe(true)
            expect(wrapper.text()).toContain('Agent 版本配置')
            expect(wrapper.text()).toContain('代码测试集')
            expect(wrapper.text()).toContain('新建评测任务')
            expect(wrapper.text()).toContain('评测任务列表')
        })

        it('should show empty state when no datasets', () => {
            const wrapper = mountView()
            expect(wrapper.find('.empty').exists()).toBe(true)
        })

        it('should show empty state when no tasks', () => {
            const wrapper = mountView()
            const emptyStates = wrapper.findAll('.empty')
            expect(emptyStates.length).toBeGreaterThanOrEqual(1)
        })

        it('should show polling indicator initially (polling is described in card-desc)', () => {
            const wrapper = mountView()
            expect(wrapper.text()).toContain('每 3 秒自动刷新')
        })
    })

    // ============ 自动刷新轮询 ============
    describe('auto-refresh polling', () => {
        it('should call loadAll on mount', async () => {
            mountView()
            await flushTimers()
            expect(mockEval.loadAll).toHaveBeenCalledTimes(1)
        })

        it('should call loadTasks when running tasks exist', async () => {
            mockEval = makeEvalStore({
                tasks: [{ id: 't1', name: 'Running', status: 'running', completed_items: 0, total_items: 5, passed_count: 0, failed_count: 0 }]
            })
            mountView()
            // onMounted -> loadAll -> startPoll, setInterval 首次回调在 3 秒后
            await flushTimers(3000)
            expect(mockEval.loadTasks).toHaveBeenCalled()
        })

        it('should NOT call loadTasks when no running tasks', async () => {
            mockEval = makeEvalStore({
                tasks: [{ id: 't1', name: 'Done', status: 'completed', completed_items: 5, total_items: 5, passed_count: 5, failed_count: 0 }]
            })
            mountView()
            await flushTimers()
            expect(mockEval.loadTasks).not.toHaveBeenCalled()
        })

        it('should show polling indicator when running tasks exist', async () => {
            mockEval = makeEvalStore({
                tasks: [{ id: 't1', name: 'Active', status: 'running', completed_items: 1, total_items: 5, passed_count: 0, failed_count: 0 }]
            })
            const wrapper = mountView()
            await flushTimers()
            // 轮询指示体现在任务状态 pill 和卡片描述中
            expect(wrapper.text()).toContain('每 3 秒自动刷新')
        })

        it('should poll every 3 seconds when running', async () => {
            mockEval = makeEvalStore({
                tasks: [{ id: 't1', name: 'Running', status: 'running', completed_items: 2, total_items: 5, passed_count: 1, failed_count: 0 }]
            })
            mountView()
            await flushTimers()
            // 清除立即检查带来的调用计数
            const baseCalls = mockEval.loadTasks.mock.calls.length
            mockEval.loadTasks.mockClear()

            await flushTimers(3000)
            expect(mockEval.loadTasks).toHaveBeenCalledTimes(1)
            mockEval.loadTasks.mockClear()

            await flushTimers(6000)
            expect(mockEval.loadTasks).toHaveBeenCalledTimes(2)
        })

        it('should stop calling loadTasks when all complete', async () => {
            mockEval = makeEvalStore({
                tasks: [{ id: 't1', name: 'Working', status: 'running', completed_items: 4, total_items: 5, passed_count: 3, failed_count: 0 }]
            })
            mountView()
            await flushTimers()
            mockEval.loadTasks.mockClear()

            // 第一轮: 有 running
            await flushTimers(3000)
            expect(mockEval.loadTasks).toHaveBeenCalledTimes(1)

            // 模拟任务完成
            mockEval.tasks = [{ id: 't1', name: 'Done', status: 'completed', completed_items: 5, total_items: 5, passed_count: 5, failed_count: 0 }]
            mockEval.loadTasks.mockClear()

            // 第二轮: 无 running，不再调用
            await flushTimers(3000)
            expect(mockEval.loadTasks).not.toHaveBeenCalled()
        })
    })

    // ============ 轮询生命周期 ============
    describe('poll lifecycle', () => {
        it('should clear interval on unmount', async () => {
            const clearSpy = vi.spyOn(global, 'clearInterval')
            const wrapper = mountView()
            await flushTimers()
            wrapper.unmount()
            expect(clearSpy).toHaveBeenCalled()
            clearSpy.mockRestore()
        })

        it('should show idle after tasks complete', async () => {
            mockEval = makeEvalStore({
                tasks: [{ id: 't1', name: 'Running', status: 'running', completed_items: 2, total_items: 5, passed_count: 1, failed_count: 0 }]
            })
            const wrapper = mountView()
            await flushTimers()
            expect(wrapper.text()).toContain('每 3 秒自动刷新')

            // 任务完成
            mockEval.tasks = [{ id: 't1', name: 'Done', status: 'completed', completed_items: 5, total_items: 5, passed_count: 5, failed_count: 0 }]
            await flushTimers(3000)
            // 轮询描述仍然存在
            expect(wrapper.text()).toContain('每 3 秒自动刷新')
        })
    })

    // ============ 轮询指示器状态切换 ============
    describe('poll indicator state', () => {
        it('should show idle when no running tasks', async () => {
            const wrapper = mountView()
            await flushTimers()
            // 轮询描述始终存在
            expect(wrapper.text()).toContain('每 3 秒自动刷新')
        })

        it('should switch to active when running tasks appear', async () => {
            mockEval = makeEvalStore({
                tasks: [{ id: 't1', name: 'New Run', status: 'running', completed_items: 0, total_items: 5, passed_count: 0, failed_count: 0 }]
            })
            const wrapper = mountView()
            await flushTimers(3000)
            expect(wrapper.text()).toContain('每 3 秒自动刷新')
            // 存在运行中的任务
            expect(wrapper.text()).toContain('running')
        })
    })
})
