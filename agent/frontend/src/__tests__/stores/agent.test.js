/**
 * stores/agent.test.js
 * 测试 Pinia agent store 的核心逻辑：
 * - 状态管理（项目/会话选择、切换）
 * - API 调用流程（fetchProjects, fetchSessions, doCreateProject 等）
 * - WebSocket 连接与消息处理
 * - 计划交互（doPlanAction, pendingPlans 计算）
 * - 错误处理
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAgentStore } from '../../stores/agent.js'

// Mock API 模块
vi.mock('../../api/index.js', () => ({
    getProjects: vi.fn(),
    createProject: vi.fn(),
    getSessions: vi.fn(),
    createSession: vi.fn(),
    updateSession: vi.fn(),
    deleteSession: vi.fn(),
    clearSession: vi.fn(),
    getSessionState: vi.fn(),
    sendChat: vi.fn(),
    getPlans: vi.fn(),
    planAction: vi.fn(),
    getFileTree: vi.fn(),
    stopSession: vi.fn(),
    createWebSocket: vi.fn(),
    getToolSettings: vi.fn(),
    updateToolSettings: vi.fn(),
    getSkills: vi.fn(),
    createSkill: vi.fn(),
    updateSkill: vi.fn(),
    deleteSkill: vi.fn()
}))

// Mock persistence 模块
vi.mock('../../utils/persistence.js', () => ({
    persistProjectId: vi.fn(),
    getPersistedProjectId: vi.fn(() => null),
    persistSessionId: vi.fn(),
    getPersistedSessionId: vi.fn(() => null)
}))

import * as api from '../../api/index.js'

// ---- 辅助函数 ------------------------------------------------

/** 创建 Mock WebSocket 实例 */
function createMockWebSocket() {
    const ws = {
        url: '',
        readyState: 1,
        onopen: null,
        onmessage: null,
        onclose: null,
        onerror: null,
        send: vi.fn(),
        close: vi.fn(),
        _mockMessage(data) {
            if (this.onmessage) this.onmessage({ data: JSON.stringify(data) })
        },
        _mockOpen() {
            if (this.onopen) this.onopen()
        },
        _mockClose(code = 1000) {
            if (this.onclose) this.onclose({ code })
        },
        _mockError(err) {
            if (this.onerror) this.onerror(err)
        }
    }
    return ws
}

/** 创建全新的 store 实例 */
function createStore() {
    const pinia = createPinia()
    setActivePinia(pinia)
    // 每次调用 createWebSocket 都返回一个新的 mock 实例
    api.createWebSocket.mockImplementation(() => createMockWebSocket())
    return useAgentStore()
}

/** Mock API 返回项目列表 */
function mockProjects(projects) {
    api.getProjects.mockResolvedValue(projects)
}

/** Mock API 返回会话列表 */
function mockSessions(sessions) {
    api.getSessions.mockResolvedValue(sessions)
}

// ---- 测试套件 ------------------------------------------------

