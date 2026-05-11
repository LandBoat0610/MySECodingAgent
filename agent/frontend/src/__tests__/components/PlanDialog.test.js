/**
 * components/PlanDialog.test.js
 * 测试 Agent 计划确认对话框组件
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import PlanDialog from '../../components/PlanDialog.vue'
import { useAgentStore } from '../../stores/agent.js'

vi.mock('../../stores/agent.js', async () => {
    return { useAgentStore: vi.fn() }
})

function createMockStore(overrides = {}) {
    return {
        pendingPlans: [],
        doPlanAction: vi.fn(),
        fetchPlans: vi.fn(),
        restoreSessionState: vi.fn(),
        connectWebSocket: vi.fn(),
        ...overrides
    }
}

describe('PlanDialog.vue', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        const pinia = createPinia()
        setActivePinia(pinia)
    })

    it('should render pending plans list', () => {
        useAgentStore.mockReturnValue(createMockStore({
            pendingPlans: [
                { id: 'plan-1', content: 'Create file structure', status: 'pending', created_at: '2025-01-01T00:00:00Z' },
                { id: 'plan-2', content: 'Install dependencies', status: 'pending', created_at: null }
            ]
        }))
        const wrapper = mount(PlanDialog)
        expect(wrapper.find('.plan-count').text()).toContain('2 步待确认')
        const items = wrapper.findAll('.plan-item')
        expect(items).toHaveLength(2)
        expect(items[0].text()).toContain('Create file structure')
        expect(items[1].text()).toContain('Install dependencies')
    })

    it('should show 1 step(s) for single plan', () => {
        useAgentStore.mockReturnValue(createMockStore({
            pendingPlans: [{ id: 'p1', content: 'Step', status: 'pending' }]
        }))
        const wrapper = mount(PlanDialog)
        expect(wrapper.find('.plan-count').text()).toContain('1 步待确认')
    })

    it('should render all four action buttons', () => {
        useAgentStore.mockReturnValue(createMockStore({
            pendingPlans: [{ id: 'p1', content: 'Step', status: 'pending' }]
        }))
        const wrapper = mount(PlanDialog)
        expect(wrapper.find('.btn-agree').exists()).toBe(true)
        expect(wrapper.find('.btn-refine').exists()).toBe(true)
        expect(wrapper.find('.btn-skip').exists()).toBe(true)
        expect(wrapper.find('.btn-stop').exists()).toBe(true)
    })

    it('should display plan content', () => {
        useAgentStore.mockReturnValue(createMockStore({
            pendingPlans: [{ id: 'p1', content: 'My plan step', status: 'pending', created_at: null }]
        }))
        const wrapper = mount(PlanDialog)
        expect(wrapper.find('.plan-item-content').text()).toBe('My plan step')
    })

    // ---- 操作按钮 ----
    describe('action buttons', () => {
        it('should call doPlanAction with "agree", then fetchPlans', async () => {
            const mockStore = createMockStore({
                pendingPlans: [{ id: 'plan-1', content: 'Step', status: 'pending' }]
            })
            useAgentStore.mockReturnValue(mockStore)
            const wrapper = mount(PlanDialog)
            await wrapper.find('.btn-agree').trigger('click')
            expect(mockStore.doPlanAction).toHaveBeenCalledWith('plan-1', 'agree')
            // 等待异步完成
            await new Promise(r => setTimeout(r, 10))
            expect(mockStore.fetchPlans).toHaveBeenCalled()
        })

        it('should call doPlanAction with "refine"', async () => {
            const mockStore = createMockStore({
                pendingPlans: [{ id: 'plan-1', content: 'Step', status: 'pending' }]
            })
            useAgentStore.mockReturnValue(mockStore)
            const wrapper = mount(PlanDialog)
            await wrapper.find('.btn-refine').trigger('click')
            expect(mockStore.doPlanAction).toHaveBeenCalledWith('plan-1', 'refine')
        })

        it('should call doPlanAction with "skip"', async () => {
            const mockStore = createMockStore({
                pendingPlans: [{ id: 'plan-1', content: 'Step', status: 'pending' }]
            })
            useAgentStore.mockReturnValue(mockStore)
            const wrapper = mount(PlanDialog)
            await wrapper.find('.btn-skip').trigger('click')
            expect(mockStore.doPlanAction).toHaveBeenCalledWith('plan-1', 'skip')
        })

        it('should call doPlanAction with "stop"', async () => {
            const mockStore = createMockStore({
                pendingPlans: [{ id: 'plan-1', content: 'Step', status: 'pending' }]
            })
            useAgentStore.mockReturnValue(mockStore)
            const wrapper = mount(PlanDialog)
            await wrapper.find('.btn-stop').trigger('click')
            expect(mockStore.doPlanAction).toHaveBeenCalledWith('plan-1', 'stop')
        })

        it('should disable buttons while action is loading', async () => {
            const mockStore = createMockStore({
                pendingPlans: [{ id: 'plan-1', content: 'Step', status: 'pending' }]
            })
            // Make doPlanAction stall so loading stays true
            mockStore.doPlanAction.mockImplementation(() => new Promise(() => { }))
            useAgentStore.mockReturnValue(mockStore)
            const wrapper = mount(PlanDialog)
            await wrapper.find('.btn-stop').trigger('click')

            // After click, all buttons should be disabled
            const buttons = wrapper.findAll('.plan-actions .btn')
            for (const btn of buttons) {
                expect(btn.attributes('disabled')).toBeDefined()
            }
        })
    })

    it('should handle empty pending plans gracefully (no crash)', () => {
        useAgentStore.mockReturnValue(createMockStore({ pendingPlans: [] }))
        const wrapper = mount(PlanDialog)
        expect(wrapper.find('.plan-count').text()).toContain('0 步待确认')
        expect(wrapper.findAll('.plan-item')).toHaveLength(0)
    })
})
