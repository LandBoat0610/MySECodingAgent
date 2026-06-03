/**
 * components/FileTreeNode.test.js
 * 测试文件树节点组件：展开/折叠、文件选择事件
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import FileTreeNode from '../../components/FileTreeNode.vue'

const mockPaths = ref(new Set())

vi.mock('../../composables/useExpandedDirs.js', () => ({
    useExpandedDirs: () => ({
        isExpanded: (path) => mockPaths.value.has(path),
        toggle: (path) => {
            const next = new Set(mockPaths.value)
            next.has(path) ? next.delete(path) : next.add(path)
            mockPaths.value = next
        }
    })
}))

describe('FileTreeNode.vue', () => {
    beforeEach(() => {
        mockPaths.value = new Set()
    })
    // ---- directory node ----
    describe('directory node', () => {
        const dirNode = {
            path: '/src',
            type: 'directory',
            children: [
                { path: '/src/main.js', type: 'file' },
                { path: '/src/utils.js', type: 'file' }
            ]
        }

        it('should render directory name', () => {
            const wrapper = mount(FileTreeNode, {
                props: { node: dirNode, depth: 0 }
            })
            expect(wrapper.find('.node-name').text()).toBe('src')
        })

        it('should show folder icon (collapsed by default)', () => {
            const wrapper = mount(FileTreeNode, {
                props: { node: dirNode, depth: 0 }
            })
            expect(wrapper.find('.node-icon').text()).toBe('📁')
            expect(wrapper.find('.node-arrow').text()).toBe('▸')
        })

        it('should expand on click and show children', async () => {
            const wrapper = mount(FileTreeNode, {
                props: { node: dirNode, depth: 0 }
            })
            await wrapper.find('.tree-node').trigger('click')
            expect(wrapper.find('.node-arrow').text()).toBe('▾')
            expect(wrapper.find('.node-icon').text()).toBe('📂')
            // children should render
            const childNodes = wrapper.findAllComponents(FileTreeNode)
            expect(childNodes).toHaveLength(2) // 2 file children
        })

        it('should toggle on arrow click', async () => {
            const wrapper = mount(FileTreeNode, {
                props: { node: dirNode, depth: 0 }
            })
            const arrow = wrapper.find('.node-arrow')
            await arrow.trigger('click')
            expect(wrapper.find('.node-arrow').text()).toBe('▾')
            await arrow.trigger('click')
            expect(wrapper.find('.node-arrow').text()).toBe('▸')
        })

        it('should apply correct padding based on depth', () => {
            const wrapper = mount(FileTreeNode, {
                props: { node: dirNode, depth: 2 }
            })
            const treeNode = wrapper.find('.tree-node')
            expect(treeNode.attributes('style')).toContain('padding-left')
        })
    })

    // ---- file node ----
    describe('file node', () => {
        const fileNode = {
            path: '/src/main.js',
            type: 'file'
        }

        it('should render file name', () => {
            const wrapper = mount(FileTreeNode, {
                props: { node: fileNode, depth: 1 }
            })
            expect(wrapper.find('.node-name').text()).toBe('main.js')
        })

        it('should show file icon and no arrow', () => {
            const wrapper = mount(FileTreeNode, {
                props: { node: fileNode, depth: 0 }
            })
            expect(wrapper.find('.node-icon').text()).toBe('📄')
            expect(wrapper.find('.node-arrow').exists()).toBe(false)
        })

        it('should have is-file class', () => {
            const wrapper = mount(FileTreeNode, {
                props: { node: fileNode, depth: 0 }
            })
            expect(wrapper.find('.tree-node').classes()).toContain('is-file')
        })

        it('should emit select event on click', async () => {
            const wrapper = mount(FileTreeNode, {
                props: { node: fileNode, depth: 0 }
            })
            await wrapper.find('.tree-node').trigger('click')
            expect(wrapper.emitted('select')).toBeTruthy()
            expect(wrapper.emitted('select')[0][0]).toEqual(fileNode)
        })

        it('should not expand or show children for file nodes', () => {
            const wrapper = mount(FileTreeNode, {
                props: { node: fileNode, depth: 0 }
            })
            expect(wrapper.findAllComponents(FileTreeNode)).toHaveLength(0)
        })
    })

    // ---- empty directory ----
    describe('empty directory', () => {
        it('should handle directory with no children', () => {
            const emptyDir = {
                path: '/empty',
                type: 'directory',
                children: []
            }
            const wrapper = mount(FileTreeNode, {
                props: { node: emptyDir, depth: 0 }
            })
            expect(wrapper.find('.node-name').text()).toBe('empty')
            // expand it
            wrapper.find('.tree-node').trigger('click')
            // no FileTreeNode children should render (empty array)
            expect(wrapper.findAllComponents(FileTreeNode)).toHaveLength(0)
        })
    })
})
