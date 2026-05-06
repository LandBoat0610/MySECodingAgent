/**
 * components/LiveEvalHud.test.js
 * 测试实时评测 HUD 面板组件
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import LiveEvalHud from '../../components/LiveEvalHud.vue'
import { useAgentStore } from '../../stores/agent.js'

vi.mock('../../stores/agent.js', async (importOriginal) => {
    return { useAgentStore: vi.fn() }
})

function createMockStore(overrides = {}) {
    return {
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
    }
}

describe('LiveEvalHud.vue', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        vi.useFakeTimers()
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

    it('should show elapsed time as dash when not started', () => {
        useAgentStore.mockReturnValue(createMockStore())
        const wrapper = mount(LiveEvalHud)
        expect(wrapper.text()).toContain('—')
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

        // Initially not collapsed (panel-body visible)
        expect(wrapper.find('.panel-body').exists()).toBe(true)

        await btn.trigger('click')
        expect(wrapper.find('.panel-body').exists()).toBe(false)
        expect(wrapper.find('.panel-chevron').text()).toBe('▸')

        await btn.trigger('click')
        expect(wrapper.find('.panel-body').exists()).toBe(true)
        expect(wrapper.find('.panel-chevron').text()).toBe('▾')
    })

    it('should show elapsed time when agent is running', () => {
        const now = Date.now()
        useAgentStore.mockReturnValue(createMockStore({
            agentRunning: true,
            agentRunStartedAt: now - 5000  // started 5s ago
        }))
        const wrapper = mount(LiveEvalHud)
        // Should show seconds-based elapsed
        expect(wrapper.text()).toMatch(/\d+\.\d+\s*s/)
    })

    it('should show ms elapsed when under 1s', () => {
        const now = Date.now()
        useAgentStore.mockReturnValue(createMockStore({
            agentRunning: true,
            agentRunStartedAt: now - 500  // started 500ms ago
        }))
        const wrapper = mount(LiveEvalHud)
        expect(wrapper.text()).toMatch(/\d+\s*ms/)
    })

    it('should expand when agent starts running', async () => {
        const store = createMockStore({ agentRunning: false })
        useAgentStore.mockReturnValue(store)
        const wrapper = mount(LiveEvalHud)

        // Collapse first
        await wrapper.find('.panel-toggle').trigger('click')
        expect(wrapper.find('.panel-body').exists()).toBe(false)

        // Simulate agent start
        store.agentRunning = true
        store.agentRunStartedAt = Date.now()
        await wrapper.vm.$nextTick()

        expect(wrapper.find('.panel-body').exists()).toBe(true)
    })
})
