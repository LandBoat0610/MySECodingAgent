/**
 * layouts/MainShell.test.js
 * 测试主布局外壳组件
 */
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import MainShell from '../../layouts/MainShell.vue'

// Mock child components
vi.mock('../../components/WorkspaceSwitcher.vue', () => ({
    default: { name: 'WorkspaceSwitcher', template: '<div class="workspace-switcher-mock" />' }
}))
vi.mock('../../components/ConfirmDialog.vue', () => ({
    default: { name: 'ConfirmDialog', template: '<div class="confirm-dialog-mock" />' }
}))

// Mock vue-router
vi.mock('vue-router', () => ({
    RouterView: { name: 'RouterView', template: '<div class="router-view-mock" />' }
}))

describe('MainShell', () => {
    it('should render all child components', () => {
        const wrapper = mount(MainShell)
        expect(wrapper.find('.router-view-mock').exists()).toBe(true)
        expect(wrapper.find('.workspace-switcher-mock').exists()).toBe(true)
        expect(wrapper.find('.confirm-dialog-mock').exists()).toBe(true)
    })

    it('should have main-shell class', () => {
        const wrapper = mount(MainShell)
        expect(wrapper.find('.main-shell').exists()).toBe(true)
    })
})
