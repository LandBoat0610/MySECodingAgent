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
        put: vi.fn(),
        delete: vi.fn(),
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

        it('should include feedback when provided', async () => {
            axios.post.mockResolvedValue({ data: { status: 'refining' } })
            await api.planAction('proj-1', 'sess-1', 'plan-1', 'refine', '先检查文件')
            expect(axios.post).toHaveBeenCalledWith(
                '/projects/proj-1/sessions/sess-1/plan/plan-1/action',
                { action: 'refine', feedback: '先检查文件' }
            )
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

    describe('getAgentConfig', () => {
        it('should call GET /settings/agent-config', async () => {
            axios.get.mockResolvedValue({ data: { model: 'gpt-4o-mini', version_label: '' } })
            const result = await api.getAgentConfig()
            expect(axios.get).toHaveBeenCalledWith('/settings/agent-config')
            expect(result).toEqual({ model: 'gpt-4o-mini', version_label: '' })
        })
    })

    describe('updateAgentConfig', () => {
        it('should call PUT /settings/agent-config', async () => {
            axios.put.mockResolvedValue({ data: { model: 'gpt-4o', version_label: 'v2' } })
            const body = { model: 'gpt-4o', version_label: 'v2' }
            const result = await api.updateAgentConfig(body)
            expect(axios.put).toHaveBeenCalledWith('/settings/agent-config', body)
            expect(result).toEqual({ model: 'gpt-4o', version_label: 'v2' })
        })
    })

    describe('deleteEvalDataset', () => {
        it('should call DELETE /eval/datasets/:id without cascade query', async () => {
            axios.delete.mockResolvedValue({ data: { ok: true } })
            const result = await api.deleteEvalDataset('ds-1')
            expect(axios.delete).toHaveBeenCalledWith('/eval/datasets/ds-1', { params: {} })
            expect(result).toEqual({ ok: true })
        })

        it('should pass cascade=true when opts.cascade is set', async () => {
            axios.delete.mockResolvedValue({ data: { ok: true } })
            await api.deleteEvalDataset('ds-2', { cascade: true })
            expect(axios.delete).toHaveBeenCalledWith('/eval/datasets/ds-2', {
                params: { cascade: true }
            })
        })
    })

    describe('listEvalTasks', () => {
        it('should call GET /eval/tasks', async () => {
            axios.get.mockResolvedValue({ data: [] })
            await api.listEvalTasks()
            expect(axios.get).toHaveBeenCalledWith('/eval/tasks')
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

    // ============ Evaluation API ============
    describe('uploadEvalDataset', () => {
        it('should POST /eval/datasets/upload with FormData', async () => {
            const file = new File(['{"items":[{"description":"t"}]}'], 'test.json', { type: 'application/json' })
            axios.post.mockResolvedValue({ data: { id: 'ds1', name: 'Test', item_count: 1, created_at: 'now' } })
            const result = await api.uploadEvalDataset(file, 'My Dataset')
            expect(axios.post).toHaveBeenCalledWith('/eval/datasets/upload', expect.any(FormData), expect.any(Object))
            expect(result).toEqual({ id: 'ds1', name: 'Test', item_count: 1, created_at: 'now' })
        })

        it('should upload without name', async () => {
            const file = new File(['{"items":[{"description":"t"}]}'], 'test.json')
            axios.post.mockResolvedValue({ data: { id: 'ds2', name: 'unnamed', item_count: 1, created_at: 'now' } })
            await api.uploadEvalDataset(file)
            expect(axios.post).toHaveBeenCalledWith('/eval/datasets/upload', expect.any(FormData), expect.any(Object))
        })
    })

    describe('createEvalDatasetJson', () => {
        it('should POST /eval/datasets with body', async () => {
            const body = { name: 'DS', items: [{ description: 't' }] }
            axios.post.mockResolvedValue({ data: { id: 'ds3', name: 'DS', item_count: 1, created_at: 'now' } })
            const result = await api.createEvalDatasetJson(body)
            expect(axios.post).toHaveBeenCalledWith('/eval/datasets', body, expect.any(Object))
            expect(result.name).toBe('DS')
        })
    })

    describe('listEvalDatasets', () => {
        it('should call GET /eval/datasets', async () => {
            axios.get.mockResolvedValue({ data: [{ id: 'ds1', name: 'DS1' }] })
            const result = await api.listEvalDatasets()
            expect(axios.get).toHaveBeenCalledWith('/eval/datasets')
            expect(result).toHaveLength(1)
        })
    })

    describe('deleteEvalDataset', () => {
        it('should call DELETE /eval/datasets/:id', async () => {
            axios.delete.mockResolvedValue({ data: { ok: true } })
            const result = await api.deleteEvalDataset('ds1')
            expect(axios.delete).toHaveBeenCalledWith('/eval/datasets/ds1', { params: {} })
            expect(result).toEqual({ ok: true })
        })
    })

    describe('createEvalTask', () => {
        it('should POST /eval/tasks with body', async () => {
            const body = { name: 'Task', dataset_id: 'ds1', eval_method: 'result' }
            axios.post.mockResolvedValue({ data: { id: 't1', name: 'Task', status: 'pending' } })
            const result = await api.createEvalTask(body)
            expect(axios.post).toHaveBeenCalledWith('/eval/tasks', body)
            expect(result.status).toBe('pending')
        })
    })

    describe('listEvalTasks', () => {
        it('should call GET /eval/tasks', async () => {
            axios.get.mockResolvedValue({ data: [{ id: 't1', name: 'Task 1' }] })
            const result = await api.listEvalTasks()
            expect(axios.get).toHaveBeenCalledWith('/eval/tasks')
            expect(result).toHaveLength(1)
        })
    })

    describe('startEvalTask', () => {
        it('should POST /eval/tasks/:id/start', async () => {
            axios.post.mockResolvedValue({ data: { id: 't1', status: 'running' } })
            const result = await api.startEvalTask('t1')
            expect(axios.post).toHaveBeenCalledWith('/eval/tasks/t1/start')
            expect(result.status).toBe('running')
        })
    })

    describe('cancelEvalTask', () => {
        it('should POST /eval/tasks/:id/cancel', async () => {
            axios.post.mockResolvedValue({ data: { id: 't1', status: 'cancelling' } })
            const result = await api.cancelEvalTask('t1')
            expect(axios.post).toHaveBeenCalledWith('/eval/tasks/t1/cancel')
            expect(result.status).toBe('cancelling')
        })
    })

    describe('getEvalTaskResults', () => {
        it('should GET /eval/tasks/:id/results', async () => {
            axios.get.mockResolvedValue({ data: [{ id: 'r1', task_id: 't1', item_index: 0, status: 'completed' }] })
            const result = await api.getEvalTaskResults('t1')
            expect(axios.get).toHaveBeenCalledWith('/eval/tasks/t1/results')
            expect(result).toHaveLength(1)
        })
    })

    describe('deleteEvalTask', () => {
        it('should DELETE /eval/tasks/:id', async () => {
            axios.delete.mockResolvedValue({ data: { ok: true } })
            const result = await api.deleteEvalTask('t1')
            expect(axios.delete).toHaveBeenCalledWith('/eval/tasks/t1')
            expect(result).toEqual({ ok: true })
        })
    })
})
