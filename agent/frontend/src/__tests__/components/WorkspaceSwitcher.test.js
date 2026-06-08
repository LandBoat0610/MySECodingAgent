/**
 * components/WorkspaceSwitcher.test.js
 * 测试工作区切换按钮组件
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import WorkspaceSwitcher from '../../components/WorkspaceSwitcher.vue'

// Mock vue-router
const mockPush = vi.fn()
vi.mock('vue-router', () => ({
    useRoute: vi.fn(),
    useRouter: vi.fn(() => ({
        push: mockPush
    }))
}))

import { useRoute, useRouter } from 'vue-router'

describe('WorkspaceSwitcher', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mockPush.mockClear()
    })

    function createWrapper(routeName = 'ide') {
        useRoute.mockReturnValue({ name: routeName })
        useRouter.mockReturnValue({ push: mockPush })
        return mount(WorkspaceSwitcher)
    }

    it('should render both IDE and 评测中心 buttons', () => {
        const wrapper = createWrapper()
        const buttons = wrapper.findAll('button')
        expect(buttons).toHaveLength(2)
        expect(buttons[0].text()).toBe('IDE')
        expect(buttons[1].text()).toBe('评测中心')
    })

    it('should mark IDE button as active when on IDE route', () => {
        const wrapper = createWrapper('ide')
        const ideBtn = wrapper.findAll('button')[0]
        expect(ideBtn.classes()).toContain('active')
    })

    it('should mark 评测中心 button as active when on eval route', () => {
        const wrapper = createWrapper('eval-tasks')
        const evalBtn = wrapper.findAll('button')[1]
        expect(evalBtn.classes()).toContain('active')
    })

    it('should navigate to eval-tasks when clicking 评测中心 from IDE', async () => {
        const wrapper = createWrapper('ide')
        const evalBtn = wrapper.findAll('button')[1]
        await evalBtn.trigger('click')
        expect(mockPush).toHaveBeenCalledWith({ name: 'eval-tasks' })
    })

    it('should navigate to IDE when clicking IDE from eval route', async () => {
        const wrapper = createWrapper('eval-tasks')
        const ideBtn = wrapper.findAll('button')[0]
        await ideBtn.trigger('click')
        expect(mockPush).toHaveBeenCalledWith({ name: 'ide' })
    })

    it('should not navigate when already on IDE and clicking IDE', async () => {
        const wrapper = createWrapper('ide')
        const ideBtn = wrapper.findAll('button')[0]
        await ideBtn.trigger('click')
        expect(mockPush).not.toHaveBeenCalled()
    })

    it('should not navigate when already on eval and clicking eval', async () => {
        const wrapper = createWrapper('eval-tasks')
        const evalBtn = wrapper.findAll('button')[1]
        await evalBtn.trigger('click')
        expect(mockPush).not.toHaveBeenCalled()
    })

    it('should have correct aria-pressed values', () => {
        const wrapper = createWrapper('ide')
        const buttons = wrapper.findAll('button')
        expect(buttons[0].attributes('aria-pressed')).toBe('true')
        expect(buttons[1].attributes('aria-pressed')).toBe('false')
    })

    it('should have role toolbar', () => {
        const wrapper = createWrapper()
        expect(wrapper.attributes('role')).toBe('toolbar')
        expect(wrapper.attributes('aria-label')).toBe('工作区切换')
    })
})
