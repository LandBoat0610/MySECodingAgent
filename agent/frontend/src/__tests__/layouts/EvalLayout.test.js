/**
 * layouts/EvalLayout.test.js
 * 测试评测布局组件：路由子视图、导航渲染、错误处理
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import EvalLayout from '../../layouts/EvalLayout.vue'
import { useAgentConfigStore } from '../../stores/agentConfig.js'

vi.mock('../../stores/agentConfig.js', () => ({
    useAgentConfigStore: vi.fn()
}))

function createMockConfigStore(overrides = {}) {
    return {
        model: '',
        versionLabel: '',
        loading: false,
        error: null,
        load: vi.fn().mockResolvedValue(undefined),
        ...overrides
    }
}

function createRouterWithRoutes() {
    return createRouter({
        history: createMemoryHistory(),
        routes: [
            {
                path: '/',
                name: 'ide',
                component: { template: '<div class="stub-ide">IDE</div>' }
            },
            {
                path: '/workspace/evaluation',
                component: EvalLayout,
                children: [
                    { path: 'tasks', name: 'eval-tasks', component: { template: '<div class="stub-tasks">Tasks</div>' } },
                    { path: 'metrics', name: 'eval-metrics', component: { template: '<div class="stub-metrics">Metrics</div>' } },
                    { path: 'compare', name: 'eval-compare', component: { template: '<div class="stub-compare">Compare</div>' } },
                    { path: 'charts', name: 'eval-charts', component: { template: '<div class="stub-charts">Charts</div>' } },
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
        useAgentConfigStore.mockReturnValue(createMockConfigStore())
    })

    it('should mount and render navigation tabs', async () => {
        const router = createRouterWithRoutes()
        const wrapper = mount(EvalLayout, {
            global: { plugins: [router] }
        })
        router.push('/workspace/evaluation/tasks')
        await router.isReady()

        expect(wrapper.find('.eval-shell').exists()).toBe(true)
        const tabLinks = wrapper.findAll('.eval-tab')
        expect(tabLinks.length).toBeGreaterThanOrEqual(2)
        expect(tabLinks[0].text()).toBe('任务管理')
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

    it('should call agentConfigStore.load on mount', () => {
        const mockStore = createMockConfigStore()
        useAgentConfigStore.mockReturnValue(mockStore)

        const router = createRouterWithRoutes()
        mount(EvalLayout, {
            global: { plugins: [router] }
        })
        expect(mockStore.load).toHaveBeenCalled()
    })

    it('should have a back link to IDE', async () => {
        const router = createRouterWithRoutes()
        const wrapper = mount(EvalLayout, {
            global: { plugins: [router] }
        })
        router.push('/workspace/evaluation/tasks')
        await router.isReady()

        expect(wrapper.find('.back-to-ide').exists()).toBe(true)
        expect(wrapper.find('.back-to-ide').text()).toBe('← IDE')
    })

    it('should render eval title', async () => {
        const router = createRouterWithRoutes()
        const wrapper = mount(EvalLayout, {
            global: { plugins: [router] }
        })
        router.push('/workspace/evaluation/tasks')
        await router.isReady()

        expect(wrapper.find('.eval-title').text()).toBe('评测中心')
    })
})
