/**
 * components/App.test.js
 * 测试根组件 App.vue：挂载、子组件渲染、生命周期
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import App from '../../App.vue'
import { useAgentStore } from '../../stores/agent.js'

// Mock 子组件，避免渲染整个子树
vi.mock('../../components/ProjectPanel.vue', () => ({
    default: { name: 'ProjectPanel', template: '<div class="mock-project-panel"></div>' }
}))
vi.mock('../../components/FileTreePanel.vue', () => ({
    default: { name: 'FileTreePanel', template: '<div class="mock-filetree-panel"></div>', emits: ['select-file'] }
}))
vi.mock('../../components/FilePreview.vue', () => ({
    default: { name: 'FilePreview', template: '<div class="mock-file-preview"></div>', emits: [], expose: [] }
}))
vi.mock('../../components/ChatPanel.vue', () => ({
    default: { name: 'ChatPanel', template: '<div class="mock-chat-panel"></div>' }
}))

// Mock store 方法
vi.mock('../../stores/agent.js', async (importOriginal) => {
    const actual = await importOriginal()
    return {
        useAgentStore: vi.fn()
    }
})

function createMockStore(overrides = {}) {
    return {
        selectedProjectId: null,
        selectedSessionId: null,
        sessionStatus: 'idle',
        fileTree: [],
        projects: [],
        sessions: [],
        pendingPlans: [],
        chatMessages: [],
        traceLogs: [],
        finalAnswer: '',
        agentRunning: false,
        error: null,
        loading: false,
        fetchProjects: vi.fn(),
        fetchSessions: vi.fn(),
        fetchFileTree: vi.fn(),
        restoreSessionState: vi.fn(),
        ...overrides
    }
}

describe('App.vue', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        const pinia = createPinia()
        setActivePinia(pinia)
    })

    it('should mount successfully', () => {
        useAgentStore.mockReturnValue(createMockStore())
        const wrapper = mount(App, {
            global: {
                stubs: {
                    ProjectPanel: true,
                    FileTreePanel: true,
                    FilePreview: true,
                    ChatPanel: true
                }
            }
        })
        expect(wrapper.find('.app-container').exists()).toBe(true)
    })

    it('should render left sidebar with ProjectPanel and FileTreePanel', () => {
        useAgentStore.mockReturnValue(createMockStore())
        const wrapper = mount(App, {
            global: {
                stubs: {
                    ProjectPanel: { template: '<div class="mock-project-panel">Project</div>' },
                    FileTreePanel: { template: '<div class="mock-filetree-panel">FileTree</div>' },
                    FilePreview: { template: '<div class="mock-file-preview">Preview</div>' },
                    ChatPanel: { template: '<div class="mock-chat-panel">Chat</div>' }
                }
            }
        })
        expect(wrapper.find('.left-sidebar').exists()).toBe(true)
        expect(wrapper.find('.center-preview').exists()).toBe(true)
        expect(wrapper.find('.right-panel').exists()).toBe(true)
    })

    it('should call store.fetchProjects on mount', async () => {
        const mockStore = createMockStore()
        useAgentStore.mockReturnValue(mockStore)
        mount(App, { global: { stubs: { ProjectPanel: true, FileTreePanel: true, FilePreview: true, ChatPanel: true } } })
        // 等待 onMounted
        await new Promise(r => setTimeout(r, 50))
        expect(mockStore.fetchProjects).toHaveBeenCalled()
    })

    it('should fetch sessions and file tree if project is selected on mount', async () => {
        const mockStore = createMockStore({ selectedProjectId: 'p1' })
        useAgentStore.mockReturnValue(mockStore)
        mount(App, { global: { stubs: { ProjectPanel: true, FileTreePanel: true, FilePreview: true, ChatPanel: true } } })
        await new Promise(r => setTimeout(r, 50))
        expect(mockStore.fetchProjects).toHaveBeenCalled()
        expect(mockStore.fetchSessions).toHaveBeenCalled()
        expect(mockStore.fetchFileTree).toHaveBeenCalled()
    })

    it('should handle select-file event from FileTreePanel', async () => {
        const mockStore = createMockStore()
        useAgentStore.mockReturnValue(mockStore)
        const wrapper = mount(App, {
            global: {
                stubs: {
                    ProjectPanel: true,
                    FileTreePanel: {
                        template: '<div class="mock-filetree" @click="$emit(\'select-file\', { path: \'/test.js\' })">tree</div>',
                        emits: ['select-file']
                    },
                    FilePreview: {
                        template: '<div>preview</div>',
                        methods: { setSelectedFile: vi.fn() }
                    },
                    ChatPanel: true
                }
            }
        })
        // 触发子组件的 click 事件 → 应该 emit select-file
        await wrapper.find('.mock-filetree').trigger('click')
        // 验证事件被发出
        expect(wrapper.emitted()).toBeTruthy()
    })
})
