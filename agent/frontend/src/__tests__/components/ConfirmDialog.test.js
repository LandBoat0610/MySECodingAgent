/**
 * components/ConfirmDialog.test.js
 * 测试自定义确认弹窗组件与 useConfirm composable
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import ConfirmDialog from '../../components/ConfirmDialog.vue'
import { showConfirm, useConfirmDialog } from '../../composables/useConfirm.js'

// 确认弹窗需要挂载到 DOM 中才能正常渲染 Transition
function mountDialog() {
    return mount(ConfirmDialog, { attachTo: document.body })
}

describe('ConfirmDialog.vue', () => {
    beforeEach(() => {
        // 重置全局状态
        const { onCancel } = useConfirmDialog()
        onCancel() // 关闭任何打开的弹窗
    })

    describe('rendering', () => {
        it('should be hidden by default', () => {
            const wrapper = mountDialog()
            expect(wrapper.find('.confirm-dialog').exists()).toBe(false)
            wrapper.unmount()
        })

        it('should show dialog when showConfirm is called', async () => {
            const wrapper = mountDialog()
            showConfirm({ title: '测试', message: '确认消息内容', variant: 'danger' })
            await nextTick()
            expect(wrapper.find('.confirm-dialog').exists()).toBe(true)
            expect(wrapper.text()).toContain('测试')
            expect(wrapper.text()).toContain('确认消息内容')
            wrapper.unmount()
        })

        it('should show danger variant with ⚠️ icon', async () => {
            const wrapper = mountDialog()
            showConfirm({ title: '危险操作', message: '确认删除？', variant: 'danger' })
            await nextTick()
            expect(wrapper.text()).toContain('⚠️')
            wrapper.unmount()
        })

        it('should show warning variant with ⚡ icon', async () => {
            const wrapper = mountDialog()
            showConfirm({ title: '警告', message: '注意', variant: 'warning' })
            await nextTick()
            expect(wrapper.text()).toContain('⚡')
            wrapper.unmount()
        })

        it('should show info variant with ℹ️ icon', async () => {
            const wrapper = mountDialog()
            showConfirm({ title: '提示', message: '信息', variant: 'info' })
            await nextTick()
            expect(wrapper.text()).toContain('ℹ️')
            wrapper.unmount()
        })

        it('should use custom button texts', async () => {
            const wrapper = mountDialog()
            showConfirm({ title: 'T', message: 'M', confirmText: 'Yes', cancelText: 'No' })
            await nextTick()
            const buttons = wrapper.findAll('button')
            expect(buttons.some(b => b.text() === 'Yes')).toBe(true)
            expect(buttons.some(b => b.text() === 'No')).toBe(true)
            wrapper.unmount()
        })
    })

    describe('interaction', () => {
        it('should resolve true on confirm click', async () => {
            const wrapper = mountDialog()
            const promise = showConfirm({ title: '确认', message: '确定？' })
            await nextTick()

            // 点击确定按钮
            const buttons = wrapper.findAll('button')
            const confirmBtn = buttons.find(b => b.text() === '确定')
            await confirmBtn.trigger('click')

            const result = await promise
            expect(result).toBe(true)
            wrapper.unmount()
        })

        it('should resolve false on cancel click', async () => {
            const wrapper = mountDialog()
            const promise = showConfirm({ title: '确认', message: '确定？' })
            await nextTick()

            const buttons = wrapper.findAll('button')
            const cancelBtn = buttons.find(b => b.text() === '取消')
            await cancelBtn.trigger('click')

            const result = await promise
            expect(result).toBe(false)
            wrapper.unmount()
        })

        it('should resolve false on mask click', async () => {
            const wrapper = mountDialog()
            const promise = showConfirm({ title: '确认', message: '确定？' })
            await nextTick()

            await wrapper.find('.confirm-mask').trigger('click')

            const result = await promise
            expect(result).toBe(false)
            wrapper.unmount()
        })

        it('should close dialog after confirm', async () => {
            const wrapper = mountDialog()
            const promise = showConfirm({ title: 'X', message: 'Y' })
            await nextTick()

            const buttons = wrapper.findAll('button')
            const confirmBtn = buttons.find(b => b.text() === '确定')
            await confirmBtn.trigger('click')
            await promise
            await nextTick()

            expect(wrapper.find('.confirm-dialog').exists()).toBe(false)
            wrapper.unmount()
        })

        it('should close dialog after cancel', async () => {
            const wrapper = mountDialog()
            const promise = showConfirm({ title: 'X', message: 'Y' })
            await nextTick()

            const buttons = wrapper.findAll('button')
            const cancelBtn = buttons.find(b => b.text() === '取消')
            await cancelBtn.trigger('click')
            await promise
            await nextTick()

            expect(wrapper.find('.confirm-dialog').exists()).toBe(false)
            wrapper.unmount()
        })
    })

    describe('composable', () => {
        it('showConfirm should return a Promise', () => {
            const result = showConfirm({ title: 'T', message: 'M' })
            expect(result).toBeInstanceOf(Promise)
            // 清理
            const { onCancel } = useConfirmDialog()
            onCancel()
        })

        it('should support multiple sequential confirms', async () => {
            const wrapper = mountDialog()

            const p1 = showConfirm({ title: 'First', message: 'Msg 1' })
            await nextTick()
            const buttons1 = wrapper.findAll('button')
            await buttons1.find(b => b.text() === '确定').trigger('click')
            expect(await p1).toBe(true)
            await nextTick()

            const p2 = showConfirm({ title: 'Second', message: 'Msg 2' })
            await nextTick()
            const buttons2 = wrapper.findAll('button')
            await buttons2.find(b => b.text() === '取消').trigger('click')
            expect(await p2).toBe(false)

            wrapper.unmount()
        })
    })
})
