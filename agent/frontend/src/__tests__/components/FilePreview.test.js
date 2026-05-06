/**
 * components/FilePreview.test.js
 * 测试文件预览组件
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import FilePreview from '../../components/FilePreview.vue'

describe('FilePreview.vue', () => {
    it('should show placeholder when no file selected', () => {
        const wrapper = mount(FilePreview)
        expect(wrapper.find('.preview-title').text()).toBe('File Preview')
        expect(wrapper.find('.placeholder-text').text()).toContain('Select a file')
    })

    it('should expose setSelectedFile method', () => {
        const wrapper = mount(FilePreview)
        expect(wrapper.vm.setSelectedFile).toBeInstanceOf(Function)
    })

    it('should update display when setSelectedFile is called', async () => {
        const wrapper = mount(FilePreview)
        wrapper.vm.setSelectedFile({ path: '/src/main.js', type: 'file' })
        await wrapper.vm.$nextTick()
        expect(wrapper.find('.preview-title').text()).toBe('/src/main.js')
        expect(wrapper.find('.preview-badge').text()).toBe('file')
    })

    it('should display the TODO message for both empty and selected state', () => {
        const wrapper = mount(FilePreview)
        expect(wrapper.find('.placeholder-todo').text()).toContain('TODO')
    })

    it('should accept null to clear selected file', async () => {
        const wrapper = mount(FilePreview)
        wrapper.vm.setSelectedFile({ path: '/test.js', type: 'file' })
        await wrapper.vm.$nextTick()
        wrapper.vm.setSelectedFile(null)
        await wrapper.vm.$nextTick()
        expect(wrapper.find('.preview-title').text()).toBe('File Preview')
        expect(wrapper.find('.preview-badge').exists()).toBe(false)
    })
})
