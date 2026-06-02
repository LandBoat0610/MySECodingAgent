import { createRouter, createWebHistory } from 'vue-router'
import MainShell from '../layouts/MainShell.vue'
import IdeLayout from '../layouts/IdeLayout.vue'
import EvalLayout from '../layouts/EvalLayout.vue'

function redirectLegacyEvaluation(to) {
  const pm = to.params.pathMatch
  if (Array.isArray(pm)) {
    const rest = pm.filter(Boolean).join('/')
    return rest ? `/workspace/evaluation/${rest}` : '/workspace/evaluation/tasks'
  }
  return pm ? `/workspace/evaluation/${pm}` : '/workspace/evaluation/tasks'
}

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/evaluation/:pathMatch(.*)*',
      redirect: redirectLegacyEvaluation
    },
    {
      path: '/',
      component: MainShell,
      redirect: '/workspace/ide',
      children: [
        {
          path: 'workspace/ide',
          name: 'ide',
          component: IdeLayout
        },
        {
          path: 'workspace/evaluation',
          component: EvalLayout,
          redirect: { name: 'eval-tasks' },
          children: [
            {
              path: 'tasks',
              name: 'eval-tasks',
              component: () => import('../views/evaluation/EvalTasksView.vue'),
              meta: { title: '任务管理' }
            },
            {
              path: 'metrics',
              name: 'eval-metrics',
              component: () => import('../views/evaluation/EvalMetricsView.vue'),
              meta: { title: '指标看板' }
            },
            {
              path: 'compare',
              name: 'eval-compare',
              component: () => import('../views/evaluation/EvalCompareView.vue'),
              meta: { title: '对比分析' }
            },
            {
              path: 'charts',
              name: 'eval-charts',
              component: () => import('../views/evaluation/EvalChartsView.vue'),
              meta: { title: '图表可视化' }
            },
            {
              path: 'results/:taskId',
              name: 'eval-results',
              component: () => import('../views/evaluation/EvalResultDetail.vue'),
              meta: { title: '结果明细' }
            }
          ]
        }
      ]
    }
  ]
})

export default router
