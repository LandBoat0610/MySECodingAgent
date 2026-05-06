/**
 * layouts/EvalLayout.test.js
 * 测试评测布局组件：路由子视图与导航渲染
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import EvalLayout from '../../layouts/EvalLayout.vue'
import { useEvaluationStore } from '../../stores/evaluation.js'

vi.mock('../../stores/evaluation.js', () => ({
    useEvaluationStore: vi.fn()
}))

function createMockEvalStore(overrides = {}) {
    return {
        datasets: [],
        tasks: [],
        loading: false,
        error: null,
        loadAll: vi.fn().mockResolvedValue(undefined),
        loadDatasets: vi.fn().mockResolvedValue(undefined),
        loadTasks: vi.fn().mockResolvedValue(undefined),
        clearError: vi.fn(),
        ...overrides
    }
}

function createRouterWithRoutes() {
    return createRouter({
        history: createMemoryHistory(),
        routes: [
            {
                path: '/workspace/evaluation',
                component: EvalLayout,
                children: [
                    { path: 'tasks', component: { template: '<div class="stub-tasks">Tasks</div>' } },
                    { path: 'metrics', component: { template: '<div class="stub-metrics">Metrics</div>' } },
                    { path: 'compare', component: { template: '<div class="stub-compare">Compare</div>' } },
                    { path: 'charts', component: { template: '<div class="stub-charts">Charts</div>' } },
                ]
            }
        ]
    })
}

describe('EvalLayout.vue', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        const pinia = createPinia()
        setActivePinia(pinia)
        useEvaluationStore.mockReturnValue(createMockEvalStore())
    })

    it('should mount and render navigation tabs', async () => {
        const router = createRouterWithRoutes()
        const wrapper = mount(EvalLayout, {
            global: { plugins: [router] }
        })
        router.push('/workspace/evaluation/tasks')
        await router.isReady()

        expect(wrapper.find('.eval-layout').exists()).toBe(true)
        const navLinks = wrapper.findAll('.tab-link')
        expect(navLinks.length).toBeGreaterThanOrEqual(2)
    })

    it('should navigate to tasks view', async () => {
        const router = createRouterWithRoutes()
        const wrapper = mount(EvalLayout, {
            global: { plugins: [router] }
        })
        router.push('/workspace/evaluation/tasks')
        await router.isReady()

        expect(wrapper.find('.stub-tasks').exists()).toBe(true)
    })

    it('should navigate to metrics view', async () => {
        const router = createRouterWithRoutes()
        const wrapper = mount(EvalLayout, {
            global: { plugins: [router] }
        })
        router.push('/workspace/evaluation/metrics')
        await router.isReady()

        expect(wrapper.find('.stub-metrics').exists()).toBe(true)
    })

    it('should navigate to compare view', async () => {
        const router = createRouterWithRoutes()
        const wrapper = mount(EvalLayout, {
            global: { plugins: [router] }
        })
        router.push('/workspace/evaluation/compare')
        await router.isReady()

        expect(wrapper.find('.stub-compare').exists()).toBe(true)
    })

    it('should navigate to charts view', async () => {
        const router = createRouterWithRoutes()
        const wrapper = mount(EvalLayout, {
            global: { plugins: [router] }
        })
        router.push('/workspace/evaluation/charts')
        await router.isReady()

        expect(wrapper.find('.stub-charts').exists()).toBe(true)
    })

    it('should call loadAll on mount', () => {
        const mockStore = createMockEvalStore()
        useEvaluationStore.mockReturnValue(mockStore)

        const router = createRouterWithRoutes()
        mount(EvalLayout, {
            global: { plugins: [router] }
        })
        expect(mockStore.loadAll).toHaveBeenCalled()
    })

    it('should show error banner when error is present', () => {
        useEvaluationStore.mockReturnValue(createMockEvalStore({ error: 'Something went wrong' }))
        const router = createRouterWithRoutes()
        const wrapper = mount(EvalLayout, {
            global: { plugins: [router] }
        })
        expect(wrapper.find('.error-banner').exists()).toBe(true)
        expect(wrapper.find('.error-banner').text()).toContain('Something went wrong')
    })

    it('should call clearError on dismiss error click', async () => {
        const mockStore = createMockEvalStore({ error: 'Error msg' })
        useEvaluationStore.mockReturnValue(mockStore)
        const router = createRouterWithRoutes()
        const wrapper = mount(EvalLayout, {
            global: { plugins: [router] }
        })
        await wrapper.find('.error-dismiss').trigger('click')
        expect(mockStore.clearError).toHaveBeenCalled()
    })
})
