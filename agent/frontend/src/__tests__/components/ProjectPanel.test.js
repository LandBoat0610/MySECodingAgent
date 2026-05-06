/**
 * components/ProjectPanel.test.js
 * 测试项目面板组件：项目列表、创建项目、会话列表、创建会话
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import ProjectPanel from '../../components/ProjectPanel.vue'
import { useAgentStore } from '../../stores/agent.js'

vi.mock('../../stores/agent.js', async () => {
    return { useAgentStore: vi.fn() }
})

function createMockStore(overrides = {}) {
    return {
        projects: [],
        selectedProjectId: null,
        sessions: [],
        selectedSessionId: null,
        loading: false,
        error: null,
        selectProject: vi.fn(),
        selectSession: vi.fn(),
        doCreateProject: vi.fn(),
        doCreateSession: vi.fn(),
        clearError: vi.fn(),
        ...overrides
    }
}

describe('ProjectPanel.vue', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        const pinia = createPinia()
        setActivePinia(pinia)
    })

    // ---- 项目列表 ----
    describe('project list', () => {
        it('should show empty hint when no projects and not loading', () => {
            useAgentStore.mockReturnValue(createMockStore())
            const wrapper = mount(ProjectPanel)
            expect(wrapper.find('.empty-hint').text()).toContain('No projects')
        })

        it('should render project items', () => {
            useAgentStore.mockReturnValue(createMockStore({
                projects: [
                    { id: 'p1', name: 'Project Alpha' },
                    { id: 'p2', name: 'Project Beta' }
                ]
            }))
            const wrapper = mount(ProjectPanel)
            const items = wrapper.findAll('.project-item')
            expect(items).toHaveLength(2)
            expect(items[0].text()).toContain('Project Alpha')
            expect(items[1].text()).toContain('Project Beta')
        })

        it('should mark selected project as active', () => {
            useAgentStore.mockReturnValue(createMockStore({
                projects: [{ id: 'p1', name: 'Alpha' }, { id: 'p2', name: 'Beta' }],
                selectedProjectId: 'p2'
            }))
            const wrapper = mount(ProjectPanel)
            const items = wrapper.findAll('.project-item')
            expect(items[0].classes()).not.toContain('active')
            expect(items[1].classes()).toContain('active')
        })

        it('should call store.selectProject on click', async () => {
            const mockStore = createMockStore({
                projects: [{ id: 'p1', name: 'Alpha' }]
            })
            useAgentStore.mockReturnValue(mockStore)
            const wrapper = mount(ProjectPanel)
            await wrapper.find('.project-item').trigger('click')
            expect(mockStore.selectProject).toHaveBeenCalledWith('p1')
        })
    })

    // ---- 创建项目表单 ----
    describe('create project form', () => {
        it('should toggle new project form on + button click', async () => {
            useAgentStore.mockReturnValue(createMockStore())
            const wrapper = mount(ProjectPanel)
            expect(wrapper.find('.new-project-form').exists()).toBe(false)
            await wrapper.findAll('.btn-icon')[0].trigger('click')
            expect(wrapper.find('.new-project-form').exists()).toBe(true)
        })

        it('should disable Create button when name is empty', async () => {
            useAgentStore.mockReturnValue(createMockStore())
            const wrapper = mount(ProjectPanel)
            await wrapper.findAll('.btn-icon')[0].trigger('click')
            const createBtn = wrapper.find('.btn-primary')
            expect(createBtn.attributes('disabled')).toBeDefined()
        })

        it('should call doCreateProject on form submit', async () => {
            const mockStore = createMockStore()
            useAgentStore.mockReturnValue(mockStore)
            const wrapper = mount(ProjectPanel)
            await wrapper.findAll('.btn-icon')[0].trigger('click')
            const input = wrapper.find('.new-project-form input')
            await input.setValue('New Project')
            await wrapper.find('.btn-primary').trigger('click')
            expect(mockStore.doCreateProject).toHaveBeenCalledWith({ name: 'New Project' })
        })

        it('should close form on Cancel click', async () => {
            useAgentStore.mockReturnValue(createMockStore())
            const wrapper = mount(ProjectPanel)
            await wrapper.findAll('.btn-icon')[0].trigger('click')
            await wrapper.find('.btn-ghost').trigger('click')
            expect(wrapper.find('.new-project-form').exists()).toBe(false)
        })

        it('should submit on Enter key', async () => {
            const mockStore = createMockStore()
            useAgentStore.mockReturnValue(mockStore)
            const wrapper = mount(ProjectPanel)
            await wrapper.findAll('.btn-icon')[0].trigger('click')
            const input = wrapper.find('.new-project-form input')
            await input.setValue('Enter Project')
            await input.trigger('keyup.enter')
            expect(mockStore.doCreateProject).toHaveBeenCalledWith({ name: 'Enter Project' })
        })
    })

    // ---- 会话列表 (sessions) ----
    describe('sessions', () => {
        it('should show session section only when project is selected', () => {
            useAgentStore.mockReturnValue(createMockStore({ selectedProjectId: 'p1' }))
            const wrapper = mount(ProjectPanel)
            expect(wrapper.find('.session-section').exists()).toBe(true)
        })

        it('should hide session section when no project selected', () => {
            useAgentStore.mockReturnValue(createMockStore({ selectedProjectId: null }))
            const wrapper = mount(ProjectPanel)
            expect(wrapper.find('.session-section').exists()).toBe(false)
        })

        it('should show empty hint when no sessions', () => {
            useAgentStore.mockReturnValue(createMockStore({
                selectedProjectId: 'p1',
                sessions: []
            }))
            const wrapper = mount(ProjectPanel)
            // 第二个 empty-hint
            const hints = wrapper.findAll('.empty-hint')
            expect(hints.length).toBeGreaterThanOrEqual(1)
            expect(hints[hints.length - 1].text()).toContain('No sessions')
        })

        it('should render session items', () => {
            useAgentStore.mockReturnValue(createMockStore({
                selectedProjectId: 'p1',
                sessions: [
                    { id: 's1', title: 'Chat 1', status: 'idle', created_at: '2025-01-01T00:00:00Z' },
                    { id: 's2', title: 'Chat 2', status: 'running', created_at: null }
                ]
            }))
            const wrapper = mount(ProjectPanel)
            const items = wrapper.findAll('.session-item')
            expect(items).toHaveLength(2)
            expect(items[0].text()).toContain('Chat 1')
            expect(items[1].text()).toContain('Chat 2')
        })

        it('should mark selected session as active', () => {
            useAgentStore.mockReturnValue(createMockStore({
                selectedProjectId: 'p1',
                sessions: [{ id: 's1', title: 'S1' }, { id: 's2', title: 'S2' }],
                selectedSessionId: 's1'
            }))
            const wrapper = mount(ProjectPanel)
            const items = wrapper.findAll('.session-item')
            expect(items[0].classes()).toContain('active')
            expect(items[1].classes()).not.toContain('active')
        })

        it('should call store.selectSession on click', async () => {
            const mockStore = createMockStore({
                selectedProjectId: 'p1',
                sessions: [{ id: 's1', title: 'Chat', status: 'idle', created_at: '' }]
            })
            useAgentStore.mockReturnValue(mockStore)
            const wrapper = mount(ProjectPanel)
            await wrapper.find('.session-item').trigger('click')
            expect(mockStore.selectSession).toHaveBeenCalledWith('s1')
        })
    })

    // ---- 创建会话表单 ----
    describe('create session form', () => {
        it('should toggle new session form', async () => {
            useAgentStore.mockReturnValue(createMockStore({ selectedProjectId: 'p1' }))
            const wrapper = mount(ProjectPanel)
            // 第二个 btn-icon (+)
            const sessionButtons = wrapper.findAll('.btn-icon')
            await sessionButtons[sessionButtons.length - 1].trigger('click')
            expect(wrapper.find('.new-session-form').exists()).toBe(true)
        })

        it('should call doCreateSession on submit', async () => {
            const mockStore = createMockStore({ selectedProjectId: 'p1' })
            useAgentStore.mockReturnValue(mockStore)
            const wrapper = mount(ProjectPanel)
            const sessionButtons = wrapper.findAll('.btn-icon')
            await sessionButtons[sessionButtons.length - 1].trigger('click')
            const input = wrapper.find('.new-session-form input')
            await input.setValue('New Session')
            await wrapper.find('.new-session-form .btn-primary').trigger('click')
            expect(mockStore.doCreateSession).toHaveBeenCalledWith('New Session')
        })
    })

    // ---- 错误横幅 ----
    describe('error banner', () => {
        it('should show error banner when store has error', () => {
            useAgentStore.mockReturnValue(createMockStore({ error: 'Something went wrong' }))
            const wrapper = mount(ProjectPanel)
            expect(wrapper.find('.error-banner').exists()).toBe(true)
            expect(wrapper.find('.error-banner').text()).toContain('Something went wrong')
        })

        it('should hide error banner when no error', () => {
            useAgentStore.mockReturnValue(createMockStore({ error: null }))
            const wrapper = mount(ProjectPanel)
            expect(wrapper.find('.error-banner').exists()).toBe(false)
        })

        it('should call clearError on close button click', async () => {
            const mockStore = createMockStore({ error: 'Error!' })
            useAgentStore.mockReturnValue(mockStore)
            const wrapper = mount(ProjectPanel)
            await wrapper.find('.error-banner .btn-icon').trigger('click')
            expect(mockStore.clearError).toHaveBeenCalled()
        })
    })
})
