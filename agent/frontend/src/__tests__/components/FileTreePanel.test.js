/**
 * components/FileTreePanel.test.js
 * 测试文件树面板组件
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import FileTreePanel from '../../components/FileTreePanel.vue'
import { useAgentStore } from '../../stores/agent.js'

vi.mock('../../stores/agent.js', async (importOriginal) => {
    const actual = await importOriginal()
    return { useAgentStore: vi.fn() }
})

function createMockStore(overrides = {}) {
    return {
        selectedProjectId: null,
        fileTree: [],
        fetchFileTree: vi.fn(),
        ...overrides
    }
}

describe('FileTreePanel.vue', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        const pinia = createPinia()
        setActivePinia(pinia)
    })

    it('should show empty hint when no project selected', () => {
        useAgentStore.mockReturnValue(createMockStore())
        const wrapper = mount(FileTreePanel)
        expect(wrapper.find('.empty-hint').text()).toContain('Select a project')
    })

    it('should show empty hint when fileTree is empty', () => {
        useAgentStore.mockReturnValue(createMockStore({ selectedProjectId: 'p1', fileTree: [] }))
        const wrapper = mount(FileTreePanel)
        expect(wrapper.find('.empty-hint').text()).toContain('No files')
    })

    it('should render FileTreeNode for each tree item', () => {
        useAgentStore.mockReturnValue(createMockStore({
            selectedProjectId: 'p1',
            fileTree: [
                { path: '/src', type: 'directory', children: [] },
                { path: '/README.md', type: 'file' }
            ]
        }))
        const wrapper = mount(FileTreePanel)
        const nodes = wrapper.findAll('.tree-node')
        expect(nodes).toHaveLength(2)
    })

    it('should call store.fetchFileTree on refresh button click', async () => {
        const mockStore = createMockStore({ selectedProjectId: 'p1', fileTree: [] })
        useAgentStore.mockReturnValue(mockStore)
        const wrapper = mount(FileTreePanel)
        await wrapper.find('button[title="Refresh"]').trigger('click')
        expect(mockStore.fetchFileTree).toHaveBeenCalled()
    })

    it('should collapse and expand file tree body', async () => {
        useAgentStore.mockReturnValue(createMockStore({
            selectedProjectId: 'p1',
            fileTree: [{ path: '/test.js', type: 'file' }]
        }))
        const wrapper = mount(FileTreePanel)
        expect(wrapper.find('.filetree-body').exists()).toBe(true)
        await wrapper.find('button[title="Collapse Files"]').trigger('click')
        expect(wrapper.find('.filetree-body').exists()).toBe(false)
        await wrapper.find('button[title="Expand Files"]').trigger('click')
        expect(wrapper.find('.filetree-body').exists()).toBe(true)
    })

    it('should emit select-file when child node emits select', async () => {
        useAgentStore.mockReturnValue(createMockStore({
            selectedProjectId: 'p1',
            fileTree: [{ path: '/test.js', type: 'file' }]
        }))
        const wrapper = mount(FileTreePanel)
        // 点击文件节点触发 select
        const node = wrapper.find('.tree-node')
        await node.trigger('click')
        expect(wrapper.emitted('select-file')).toBeTruthy()
    })
})