describe('agent store', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        // 重置 mock 为默认成功返回值
        api.getProjects.mockResolvedValue([])
        api.getSessions.mockResolvedValue([])
        api.getSessionState.mockResolvedValue({ status: 'idle', snapshot: null })
        api.getPlans.mockResolvedValue([])
        api.getFileTree.mockResolvedValue([])
        api.createProject.mockResolvedValue({ id: 'new-proj', name: 'New' })
        api.createSession.mockResolvedValue({ id: 'new-sess', title: 'New Session' })
        api.updateSession.mockResolvedValue({ id: 's1', title: 'Updated', pinned: false, status: 'idle' })
        api.deleteSession.mockResolvedValue({ status: 'deleted' })
        api.clearSession.mockResolvedValue({ status: 'cleared' })
        api.sendChat.mockResolvedValue({ status: 'running' })
        api.planAction.mockResolvedValue({ status: 'approved' })
        api.getToolSettings.mockResolvedValue({ tools: [] })
        api.updateToolSettings.mockResolvedValue({ tools: [] })
        api.getSkills.mockResolvedValue({ skills: [] })
        api.createSkill.mockResolvedValue({ id: 'sk1', name: 'Skill', content: 'Do this', enabled: true })
        api.updateSkill.mockResolvedValue({ id: 'sk1', name: 'Skill 2', content: 'Do that', enabled: true })
        api.deleteSkill.mockResolvedValue({ status: 'deleted' })
    })

    // ============================================================
    // 初始状态
    // ============================================================
    describe('initial state', () => {
        it('should have correct default values', () => {
            const store = createStore()
            expect(store.projects).toEqual([])
            expect(store.selectedProjectId).toBeNull()
            expect(store.sessions).toEqual([])
            expect(store.selectedSessionId).toBeNull()
            expect(store.sessionStatus).toBe('idle')
            expect(store.fileTree).toEqual([])
            expect(store.plans).toEqual([])
            expect(store.traceLogs).toEqual([])
            expect(store.chatMessages).toEqual([])
            expect(store.finalAnswer).toBe('')
            expect(store.agentRunning).toBe(false)
            expect(store.agentRunStartedAt).toBeNull()
            expect(store.livePerf.tokensTotal).toBe(0)
            expect(store.wsConnection).toBeNull()
            expect(store.loading).toBe(false)
            expect(store.error).toBeNull()
        })

        it('should compute selectedProject as null when no project selected', () => {
            const store = createStore()
            expect(store.selectedProject).toBeNull()
        })

        it('should compute selectedSession as null when no session selected', () => {
            const store = createStore()
            expect(store.selectedSession).toBeNull()
        })

        it('should compute pendingPlans as empty array', () => {
            const store = createStore()
            expect(store.pendingPlans).toEqual([])
        })
    })

    // ============================================================
    // fetchProjects
    // ============================================================
    describe('fetchProjects', () => {
        it('should populate projects on success', async () => {
            const store = createStore()
            mockProjects([{ id: 'p1', name: 'Project 1' }, { id: 'p2', name: 'Project 2' }])
            await store.fetchProjects()
            expect(store.projects).toHaveLength(2)
            expect(store.projects[0].name).toBe('Project 1')
            expect(store.loading).toBe(false)
        })

        it('should clear selectedProjectId if it no longer exists', async () => {
            const store = createStore()
            store.selectedProjectId = 'deleted-project'
            mockProjects([{ id: 'other', name: 'Other' }])
            await store.fetchProjects()
            expect(store.selectedProjectId).toBeNull()
        })

        it('should set error on failure', async () => {
            const store = createStore()
            api.getProjects.mockRejectedValue(new Error('Network error'))
            await store.fetchProjects()
            expect(store.error).toBeTruthy()
            expect(store.loading).toBe(false)
        })

        it('should set loading to true while fetching', async () => {
            const store = createStore()
            let loadingDuringCall = false
            api.getProjects.mockImplementation(async () => {
                loadingDuringCall = store.loading
                return []
            })
            await store.fetchProjects()
            expect(loadingDuringCall).toBe(true)
        })
    })

    // ============================================================
    // doCreateProject
    // ============================================================
    describe('doCreateProject', () => {
        it('should add new project to the list and select it', async () => {
            const store = createStore()
            mockProjects([])
            const project = await store.doCreateProject({ name: 'My Project' })
            expect(api.createProject).toHaveBeenCalledWith({ name: 'My Project' })
            expect(store.projects).toHaveLength(1)
            expect(store.selectedProjectId).toBe('new-proj')
            expect(project.id).toBe('new-proj')
        })

        it('should throw on failure (no internal error capture)', async () => {
            const store = createStore()
            api.createProject.mockRejectedValue(new Error('Create failed'))
            await expect(store.doCreateProject({ name: 'Bad' })).rejects.toThrow('Create failed')
            // doCreateProject does not catch errors, so store.error stays null
            expect(store.error).toBeNull()
        })
    })

    // ============================================================
    // selectProject
    // ============================================================
    describe('selectProject', () => {
        it('should set selectedProjectId and reset session-related state', async () => {
            const store = createStore()
            store.selectedSessionId = 'old-session'
            store.sessions = [{ id: 's1', title: 'S1' }]
            store.fileTree = [{ path: '/x', type: 'file' }]
            store.chatMessages = [{ role: 'user', content: 'hi' }]
            store.finalAnswer = 'done'
            store.sessionStatus = 'running'

            mockProjects([{ id: 'p1', name: 'P1' }])
            mockSessions([{ id: 's1', title: 'S1' }])

            store.selectProject('p1')

            expect(store.selectedProjectId).toBe('p1')
            expect(store.selectedSessionId).toBeNull()
            expect(store.sessions).toEqual([])  // 先清空再 fetch
            expect(store.fileTree).toEqual([])
            expect(store.chatMessages).toEqual([])
            expect(store.finalAnswer).toBe('')
            expect(store.sessionStatus).toBe('idle')
        })
    })

    // ============================================================
    // fetchSessions
    // ============================================================
    describe('fetchSessions', () => {
        it('should not call API if no project selected', async () => {
            const store = createStore()
            await store.fetchSessions()
            expect(api.getSessions).not.toHaveBeenCalled()
        })

        it('should populate sessions on success', async () => {
            const store = createStore()
            store.selectedProjectId = 'p1'
            mockSessions([{ id: 's1', title: 'Session 1' }])
            await store.fetchSessions()
            expect(store.sessions).toHaveLength(1)
            expect(store.sessions[0].title).toBe('Session 1')
        })

        it('should clear selectedSessionId if it no longer exists', async () => {
            const store = createStore()
            store.selectedProjectId = 'p1'
            store.selectedSessionId = 'deleted-session'
            mockSessions([{ id: 'other', title: 'Other' }])
            await store.fetchSessions()
            expect(store.selectedSessionId).toBeNull()
        })
    })

    // ============================================================
    // doCreateSession
    // ============================================================
    describe('doCreateSession', () => {
        it('should create session and select it', async () => {
            const store = createStore()
            store.selectedProjectId = 'p1'
            const session = await store.doCreateSession('New Chat')
            expect(api.createSession).toHaveBeenCalledWith('p1', { title: 'New Chat' })
            expect(store.sessions).toHaveLength(1)
            expect(store.selectedSessionId).toBe('new-sess')
            expect(session.id).toBe('new-sess')
        })
    })

    // ============================================================
    // selectSession
    // ============================================================
    describe('selectSession', () => {
        it('should set selectedSessionId and call restoreSessionState', async () => {
            const store = createStore()
            store.selectedProjectId = 'p1'
            api.getSessionState.mockResolvedValue({ status: 'idle', snapshot: { messages: [] } })

            await store.selectSession('s1')

            expect(store.selectedSessionId).toBe('s1')
            expect(api.getSessionState).toHaveBeenCalledWith('p1', 's1')
            expect(store.sessionStatus).toBe('idle')
        })

        it('should restore chat messages from snapshot', async () => {
            const store = createStore()
            store.selectedProjectId = 'p1'
            api.getSessionState.mockResolvedValue({
                status: 'completed',
                snapshot: {
                    messages: [
                        { role: 'user', content: 'hello' },
                        { role: 'assistant', content: 'hi there', tool_calls: null }
                    ],
                    final_answer: 'task done',
                    trace: [{ phase: 'plan', content: 'step 1' }]
                }
            })

            await store.selectSession('s1')

            expect(store.chatMessages).toHaveLength(2)
            expect(store.chatMessages[0].role).toBe('user')
            expect(store.finalAnswer).toBe('task done')
            expect(store.traceLogs).toHaveLength(1)
        })
    })

    // ============================================================
    // fetchFileTree
    // ============================================================
    describe('fetchFileTree', () => {
        it('should not call API if no project selected', async () => {
            const store = createStore()
            await store.fetchFileTree()
            expect(api.getFileTree).not.toHaveBeenCalled()
        })

        it('should populate fileTree on success', async () => {
            const store = createStore()
            store.selectedProjectId = 'p1'
            api.getFileTree.mockResolvedValue([
                { path: '/src', type: 'directory', children: [{ path: '/src/main.js', type: 'file' }] }
            ])
            await store.fetchFileTree()
            expect(store.fileTree).toHaveLength(1)
            expect(store.fileTree[0].type).toBe('directory')
        })

        it('should set error on failure', async () => {
            const store = createStore()
            store.selectedProjectId = 'p1'
            api.getFileTree.mockRejectedValue(new Error('Not found'))
            await store.fetchFileTree()
            expect(store.error).toBeTruthy()
        })
    })

    // ============================================================
    // fetchPlans
    // ============================================================
    describe('fetchPlans', () => {
        it('should not call API without project or session', async () => {
            const store = createStore()
            await store.fetchPlans()
            expect(api.getPlans).not.toHaveBeenCalled()
        })

        it('should populate plans', async () => {
            const store = createStore()
            store.selectedProjectId = 'p1'
            store.selectedSessionId = 's1'
            api.getPlans.mockResolvedValue([
                { id: 'plan-1', content: 'Step 1', status: 'pending', created_at: '2025-01-01' }
            ])
            await store.fetchPlans()
            expect(store.plans).toHaveLength(1)
        })

        it('pendingPlans should filter by status pending', async () => {
            const store = createStore()
            store.selectedProjectId = 'p1'
            store.selectedSessionId = 's1'
            api.getPlans.mockResolvedValue([
                { id: 'plan-1', content: 'Step 1', status: 'pending' },
                { id: 'plan-2', content: 'Step 2', status: 'approved' }
            ])
            await store.fetchPlans()
            expect(store.pendingPlans).toHaveLength(1)
            expect(store.pendingPlans[0].id).toBe('plan-1')
        })
    })

    // ============================================================
    // WebSocket 管理
    // ============================================================
    describe('WebSocket', () => {
        it('should not connect if no project or session selected', () => {
            const store = createStore()
            store.connectWebSocket()
            expect(api.createWebSocket).not.toHaveBeenCalled()
            expect(store.agentRunning).toBe(false)
        })

        it('should create WebSocket and set agentRunning', () => {
            const store = createStore()
            store.selectedProjectId = 'p1'
            store.selectedSessionId = 's1'
            store.connectWebSocket()
            expect(api.createWebSocket).toHaveBeenCalledWith('p1', 's1')
            expect(store.agentRunning).toBe(true)
            expect(store.wsConnection).not.toBeNull()
        })

        it('should close existing connection before creating new one', () => {
            const store = createStore()
            store.selectedProjectId = 'p1'
            store.selectedSessionId = 's1'

            // first connection
            store.connectWebSocket()
            const firstWs = store.wsConnection
            const closeSpy = vi.spyOn(firstWs, 'close')

            // second connection
            store.connectWebSocket()
            expect(closeSpy).toHaveBeenCalled()
            expect(store.wsConnection).not.toBe(firstWs)
        })

        it('should record run start time on ws phase start without clearing trace', () => {
            const store = createStore()
            store.selectedProjectId = 'p1'
            store.selectedSessionId = 's1'
            store.traceLogs.push({ phase: 'old', content: 'x' })
            store.connectWebSocket()

            store.wsConnection._mockMessage({
                phase: 'start',
                message: 'Agent 正在执行...'
            })

            // traceLogs 在 start 阶段不会被清空，避免重连时覆盖已有轨迹
            expect(store.traceLogs).toHaveLength(1)
            expect(store.traceLogs[0]).toEqual({ phase: 'old', content: 'x' })
            expect(store.agentRunStartedAt).toBeTruthy()
            expect(typeof store.agentRunStartedAt).toBe('number')
            expect(store.livePerf.tokensTotal).toBe(0)
        })

        it('should handle ws.onmessage trace events', () => {
            const store = createStore()
            store.selectedProjectId = 'p1'
            store.selectedSessionId = 's1'
            store.connectWebSocket()

            store.wsConnection._mockMessage({
                type: 'trace',
                data: { phase: 'plan', content: 'thinking...' }
            })
            expect(store.traceLogs).toHaveLength(1)
            expect(store.traceLogs[0].content).toBe('thinking...')
        })

        it('should handle ws.onmessage done event', () => {
            const store = createStore()
            store.selectedProjectId = 'p1'
            store.selectedSessionId = 's1'
            store.connectWebSocket()

            store.wsConnection._mockMessage({
                phase: 'done',
                final_answer: 'all done',
                status: 'completed'
            })

            expect(store.agentRunning).toBe(false)
            expect(store.finalAnswer).toBe('all done')
            expect(store.sessionStatus).toBe('completed')
        })

        it('should handle ws.onmessage cancelled event', () => {
            const store = createStore()
            store.selectedProjectId = 'p1'
            store.selectedSessionId = 's1'
            store.connectWebSocket()

            store.wsConnection._mockMessage({
                phase: 'cancelled'
            })

            expect(store.agentRunning).toBe(false)
            expect(store.sessionStatus).toBe('stopped')
        })

        it('should handle ws.onmessage error', () => {
            const store = createStore()
            store.selectedProjectId = 'p1'
            store.selectedSessionId = 's1'
            store.connectWebSocket()

            store.wsConnection._mockMessage({
                error: 'Something went wrong'
            })

            expect(store.error).toBeTruthy()
            expect(store.agentRunning).toBe(false)
        })

        it('should disconnect and clean up', () => {
            const store = createStore()
            store.selectedProjectId = 'p1'
            store.selectedSessionId = 's1'
            store.connectWebSocket()

            const ws = store.wsConnection
            const closeSpy = vi.spyOn(ws, 'close')

            store.disconnectWebSocket()
            expect(closeSpy).toHaveBeenCalled()
            expect(store.agentRunning).toBe(false)
            expect(store.wsConnection).toBeNull()
        })

        it('should handle ws.onclose and attempt reconnect when status is running', async () => {
            vi.useFakeTimers()
            const store = createStore()
            store.selectedProjectId = 'p1'
            store.selectedSessionId = 's1'
            store.sessionStatus = 'running'
            store.connectWebSocket()

            // manually trigger close (unintentional, wsIntentionalClose=false)
            store.wsConnection.onclose()

            // wsConnection is set to null by handler
            expect(store.wsConnection).toBeNull()
            // agentRunning stays true because reconnect is pending
            expect(store.agentRunning).toBe(true)

            // after 2s backoff, connectWebSocket is called again
            await vi.advanceTimersByTimeAsync(2000)
            expect(api.createWebSocket).toHaveBeenCalledTimes(2) // first connect + reconnect

            vi.useRealTimers()
        })

        it('should handle ws.onerror and set agentRunning to false', () => {
            const store = createStore()
            store.selectedProjectId = 'p1'
            store.selectedSessionId = 's1'
            store.connectWebSocket()

            store.wsConnection.onerror(new Error('Connection refused'))
            expect(store.agentRunning).toBe(false)
        })
    })

    // ============================================================
    // doSendChat
    // ============================================================
    describe('doSendChat', () => {
        it('should push user message and call sendChat API', async () => {
            const store = createStore()
            store.selectedProjectId = 'p1'
            store.selectedSessionId = 's1'
            api.sendChat.mockResolvedValue({ status: 'running' })

            await store.doSendChat('Hello agent')

            expect(store.chatMessages).toHaveLength(1)
            expect(store.chatMessages[0].role).toBe('user')
            expect(store.chatMessages[0].content).toBe('Hello agent')
            expect(api.sendChat).toHaveBeenCalledWith('p1', 's1', 'Hello agent')
            expect(store.sessionStatus).toBe('running')
        })

        it('should auto-create a session before sending the first message', async () => {
            const store = createStore()
            store.selectedProjectId = 'p1'
            store.selectedSessionId = null
            api.createSession.mockResolvedValue({
                id: 'new-sess',
                project_id: 'p1',
                title: 'Generated title',
                status: 'idle'
            })
            api.sendChat.mockResolvedValue({ session_id: 'new-sess', status: 'running' })

            await store.doSendChat('Build the login page')

            expect(api.createSession).toHaveBeenCalledWith('p1', { initial_message: 'Build the login page' })
            expect(store.selectedSessionId).toBe('new-sess')
            expect(store.sessions[0].title).toBe('Generated title')
            expect(api.sendChat).toHaveBeenCalledWith('p1', 'new-sess', 'Build the login page')
        })

        it('should start a new session when sending after the current session was stopped', async () => {
            const store = createStore()
            store.selectedProjectId = 'p1'
            store.selectedSessionId = 'stopped-sess'
            store.sessionStatus = 'stopped'
            api.createSession.mockResolvedValue({
                id: 'new-sess',
                project_id: 'p1',
                title: 'New title',
                status: 'idle'
            })
            api.sendChat.mockResolvedValue({ session_id: 'new-sess', status: 'running' })

            await store.doSendChat('Continue with a new task')

            expect(api.createSession).toHaveBeenCalledWith('p1', { initial_message: 'Continue with a new task' })
            expect(api.sendChat).toHaveBeenCalledWith('p1', 'new-sess', 'Continue with a new task')
        })

        it('should remove user message and throw on failure', async () => {
            const store = createStore()
            store.selectedProjectId = 'p1'
            store.selectedSessionId = 's1'
            api.sendChat.mockRejectedValue(new Error('Send failed'))

            await expect(store.doSendChat('Bad message')).rejects.toThrow()
            expect(store.chatMessages).toHaveLength(0) // message rolled back
            expect(store.error).toBeTruthy()
        })
    })

    // ============================================================
    // doPlanAction
    // ============================================================
    describe('doPlanAction', () => {
        it('should call planAction API and update plan status', async () => {
            const store = createStore()
            store.selectedProjectId = 'p1'
            store.selectedSessionId = 's1'
            store.plans = [{ id: 'plan-1', content: 'Step 1', status: 'pending' }]
            api.planAction.mockResolvedValue({ status: 'approved' })

            await store.doPlanAction('plan-1', 'agree')

            expect(api.planAction).toHaveBeenCalledWith('p1', 's1', 'plan-1', 'agree', '')
            expect(store.plans[0].status).toBe('approved')
        })

        it('should throw and set error on failure', async () => {
            const store = createStore()
            store.selectedProjectId = 'p1'
            store.selectedSessionId = 's1'
            store.plans = [{ id: 'plan-1', content: 'Step 1', status: 'pending' }]
            api.planAction.mockRejectedValue(new Error('Action failed'))

            await expect(store.doPlanAction('plan-1', 'stop')).rejects.toThrow()
            expect(store.error).toBeTruthy()
        })
    })

    // ============================================================
    // addAssistantMessage
    // ============================================================
    describe('addAssistantMessage', () => {
        it('should add an assistant message to chatMessages', () => {
            const store = createStore()
            store.addAssistantMessage('Hello from assistant')
            expect(store.chatMessages).toHaveLength(1)
            expect(store.chatMessages[0].role).toBe('assistant')
            expect(store.chatMessages[0].content).toBe('Hello from assistant')
        })
    })

    // ============================================================
    // error 管理
    // ============================================================
    describe('error handling', () => {
        it('should have error initially null', () => {
            const store = createStore()
            expect(store.error).toBeNull()
        })

        it('should set error when fetchProjects fails', async () => {
            const store = createStore()
            api.getProjects.mockRejectedValue(new Error('Network error'))
            await store.fetchProjects()
            expect(store.error).toBeTruthy()
            expect(typeof store.error).toBe('string')
        })

        it('should set error from axios-like response on fetchProjects failure', async () => {
            const store = createStore()
            api.getProjects.mockRejectedValue({ response: { data: { detail: 'API error detail' } } })
            await store.fetchProjects()
            expect(store.error).toBe('API error detail')
        })

        it('clearError should reset error to null', async () => {
            const store = createStore()
            api.getProjects.mockRejectedValue(new Error('Some error'))
            await store.fetchProjects()
            expect(store.error).toBeTruthy()
            store.clearError()
            expect(store.error).toBeNull()
        })

        it('setError handles string errors (via fetchFileTree)', async () => {
            const store = createStore()
            store.selectedProjectId = 'p1'
            api.getFileTree.mockRejectedValue('Plain string error')
            await store.fetchFileTree()
            expect(store.error).toBe('Plain string error')
        })
    })
})
