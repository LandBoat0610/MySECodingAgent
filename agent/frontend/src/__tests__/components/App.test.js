/**
 * 根组件：挂载 router-view 与全局样式
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import App from '../../App.vue'

describe('App.vue', () => {
  beforeEach(() => {
    const pinia = createPinia()
    setActivePinia(pinia)
  })

  it('should render routed view at /', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/', component: { template: '<div class="stub-route">OK</div>' } }]
    })
    const wrapper = mount(App, {
      global: { plugins: [router] }
    })
    await router.push('/')
    await router.isReady()
    expect(wrapper.find('.stub-route').exists()).toBe(true)
  })
})
