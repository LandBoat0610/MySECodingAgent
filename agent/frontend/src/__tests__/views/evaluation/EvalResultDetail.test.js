/**
 * views/evaluation/EvalResultDetail.test.js
 * 测试评测结果明细组件
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import { setActivePinia, createPinia } from 'pinia'
import EvalResultDetail from '../../../views/evaluation/EvalResultDetail.vue'

// Mock API
vi.mock('../../../api/index.js', () => ({
    getEvalTaskResults: vi.fn()
}))

// Mock vue-router
const mockRoute = {
    params: { taskId: 'task-1' }
}
vi.mock('vue-router', () => ({
    useRoute: () => mockRoute,
    RouterLink: {
        name: 'RouterLink',
        template: '<a><slot /></a>',
        props: ['to']
    }
}))

// Mock status components
vi.mock('../../../components/status/index.js', () => ({
    LoadingSpinner: { name: 'LoadingSpinner', template: '<div class="loading-spinner"><slot /></div>', props: ['text'] },
    ErrorBanner: { name: 'ErrorBanner', template: '<div class="error-banner">{{ message }}</div>', props: ['message', 'dismissible'] },
    EmptyState: { name: 'EmptyState', template: '<div class="empty-state">{{ desc }}</div>', props: ['icon', 'title', 'desc'] }
}))

import { getEvalTaskResults } from '../../../api/index.js'

describe('EvalResultDetail', () => {
    beforeEach(() => {
        const pinia = createPinia()
        setActivePinia(pinia)
        vi.clearAllMocks()
    })

    function createWrapper() {
        return mount(EvalResultDetail)
    }

    it('should show loading spinner initially', () => {
        getEvalTaskResults.mockResolvedValue([])
        const wrapper = createWrapper()
        expect(wrapper.find('.loading-spinner').exists()).toBe(true)
    })

    it('should load and display results', async () => {
        getEvalTaskResults.mockResolvedValue([
            {
                id: 'r1',
                task_id: 'task-1',
                item_index: 0,
                passed: true,
                final_answer: 'sorted list output',
                trace_json: []
            },
            {
                id: 'r2',
                task_id: 'task-1',
                item_index: 1,
                passed: false,
                final_answer: 'error',
                trace_json: [{ phase: 'plan', content: 'step 1', time: '2024-01-01' }]
            }
        ])

        const wrapper = createWrapper()
        await flushPromises()
        await nextTick()

        expect(wrapper.find('.loading-spinner').exists()).toBe(false)
        // Should have rows
        const rows = wrapper.findAll('tr')
        // header + 2 data rows
        expect(rows.length).toBeGreaterThanOrEqual(2)

        // Should show passed/failed status
        expect(wrapper.text()).toContain('sorted list output')
    })

    it('should show empty state when no results', async () => {
        getEvalTaskResults.mockResolvedValue([])

        const wrapper = createWrapper()
        await flushPromises()
        await nextTick()

        expect(wrapper.find('.empty-state').exists()).toBe(true)
    })

    it('should show error banner on load failure', async () => {
        getEvalTaskResults.mockRejectedValue(new Error('Failed to load'))

        const wrapper = createWrapper()
        await flushPromises()
        await nextTick()

        expect(wrapper.find('.error-banner').exists()).toBe(true)
    })

    it('should show error banner on network error with response', async () => {
        getEvalTaskResults.mockRejectedValue({
            response: { data: { detail: 'Task not found' } }
        })

        const wrapper = createWrapper()
        await flushPromises()
        await nextTick()

        expect(wrapper.find('.error-banner').exists()).toBe(true)
        expect(wrapper.text()).toContain('Task not found')
    })

    it('should display task ID in title', async () => {
        getEvalTaskResults.mockResolvedValue([])

        const wrapper = createWrapper()
        await flushPromises()
        await nextTick()

        expect(wrapper.text()).toContain('task-1')
    })

    it('should show replay panel when clicking replay', async () => {
        getEvalTaskResults.mockResolvedValue([
            {
                id: 'r1',
                task_id: 'task-1',
                item_index: 0,
                passed: true,
                final_answer: 'test',
                trace_json: [{ phase: 'plan', content: 'step', time: '2024-01-01', state_outline: { status: 'running' } }]
            }
        ])

        const wrapper = createWrapper()
        await flushPromises()
        await nextTick()

        // Click replay button
        const replayBtn = wrapper.find('button.btn-sm')
        expect(replayBtn.exists()).toBe(true)
        await replayBtn.trigger('click')
        await nextTick()

        // Replay detail should appear
        expect(wrapper.find('.replay-detail').exists()).toBe(true)
        expect(wrapper.text()).toContain('过程溯源')
    })
})
