/**
 * api/index.test.js
 * 测试 API 层的请求函数 —— 验证 URL 构建与参数传递
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import axios from 'axios'

// Mock axios
vi.mock('axios', () => {
    const mockAxios = {
        create: vi.fn(() => mockAxios),
        get: vi.fn(),
        post: vi.fn(),
        interceptors: {
            request: { use: vi.fn() },
            response: { use: vi.fn() }
        }
    }
    return { default: mockAxios }
})

// 动态导入以触发 mock
const api = await import('../../api/index.js')

describe('API layer', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    describe('getProjects', () => {
        it('should call GET /projects', async () => {
            axios.get.mockResolvedValue({ data: [{ id: '1', name: 'Test' }] })
            const result = await api.getProjects()
            expect(axios.get).toHaveBeenCalledWith('/projects')
            expect(result).toEqual([{ id: '1', name: 'Test' }])
        })
    })

    describe('createProject', () => {
        it('should call POST /projects with data', async () => {
            const newProject = { name: 'New Project' }
            axios.post.mockResolvedValue({ data: { id: '2', name: 'New Project' } })
            const result = await api.createProject(newProject)
            expect(axios.post).toHaveBeenCalledWith('/projects', newProject)
            expect(result).toEqual({ id: '2', name: 'New Project' })
        })
    })

    describe('getSessions', () => {
        it('should call GET /projects/:projectId/sessions', async () => {
            axios.get.mockResolvedValue({ data: [] })
            await api.getSessions('proj-1')
            expect(axios.get).toHaveBeenCalledWith('/projects/proj-1/sessions')
        })
    })

    describe('createSession', () => {
        it('should call POST /projects/:projectId/sessions with data', async () => {
            axios.post.mockResolvedValue({ data: { id: 's1', title: 'Test' } })
            await api.createSession('proj-1', { title: 'Test' })
            expect(axios.post).toHaveBeenCalledWith('/projects/proj-1/sessions', { title: 'Test' })
        })
    })

    describe('getSessionState', () => {
        it('should call GET /projects/:projectId/sessions/:sessionId/state', async () => {
            axios.get.mockResolvedValue({ data: { status: 'idle', snapshot: null } })
            const result = await api.getSessionState('proj-1', 'sess-1')
            expect(axios.get).toHaveBeenCalledWith('/projects/proj-1/sessions/sess-1/state')
            expect(result).toEqual({ status: 'idle', snapshot: null })
        })
    })

    describe('sendChat', () => {
        it('should call POST with message body', async () => {
            axios.post.mockResolvedValue({ data: { status: 'running' } })
            const result = await api.sendChat('proj-1', 'sess-1', 'Hello')
            expect(axios.post).toHaveBeenCalledWith(
                '/projects/proj-1/sessions/sess-1/chat',
                { message: 'Hello' }
            )
            expect(result).toEqual({ status: 'running' })
        })
    })

    describe('getPlans', () => {
        it('should call GET /projects/:projectId/sessions/:sessionId/plan', async () => {
            axios.get.mockResolvedValue({ data: [] })
            await api.getPlans('proj-1', 'sess-1')
            expect(axios.get).toHaveBeenCalledWith('/projects/proj-1/sessions/sess-1/plan')
        })
    })

    describe('planAction', () => {
        it('should call POST with action body', async () => {
            axios.post.mockResolvedValue({ data: { status: 'approved' } })
            const result = await api.planAction('proj-1', 'sess-1', 'plan-1', 'agree')
            expect(axios.post).toHaveBeenCalledWith(
                '/projects/proj-1/sessions/sess-1/plan/plan-1/action',
                { action: 'agree' }
            )
            expect(result).toEqual({ status: 'approved' })
        })
    })

    describe('getFileTree', () => {
        it('should call GET /projects/:projectId/files', async () => {
            axios.get.mockResolvedValue({ data: [{ path: '/a', type: 'file' }] })
            const result = await api.getFileTree('proj-1')
            expect(axios.get).toHaveBeenCalledWith('/projects/proj-1/files')
            expect(result).toEqual([{ path: '/a', type: 'file' }])
        })
    })

    describe('createWebSocket', () => {
        it('should create WebSocket with correct URL (http)', () => {
            const ws = api.createWebSocket('proj-1', 'sess-1')
            expect(ws.url).toBe('ws://localhost:3000/projects/proj-1/sessions/sess-1/chat/stream')
        })

        it('should create WebSocket with correct URL (https)', () => {
            // 临时修改 location.protocol
            const originalProtocol = window.location.protocol
            Object.defineProperty(window.location, 'protocol', {
                value: 'https:', writable: true, configurable: true
            })
            const ws = api.createWebSocket('proj-2', 'sess-2')
            expect(ws.url).toBe('wss://localhost:3000/projects/proj-2/sessions/sess-2/chat/stream')
            // 恢复
            Object.defineProperty(window.location, 'protocol', {
                value: originalProtocol, writable: true, configurable: true
            })
        })
    })

    describe('deleteProject', () => {
        it('should call DELETE /projects/:projectId', async () => {
            axios.delete.mockResolvedValue({ data: { status: 'deleted', project_id: 'proj-1' } })
            const result = await api.deleteProject('proj-1')
            expect(axios.delete).toHaveBeenCalledWith('/projects/proj-1')
            expect(result).toEqual({ status: 'deleted', project_id: 'proj-1' })
        })
    })

    describe('getFileContent', () => {
        it('should call GET /projects/:projectId/files/content with path param', async () => {
            axios.get.mockResolvedValue({ data: { path: 'test.txt', content: 'hello', size: 5, encoding: 'utf-8' } })
            const result = await api.getFileContent('proj-1', 'test.txt')
            expect(axios.get).toHaveBeenCalledWith('/projects/proj-1/files/content', { params: { path: 'test.txt' } })
            expect(result).toEqual({ path: 'test.txt', content: 'hello', size: 5, encoding: 'utf-8' })
        })
    })

    describe('stopSession', () => {
        it('should call POST /projects/:projectId/sessions/:sessionId/stop', async () => {
            axios.post.mockResolvedValue({ data: { status: 'stopped', session_id: 'sess-1' } })
            const result = await api.stopSession('proj-1', 'sess-1')
            expect(axios.post).toHaveBeenCalledWith('/projects/proj-1/sessions/sess-1/stop')
            expect(result).toEqual({ status: 'stopped', session_id: 'sess-1' })
        })
    })
})
