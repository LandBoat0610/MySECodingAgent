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
        selectedProjectId: 'p1',
        selectedSessionId: 's1',
        agentRunning: false,
        sessionStatus: 'idle',
        chatMessages: [],
        traceLogs: [],
        finalAnswer: '',
        pendingPlans: [],
        pendingCommandApproval: null,
        pendingLoopApproval: null,
        roundsHasMore: false,
        roundsLoadingOlder: false,
        // 多轮模式相关（组件新增字段）
        plans: [],
        prevRoundPlanIds: new Set(),
        completedRounds: [],
        currentRoundUserMsg: '',
        stateSnapshot: null,
        doSendChat: vi.fn(),
        doPlanAction: vi.fn(),
        doCommandApproval: vi.fn(),
        doContinueApproval: vi.fn(),
        loadOlderRounds: vi.fn(),
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
            // 状态标签显示中文映射后的文本
            expect(wrapper.find('.status-badge').text()).toBe('运行中')
        })

        it('should show status badge with correct class', () => {
            useAgentStore.mockReturnValue(createMockStore({ sessionStatus: 'completed' }))
            const wrapper = mount(ChatPanel)
            expect(wrapper.find('.status-badge').classes()).toContain('completed')
        })

        it('should show command approval dialog whenever a command is pending', () => {
            const store = createMockStore({
                sessionStatus: 'running',
                pendingCommandApproval: {
                    id: 'approve-1',
                    command: 'pytest -q',
                    purpose: '运行测试',
                    status: 'pending',
                },
            })
            useAgentStore.mockReturnValue(store)
            const wrapper = mount(ChatPanel)
            expect(wrapper.find('.command-dialog').exists()).toBe(true)
            expect(wrapper.find('.command-code').text()).toContain('pytest -q')
            expect(wrapper.find('.command-purpose').text()).toContain('运行测试')
        })

        it('should send command revision feedback from dialog', async () => {
            const store = createMockStore({
                pendingCommandApproval: {
                    id: 'approve-1',
                    command: 'npm test',
                    purpose: '运行测试',
                    status: 'pending',
                },
            })
            useAgentStore.mockReturnValue(store)
            const wrapper = mount(ChatPanel)
            await wrapper.find('.command-feedback').setValue('改成 pytest -q')
            await wrapper.find('.btn-revise').trigger('click')
            expect(store.doCommandApproval).toHaveBeenCalledWith('approve-1', 'revise', '改成 pytest -q')
        })
    })

    // ---- 消息渲染（兼容模式）----
    describe('chat messages', () => {
        it('should render user messages', () => {
            useAgentStore.mockReturnValue(createMockStore({
                chatMessages: [{ role: 'user', content: 'Hello' }]
            }))
            const wrapper = mount(ChatPanel)
            const msgs = wrapper.findAll('.message')
            expect(msgs.length).toBeGreaterThanOrEqual(1)
            const userMsg = msgs.find(m => m.classes().includes('user'))
            expect(userMsg).toBeTruthy()
            expect(userMsg.find('.message-text').text()).toContain('Hello')
        })

        it('should render assistant messages', () => {
            useAgentStore.mockReturnValue(createMockStore({
                chatMessages: [{ role: 'assistant', content: 'Hi there!' }]
            }))
            const wrapper = mount(ChatPanel)
            const msg = wrapper.find('.message.assistant')
            expect(msg.exists()).toBe(true)
            expect(msg.find('.message-text').text()).toContain('Hi there!')
        })

        it('should not render system messages', () => {
            useAgentStore.mockReturnValue(createMockStore({
                chatMessages: [
                    { role: 'system', content: 'System prompt' },
                    { role: 'user', content: 'User message' }
                ]
            }))
            const wrapper = mount(ChatPanel)
            // 只渲染用户消息，系统消息被过滤
            const msgs = wrapper.findAll('.message')
            expect(msgs.length).toBe(1)
            expect(msgs[0].classes()).toContain('user')
        })
    })

    // ---- 执行时间线（兼容模式）----
    describe('trace logs', () => {
        it('should show timeline section when trace logs exist', () => {
            useAgentStore.mockReturnValue(createMockStore({
                traceLogs: [
                    { phase: 'act', time: '12:00', content: 'Using read_file tool' },
                    { phase: 'observe', time: '12:01', content: 'Result: ok' }
                ]
            }))
            const wrapper = mount(ChatPanel)
            expect(wrapper.find('.agent-timeline').exists()).toBe(true)
        })

        it('should render act card for act phase', () => {
            useAgentStore.mockReturnValue(createMockStore({
                traceLogs: [{ phase: 'act', time: '12:00', content: '{"tool":"read_file","args":{}}' }]
            }))
            const wrapper = mount(ChatPanel)
            expect(wrapper.find('.card-act').exists()).toBe(true)
        })

        it('should attach execute_bash result to the command card', async () => {
            useAgentStore.mockReturnValue(createMockStore({
                traceLogs: [
                    { phase: 'act', time: '12:00', content: 'execute_bash({"command":"pytest -q","purpose":"运行测试"})' },
                    { phase: 'observe', time: '12:01', content: '{"status":"success","output":"100 passed","returncode":0}' }
                ]
            }))
            const wrapper = mount(ChatPanel)
            expect(wrapper.findAll('.card-act')).toHaveLength(1)
            expect(wrapper.findAll('.card-observe')).toHaveLength(0)

            await wrapper.find('.card-act .card-header').trigger('click')
            expect(wrapper.find('.command-attached-result').text()).toContain('100 passed')
        })

        it('should hide timeline when no logs and not running', () => {
            useAgentStore.mockReturnValue(createMockStore({
                chatMessages: [{ role: 'user', content: 'hello' }],
                traceLogs: []
            }))
            const wrapper = mount(ChatPanel)
            expect(wrapper.find('.agent-timeline').exists()).toBe(false)
        })
    })

    // ---- Final Answer ----
    describe('final answer', () => {
        it('should not render a separate final answer card', () => {
            useAgentStore.mockReturnValue(createMockStore({
                finalAnswer: 'Task completed successfully!'
            }))
            const wrapper = mount(ChatPanel)
            expect(wrapper.find('.final-answer-card').exists()).toBe(false)
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

        it('should allow sending when project is selected but no session exists yet', async () => {
            const mockStore = createMockStore({ selectedSessionId: null })
            useAgentStore.mockReturnValue(mockStore)
            const wrapper = mount(ChatPanel)
            const textarea = wrapper.find('.chat-input')
            await textarea.setValue('Message')
            await wrapper.find('.send-btn').trigger('click')
            expect(mockStore.doSendChat).toHaveBeenCalledWith('Message')
        })

        it('should not call doSendChat when no project selected', async () => {
            const mockStore = createMockStore({ selectedProjectId: null, selectedSessionId: null })
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

    // ---- 运行中指示器 ----
    describe('running indicator', () => {
        it('should show running indicator when agent is running in legacy mode', () => {
            useAgentStore.mockReturnValue(createMockStore({
                agentRunning: true,
                // 需要至少一条消息使组件进入兼容模式，以显示运行指示器
                chatMessages: [{ role: 'user', content: 'test' }]
            }))
            const wrapper = mount(ChatPanel)
            expect(wrapper.find('.running-indicator').exists()).toBe(true)
        })

        it('should not show running indicator when agent is idle', () => {
            useAgentStore.mockReturnValue(createMockStore({
                agentRunning: false,
                chatMessages: [{ role: 'user', content: 'test' }]
            }))
            const wrapper = mount(ChatPanel)
            expect(wrapper.find('.running-indicator').exists()).toBe(false)
        })
    })
})
