/**
 * components/FilePreview.test.js
 * 测试文件预览组件（已重构为 Pinia store 驱动，mock 需 reactive）
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { reactive } from 'vue'
import FilePreview from '../../components/FilePreview.vue'
import { useAgentStore } from '../../stores/agent.js'

vi.mock('../../stores/agent.js', () => ({
    useAgentStore: vi.fn()
}))

function createMockStore(overrides = {}) {
    return reactive({
        selectedFile: null,
        fileContent: '',
        fileLoading: false,
        error: null,
        ...overrides
    })
}

describe('FilePreview.vue', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        const pinia = createPinia()
        setActivePinia(pinia)
    })

    it('should show placeholder when no file selected', () => {
        useAgentStore.mockReturnValue(createMockStore())
        const wrapper = mount(FilePreview)
        expect(wrapper.find('.preview-title').text()).toBe('File Preview')
        expect(wrapper.find('.placeholder-text').text()).toContain('Select a file')
    })

    it('should display selected file path and type', () => {
        useAgentStore.mockReturnValue(createMockStore({
            selectedFile: { path: '/src/main.js', type: 'file' }
        }))
        const wrapper = mount(FilePreview)
        expect(wrapper.find('.preview-title').text()).toBe('/src/main.js')
        expect(wrapper.find('.preview-badge').text()).toBe('file')
    })

    it('should show loading state', () => {
        useAgentStore.mockReturnValue(createMockStore({
            selectedFile: { path: '/test.js', type: 'file' },
            fileLoading: true
        }))
        const wrapper = mount(FilePreview)
        expect(wrapper.find('.placeholder-text').text()).toBe('Loading...')
    })

    it('should show error state', () => {
        useAgentStore.mockReturnValue(createMockStore({
            selectedFile: { path: '/test.js', type: 'file' },
            error: 'File not found'
        }))
        const wrapper = mount(FilePreview)
        expect(wrapper.find('.placeholder-text').text()).toBe('File not found')
    })

    it('should render file content in pre tag when loaded', () => {
        useAgentStore.mockReturnValue(createMockStore({
            selectedFile: { path: '/test.js', type: 'file' },
            fileContent: 'console.log("hello")'
        }))
        const wrapper = mount(FilePreview)
        expect(wrapper.find('.preview-code').exists()).toBe(true)
        expect(wrapper.find('.preview-code').text()).toContain('console.log')
    })

    it('should return to placeholder when selectedFile is cleared', async () => {
        const store = createMockStore({
            selectedFile: { path: '/test.js', type: 'file' },
            fileContent: 'content'
        })
        useAgentStore.mockReturnValue(store)
        const wrapper = mount(FilePreview)
        expect(wrapper.find('.preview-code').exists()).toBe(true)

        // Clear selected file — reactive() 确保 Vue 追踪变化
        store.selectedFile = null
        store.fileContent = ''
        await wrapper.vm.$nextTick()

        expect(wrapper.find('.preview-title').text()).toBe('File Preview')
        expect(wrapper.find('.preview-badge').exists()).toBe(false)
    })
})
