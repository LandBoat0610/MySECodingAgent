/**
 * components/ChatPanel.test.js
 * 测试聊天面板组件：消息渲染、发送消息、Agent 停止、状态显示、计划弹窗
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import ChatPanel from '../../components/ChatPanel.vue'
import { useAgentStore } from '../../stores/agent.js'

vi.mock('../../stores/agent.js', async () => {
    return { useAgentStore: vi.fn() }
})

vi.mock('../../components/PlanDialog.vue', () => ({
    default: { name: 'PlanDialog', template: '<div class="mock-plan-dialog">Plan Dialog</div>' }
}))

function createMockStore(overrides = {}) {
    return {
        selectedSessionId: 's1',
        agentRunning: false,
        sessionStatus: 'idle',
        chatMessages: [],
        traceLogs: [],
        finalAnswer: '',
        pendingPlans: [],
        doSendChat: vi.fn(),
        doPlanAction: vi.fn(),
        doStopSession: vi.fn(),
        disconnectWebSocket: vi.fn(),
        ...overrides
    }
}

describe('ChatPanel.vue', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        const pinia = createPinia()
        setActivePinia(pinia)
    })

    // ---- 渲染 ----
    describe('rendering', () => {
        it('should show empty state when no messages and no traces', () => {
            useAgentStore.mockReturnValue(createMockStore())
            const wrapper = mount(ChatPanel)
            expect(wrapper.find('.chat-empty').exists()).toBe(true)
            expect(wrapper.find('.empty-title').text()).toBe('Agent Platform')
        })

        it('should show session status badge', () => {
            useAgentStore.mockReturnValue(createMockStore({ sessionStatus: 'running' }))
            const wrapper = mount(ChatPanel)
            expect(wrapper.find('.status-badge').text()).toBe('running')
        })

        it('should show status badge with correct class', () => {
            useAgentStore.mockReturnValue(createMockStore({ sessionStatus: 'completed' }))
            const wrapper = mount(ChatPanel)
            expect(wrapper.find('.status-badge').classes()).toContain('completed')
        })
    })

    // ---- 消息渲染 ----
    describe('chat messages', () => {
        it('should render user messages', () => {
            useAgentStore.mockReturnValue(createMockStore({
                chatMessages: [{ role: 'user', content: 'Hello' }]
            }))
            const wrapper = mount(ChatPanel)
            const msgs = wrapper.findAll('.message')
            expect(msgs).toHaveLength(1)
            expect(msgs[0].classes()).toContain('user')
            expect(msgs[0].find('.message-text').text()).toBe('Hello')
        })

        it('should render assistant messages', () => {
            useAgentStore.mockReturnValue(createMockStore({
                chatMessages: [{ role: 'assistant', content: 'Hi there!' }]
            }))
            const wrapper = mount(ChatPanel)
            const msg = wrapper.find('.message.assistant')
            expect(msg.exists()).toBe(true)
            expect(msg.find('.message-text').text()).toBe('Hi there!')
        })

        it('should render tool calls in messages', () => {
            useAgentStore.mockReturnValue(createMockStore({
                chatMessages: [{
                    role: 'assistant',
                    content: 'Let me do that',
                    tool_calls: [
                        { function: { name: 'read_file' } },
                        { function: { name: 'write_file' } }
                    ]
                }]
            }))
            const wrapper = mount(ChatPanel)
            const toolCalls = wrapper.findAll('.tool-call-item')
            expect(toolCalls).toHaveLength(2)
            expect(toolCalls[0].text()).toContain('read_file')
            expect(toolCalls[1].text()).toContain('write_file')
        })
    })

    // ---- 执行追踪 ----
    describe('trace logs', () => {
        it('should show trace section when logs exist', () => {
            useAgentStore.mockReturnValue(createMockStore({
                traceLogs: [
                    { phase: 'plan', time: '12:00', content: 'Planning...' },
                    { phase: 'exec', time: '12:01', content: 'Executing...' }
                ]
            }))
            const wrapper = mount(ChatPanel)
            expect(wrapper.find('.trace-section').exists()).toBe(true)
            expect(wrapper.find('.trace-header').text()).toContain('2 steps')
        })

        it('should toggle trace body on header click', async () => {
            useAgentStore.mockReturnValue(createMockStore({
                traceLogs: [{ phase: 'plan', time: '12:00', content: 'Step 1' }]
            }))
            const wrapper = mount(ChatPanel)
            expect(wrapper.find('.trace-body').exists()).toBe(true) // showTrace default true
            await wrapper.find('.trace-header').trigger('click')
            expect(wrapper.find('.trace-body').exists()).toBe(false)
            await wrapper.find('.trace-header').trigger('click')
            expect(wrapper.find('.trace-body').exists()).toBe(true)
        })

        it('should render trace phase with correct class', () => {
            useAgentStore.mockReturnValue(createMockStore({
                traceLogs: [{ phase: 'exec', time: '12:01', content: 'Running' }]
            }))
            const wrapper = mount(ChatPanel)
            expect(wrapper.find('.trace-phase.exec').exists()).toBe(true)
        })

        it('should hide trace section when no logs', () => {
            useAgentStore.mockReturnValue(createMockStore({ traceLogs: [] }))
            const wrapper = mount(ChatPanel)
            expect(wrapper.find('.trace-section').exists()).toBe(false)
        })
    })

    // ---- Final Answer ----
    describe('final answer', () => {
        it('should show final answer when present', () => {
            useAgentStore.mockReturnValue(createMockStore({
                finalAnswer: 'Task completed successfully!'
            }))
            const wrapper = mount(ChatPanel)
            expect(wrapper.find('.final-answer').exists()).toBe(true)
            expect(wrapper.find('.final-answer-content').text()).toBe('Task completed successfully!')
        })

        it('should hide final answer when empty', () => {
            useAgentStore.mockReturnValue(createMockStore({ finalAnswer: '' }))
            const wrapper = mount(ChatPanel)
            expect(wrapper.find('.final-answer').exists()).toBe(false)
        })
    })

    // ---- 发送消息 ----
    describe('send message', () => {
        it('should call doSendChat on send button click', async () => {
            const mockStore = createMockStore()
            useAgentStore.mockReturnValue(mockStore)
            const wrapper = mount(ChatPanel)
            const textarea = wrapper.find('.chat-input')
            await textarea.setValue('Do something')
            await wrapper.find('.send-btn').trigger('click')
            expect(mockStore.doSendChat).toHaveBeenCalledWith('Do something')
        })

        it('should call doSendChat on Enter key', async () => {
            const mockStore = createMockStore()
            useAgentStore.mockReturnValue(mockStore)
            const wrapper = mount(ChatPanel)
            const textarea = wrapper.find('.chat-input')
            await textarea.setValue('Quick task')
            await textarea.trigger('keydown.enter.exact')
            expect(mockStore.doSendChat).toHaveBeenCalledWith('Quick task')
        })

        it('should clear input after send', async () => {
            const mockStore = createMockStore()
            mockStore.doSendChat.mockResolvedValue({ status: 'running' })
            useAgentStore.mockReturnValue(mockStore)
            const wrapper = mount(ChatPanel)
            const textarea = wrapper.find('.chat-input')
            await textarea.setValue('Clear me')
            await wrapper.find('.send-btn').trigger('click')
            await wrapper.vm.$nextTick()
            expect(textarea.element.value).toBe('')
        })

        it('should not call doSendChat when input is empty', async () => {
            const mockStore = createMockStore()
            useAgentStore.mockReturnValue(mockStore)
            const wrapper = mount(ChatPanel)
            await wrapper.find('.send-btn').trigger('click')
            expect(mockStore.doSendChat).not.toHaveBeenCalled()
        })

        it('should not call doSendChat when no session selected', async () => {
            const mockStore = createMockStore({ selectedSessionId: null })
            useAgentStore.mockReturnValue(mockStore)
            const wrapper = mount(ChatPanel)
            const textarea = wrapper.find('.chat-input')
            await textarea.setValue('Message')
            expect(textarea.attributes('disabled')).toBeDefined()
        })

        it('should not call doSendChat when agent is running', async () => {
            const mockStore = createMockStore({ agentRunning: true })
            useAgentStore.mockReturnValue(mockStore)
            const wrapper = mount(ChatPanel)
            const textarea = wrapper.find('.chat-input')
            await textarea.setValue('Message')
            expect(textarea.attributes('disabled')).toBeDefined()
        })

        it('should restore input on send failure', async () => {
            const mockStore = createMockStore()
            mockStore.doSendChat.mockRejectedValue(new Error('Failed'))
            useAgentStore.mockReturnValue(mockStore)
            const wrapper = mount(ChatPanel)
            const textarea = wrapper.find('.chat-input')
            await textarea.setValue('Will fail')
            await wrapper.find('.send-btn').trigger('click')
            await wrapper.vm.$nextTick()
            await wrapper.vm.$nextTick()
            // input should be restored
            expect(textarea.element.value).toBe('Will fail')
        })
    })

    // ---- Stop Agent ----
    describe('stop agent', () => {
        it('should show Stop button when agent is running', () => {
            useAgentStore.mockReturnValue(createMockStore({ agentRunning: true }))
            const wrapper = mount(ChatPanel)
            expect(wrapper.find('.btn-danger').exists()).toBe(true)
        })

        it('should not show Stop button when agent is not running', () => {
            useAgentStore.mockReturnValue(createMockStore({ agentRunning: false }))
            const wrapper = mount(ChatPanel)
            expect(wrapper.find('.btn-danger').exists()).toBe(false)
        })

        it('should call doStopSession on Stop button click', async () => {
            const mockStore = createMockStore({
                agentRunning: true
            })
            mockStore.doStopSession.mockResolvedValue(undefined)
            useAgentStore.mockReturnValue(mockStore)
            const wrapper = mount(ChatPanel)
            await wrapper.find('.btn-danger').trigger('click')
            expect(mockStore.doStopSession).toHaveBeenCalled()
        })
    })

    // ---- 计划弹窗 ----
    describe('plan dialog', () => {
        it('should show PlanDialog when status is awaiting_approval and plans pending', () => {
            useAgentStore.mockReturnValue(createMockStore({
                sessionStatus: 'awaiting_approval',
                pendingPlans: [{ id: 'p1', content: 'Step', status: 'pending' }]
            }))
            const wrapper = mount(ChatPanel)
            expect(wrapper.find('.mock-plan-dialog').exists()).toBe(true)
        })

        it('should not show PlanDialog when no pending plans', () => {
            useAgentStore.mockReturnValue(createMockStore({
                sessionStatus: 'awaiting_approval',
                pendingPlans: []
            }))
            const wrapper = mount(ChatPanel)
            expect(wrapper.find('.mock-plan-dialog').exists()).toBe(false)
        })

        it('should not show PlanDialog when status is not awaiting_approval', () => {
            useAgentStore.mockReturnValue(createMockStore({
                sessionStatus: 'idle',
                pendingPlans: [{ id: 'p1', content: 'Step', status: 'pending' }]
            }))
            const wrapper = mount(ChatPanel)
            expect(wrapper.find('.mock-plan-dialog').exists()).toBe(false)
        })
    })

    // ---- 输入指示器 ----
    describe('typing indicator', () => {
        it('should show typing indicator when agent is running', () => {
            useAgentStore.mockReturnValue(createMockStore({ agentRunning: true }))
            const wrapper = mount(ChatPanel)
            expect(wrapper.find('.typing-indicator').exists()).toBe(true)
        })

        it('should not show typing indicator when agent is idle', () => {
            useAgentStore.mockReturnValue(createMockStore({ agentRunning: false }))
            const wrapper = mount(ChatPanel)
            expect(wrapper.find('.typing-indicator').exists()).toBe(false)
        })
    })
})
