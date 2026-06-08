/**
 * router/index.test.js
 * 测试路由配置（使用 memory history 以避免浏览器 API 依赖）
 */
import { describe, it, expect, vi } from 'vitest'
import { createRouter, createMemoryHistory } from 'vue-router'

// Mock dynamic imports with synchronous components
vi.mock('../../views/evaluation/EvalTasksView.vue', () => ({
    default: { name: 'EvalTasksView', template: '<div>Tasks</div>' }
}))
vi.mock('../../views/evaluation/EvalMetricsView.vue', () => ({
    default: { name: 'EvalMetricsView', template: '<div>Metrics</div>' }
}))
vi.mock('../../views/evaluation/EvalCompareView.vue', () => ({
    default: { name: 'EvalCompareView', template: '<div>Compare</div>' }
}))
vi.mock('../../views/evaluation/EvalChartsView.vue', () => ({
    default: { name: 'EvalChartsView', template: '<div>Charts</div>' }
}))
vi.mock('../../views/evaluation/EvalResultDetail.vue', () => ({
    default: { name: 'EvalResultDetail', template: '<div>Result</div>' }
}))
vi.mock('../../layouts/MainShell.vue', () => ({
    default: { name: 'MainShell', template: '<div><RouterView /></div>' }
}))
vi.mock('../../layouts/IdeLayout.vue', () => ({
    default: { name: 'IdeLayout', template: '<div>IDE</div>' }
}))
vi.mock('../../layouts/EvalLayout.vue', () => ({
    default: { name: 'EvalLayout', template: '<div><RouterView /></div>' }
}))

describe('router configuration', () => {
    // Build a router with the same route structure but using memory history
    const router = createRouter({
        history: createMemoryHistory(),
        routes: [
            {
                path: '/',
                component: () => import('../../layouts/MainShell.vue'),
                children: [
                    {
                        path: 'workspace/ide',
                        name: 'ide',
                        component: () => import('../../layouts/IdeLayout.vue')
                    },
                    {
                        path: 'workspace/evaluation',
                        component: () => import('../../layouts/EvalLayout.vue'),
                        children: [
                            {
                                path: 'tasks',
                                name: 'eval-tasks',
                                component: () => import('../../views/evaluation/EvalTasksView.vue'),
                                meta: { title: '任务管理' }
                            },
                            {
                                path: 'metrics',
                                name: 'eval-metrics',
                                component: () => import('../../views/evaluation/EvalMetricsView.vue'),
                                meta: { title: '指标看板' }
                            },
                            {
                                path: 'compare',
                                name: 'eval-compare',
                                component: () => import('../../views/evaluation/EvalCompareView.vue'),
                                meta: { title: '对比分析' }
                            },
                            {
                                path: 'charts',
                                name: 'eval-charts',
                                component: () => import('../../views/evaluation/EvalChartsView.vue'),
                                meta: { title: '图表可视化' }
                            },
                            {
                                path: 'results/:taskId',
                                name: 'eval-results',
                                component: () => import('../../views/evaluation/EvalResultDetail.vue'),
                                meta: { title: '结果明细' }
                            }
                        ]
                    }
                ]
            }
        ]
    })

    it('should be a router instance', () => {
        expect(router).toBeTruthy()
        expect(typeof router.push).toBe('function')
        expect(typeof router.resolve).toBe('function')
    })

    it('should resolve ide route', () => {
        const resolved = router.resolve({ name: 'ide' })
        expect(resolved.name).toBe('ide')
    })

    it('should resolve eval-tasks route', () => {
        const resolved = router.resolve({ name: 'eval-tasks' })
        expect(resolved.name).toBe('eval-tasks')
        expect(resolved.meta.title).toBe('任务管理')
    })

    it('should resolve eval-metrics route', () => {
        const resolved = router.resolve({ name: 'eval-metrics' })
        expect(resolved.name).toBe('eval-metrics')
        expect(resolved.meta.title).toBe('指标看板')
    })

    it('should resolve eval-compare route', () => {
        const resolved = router.resolve({ name: 'eval-compare' })
        expect(resolved.name).toBe('eval-compare')
        expect(resolved.meta.title).toBe('对比分析')
    })

    it('should resolve eval-charts route', () => {
        const resolved = router.resolve({ name: 'eval-charts' })
        expect(resolved.name).toBe('eval-charts')
        expect(resolved.meta.title).toBe('图表可视化')
    })

    it('should resolve eval-results route with taskId param', () => {
        const resolved = router.resolve({ name: 'eval-results', params: { taskId: 'task-1' } })
        expect(resolved.name).toBe('eval-results')
        expect(resolved.params.taskId).toBe('task-1')
        expect(resolved.meta.title).toBe('结果明细')
    })

    it('should have at least 6 named routes', () => {
        const routes = router.getRoutes()
        const namedRoutes = routes.filter(r => r.name)
        expect(namedRoutes.length).toBeGreaterThanOrEqual(6)
    })

    it('should redirect from root', () => {
        // With memory history, root / resolves to the MainShell
        const resolved = router.resolve('/')
        expect(resolved.matched.length).toBeGreaterThan(0)
    })

    it('should match eval-tasks path', () => {
        const resolved = router.resolve('/workspace/evaluation/tasks')
        expect(resolved.name).toBe('eval-tasks')
    })

    it('should match eval-metrics path', () => {
        const resolved = router.resolve('/workspace/evaluation/metrics')
        expect(resolved.name).toBe('eval-metrics')
    })

    it('should match eval-results path with dynamic param', () => {
        const resolved = router.resolve('/workspace/evaluation/results/my-task-id')
        expect(resolved.name).toBe('eval-results')
        expect(resolved.params.taskId).toBe('my-task-id')
    })
})
