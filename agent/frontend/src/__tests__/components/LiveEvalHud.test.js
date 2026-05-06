/**
 * components/LiveEvalHud.test.js
 * 测试实时评测 HUD 面板组件（mock store 用 reactive 确保模板响应式）
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { reactive } from 'vue'
import LiveEvalHud from '../../components/LiveEvalHud.vue'
import { useAgentStore } from '../../stores/agent.js'

vi.mock('../../stores/agent.js', () => ({
    useAgentStore: vi.fn()
}))

function createMockStore(overrides = {}) {
    return reactive({
        agentRunning: false,
        agentRunStartedAt: null,
        livePerf: {
            tokensTotal: 0,
            toolEventsCount: 0,
            toolSuccessRate: null,
            toolAvgLatencyMs: null,
        },
        traceLogs: [],
        ...overrides
    })
}

describe('LiveEvalHud.vue', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        const pinia = createPinia()
        setActivePinia(pinia)
    })

    afterEach(() => {
        vi.useRealTimers()
    })

    it('should render panel title', () => {
        useAgentStore.mockReturnValue(createMockStore())
        const wrapper = mount(LiveEvalHud)
        expect(wrapper.find('.panel-title').text()).toBe('实时评测')
    })

    it('should show dash for elapsed / token when idle', () => {
        useAgentStore.mockReturnValue(createMockStore())
        const wrapper = mount(LiveEvalHud)
        const text = wrapper.text()
        // 未启动时 Token 显示 —
        expect(text).toContain('—')
    })

    it('should display token count', () => {
        useAgentStore.mockReturnValue(createMockStore({
            livePerf: { tokensTotal: 500, toolEventsCount: 0, toolSuccessRate: null, toolAvgLatencyMs: null }
        }))
        const wrapper = mount(LiveEvalHud)
        expect(wrapper.text()).toContain('500')
    })

    it('should display trace step count', () => {
        useAgentStore.mockReturnValue(createMockStore({
            traceLogs: [{ phase: 'p1' }, { phase: 'p2' }, { phase: 'p3' }]
        }))
        const wrapper = mount(LiveEvalHud)
        expect(wrapper.text()).toContain('3')
    })

    it('should display tool call count', () => {
        useAgentStore.mockReturnValue(createMockStore({
            livePerf: { tokensTotal: 0, toolEventsCount: 7, toolSuccessRate: null, toolAvgLatencyMs: null }
        }))
        const wrapper = mount(LiveEvalHud)
        expect(wrapper.text()).toContain('7')
    })

    it('should display tool success rate when available', () => {
        useAgentStore.mockReturnValue(createMockStore({
            livePerf: { tokensTotal: 0, toolEventsCount: 10, toolSuccessRate: 0.85, toolAvgLatencyMs: null }
        }))
        const wrapper = mount(LiveEvalHud)
        expect(wrapper.text()).toContain('85%')
    })

    it('should display tool avg latency when available', () => {
        useAgentStore.mockReturnValue(createMockStore({
            livePerf: { tokensTotal: 0, toolEventsCount: 5, toolSuccessRate: null, toolAvgLatencyMs: 123.4 }
        }))
        const wrapper = mount(LiveEvalHud)
        expect(wrapper.text()).toContain('123.4 ms')
    })

    it('should toggle collapse on button click', async () => {
        useAgentStore.mockReturnValue(createMockStore())
        const wrapper = mount(LiveEvalHud)
        const btn = wrapper.find('.panel-toggle')

        expect(wrapper.find('.panel-body').exists()).toBe(true)

        await btn.trigger('click')
        expect(wrapper.find('.panel-body').exists()).toBe(false)
        expect(wrapper.find('.panel-chevron').text()).toBe('▸')

        await btn.trigger('click')
        expect(wrapper.find('.panel-body').exists()).toBe(true)
        expect(wrapper.find('.panel-chevron').text()).toBe('▾')
    })

    it('should show elapsed time in seconds when agent is running', () => {
        vi.useFakeTimers()
        const now = Date.now()
        // reactive store — watch immediate 会读到 running=true
        const store = createMockStore({
            agentRunning: true,
            agentRunStartedAt: now - 5000
        })
        useAgentStore.mockReturnValue(store)
        const wrapper = mount(LiveEvalHud)

        // 由于 agentRunning=true，watch immediate 启动 timer
        // 推进 250ms 让 tick 触发一次
        vi.advanceTimersByTime(300)
        // tick 后 elapsedLabel 会计算差值 = 5000 + 300 ≈ 5300 ms → 5.3 s
        const text = wrapper.text()
        expect(text).toMatch(/\d+\.\d+\s*s/)

        vi.useRealTimers()
    })

    it('should show ms elapsed when under 1s', () => {
        vi.useFakeTimers()
        const now = Date.now()
        const store = createMockStore({
            agentRunning: true,
            agentRunStartedAt: now - 500
        })
        useAgentStore.mockReturnValue(store)
        const wrapper = mount(LiveEvalHud)

        vi.advanceTimersByTime(100)
        // 500 + 100 = 600 ms
        const text = wrapper.text()
        expect(text).toMatch(/\d+\s*ms/)

        vi.useRealTimers()
    })

    it('should expand when agent starts running', async () => {
        vi.useFakeTimers()
        const store = createMockStore({ agentRunning: false, agentRunStartedAt: null })
        useAgentStore.mockReturnValue(store)
        const wrapper = mount(LiveEvalHud)

        // Collapse first
        await wrapper.find('.panel-toggle').trigger('click')
        expect(wrapper.find('.panel-body').exists()).toBe(false)

        // Simulate agent start via reactive store
        store.agentRunning = true
        store.agentRunStartedAt = Date.now()
        await wrapper.vm.$nextTick()

        // watch 应在 agentRunning 变为 true 时设 collapsed.value = false
        expect(wrapper.find('.panel-body').exists()).toBe(true)

        vi.useRealTimers()
    })
})
