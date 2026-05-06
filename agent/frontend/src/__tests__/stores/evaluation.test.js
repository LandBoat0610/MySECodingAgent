/**
 * stores/evaluation.test.js
 * 测试 Pinia evaluation store 的核心逻辑：
 * - 状态管理（datasets, tasks, loading, error）
 * - API 调用流程（loadDatasets, loadTasks, loadAll）
 * - 数据集操作（upload, create, delete）
 * - 任务操作（add, remove, run, stop）
 * - 错误处理
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

// Mock API 模块
vi.mock('../../api/index.js', () => ({
    listEvalDatasets: vi.fn(),
    listEvalTasks: vi.fn(),
    uploadEvalDataset: vi.fn(),
    createEvalDatasetJson: vi.fn(),
    deleteEvalDataset: vi.fn(),
    createEvalTask: vi.fn(),
    deleteEvalTask: vi.fn(),
    startEvalTask: vi.fn(),
    cancelEvalTask: vi.fn(),
    getEvalTaskResults: vi.fn(),
}))

import * as api from '../../api/index.js'
import { useEvaluationStore } from '../../stores/evaluation.js'

function createStore() {
    const pinia = createPinia()
    setActivePinia(pinia)
    return useEvaluationStore()
}

describe('evaluation store', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        api.listEvalDatasets.mockResolvedValue([])
        api.listEvalTasks.mockResolvedValue([])
        api.uploadEvalDataset.mockResolvedValue({ id: 'ds-up', name: 'uploaded' })
        api.createEvalDatasetJson.mockResolvedValue({ id: 'ds-json', name: 'json-ds' })
        api.deleteEvalDataset.mockResolvedValue({ ok: true })
        api.createEvalTask.mockResolvedValue({ id: 'task-new', name: 'New Task' })
        api.deleteEvalTask.mockResolvedValue({ ok: true })
        api.startEvalTask.mockResolvedValue({ id: 't1', status: 'running' })
        api.cancelEvalTask.mockResolvedValue({ id: 't1', status: 'cancelling' })
        api.getEvalTaskResults.mockResolvedValue([])
    })

    // ============================================================
    // 初始状态
    // ============================================================
    describe('initial state', () => {
        it('should have correct default values', () => {
            const store = createStore()
            expect(store.datasets).toEqual([])
            expect(store.tasks).toEqual([])
            expect(store.loading).toBe(false)
            expect(store.error).toBeNull()
        })
    })

    // ============================================================
    // loadDatasets
    // ============================================================
    describe('loadDatasets', () => {
        it('should populate datasets on success', async () => {
            const store = createStore()
            api.listEvalDatasets.mockResolvedValue([
                { id: 'ds1', name: 'Dataset 1', item_count: 5, created_at: 'now' },
                { id: 'ds2', name: 'Dataset 2', item_count: 10, created_at: 'later' },
            ])
            await store.loadDatasets()
            expect(store.datasets).toHaveLength(2)
            expect(store.datasets[0].name).toBe('Dataset 1')
            expect(store.loading).toBe(false)
        })

        it('should set error on failure', async () => {
            const store = createStore()
            api.listEvalDatasets.mockRejectedValue(new Error('Network error'))
            await store.loadDatasets()
            expect(store.error).toBeTruthy()
            expect(store.loading).toBe(false)
        })

        it('should handle error with response detail', async () => {
            const store = createStore()
            const err = new Error('fail')
            err.response = { data: { detail: 'Server error' } }
            api.listEvalDatasets.mockRejectedValue(err)
            await store.loadDatasets()
            expect(store.error).toBe('Server error')
        })

        it('should handle array detail in error', async () => {
            const store = createStore()
            const err = new Error('fail')
            err.response = { data: { detail: [{ msg: 'field1 error' }, { msg: 'field2 error' }] } }
            api.listEvalDatasets.mockRejectedValue(err)
            await store.loadDatasets()
            expect(store.error).toContain('field1 error')
            expect(store.error).toContain('field2 error')
        })
    })

    // ============================================================
    // loadTasks
    // ============================================================
    describe('loadTasks', () => {
        it('should populate tasks on success', async () => {
            const store = createStore()
            api.listEvalTasks.mockResolvedValue([
                { id: 't1', name: 'Task 1', status: 'pending' },
            ])
            await store.loadTasks()
            expect(store.tasks).toHaveLength(1)
            expect(store.tasks[0].status).toBe('pending')
        })

        it('should set error on failure', async () => {
            const store = createStore()
            api.listEvalTasks.mockRejectedValue(new Error('Fail'))
            await store.loadTasks()
            expect(store.error).toBe('Fail')
        })
    })

    // ============================================================
    // loadAll
    // ============================================================
    describe('loadAll', () => {
        it('should load both datasets and tasks', async () => {
            const store = createStore()
            api.listEvalDatasets.mockResolvedValue([{ id: 'ds1', name: 'D', item_count: 1, created_at: 'n' }])
            api.listEvalTasks.mockResolvedValue([{ id: 't1', name: 'T', status: 'pending' }])
            await store.loadAll()
            expect(store.datasets).toHaveLength(1)
            expect(store.tasks).toHaveLength(1)
        })

        it('should set error if either fails', async () => {
            const store = createStore()
            api.listEvalDatasets.mockResolvedValue([])
            api.listEvalTasks.mockRejectedValue(new Error('task load failed'))
            await store.loadAll()
            expect(store.error).toBe('task load failed')
        })
    })

    // ============================================================
    // uploadDataset
    // ============================================================
    describe('uploadDataset', () => {
        it('should upload and reload datasets', async () => {
            const store = createStore()
            api.listEvalDatasets.mockResolvedValue([{ id: 'ds1', name: 'Uploaded', item_count: 3, created_at: 'n' }])
            await store.uploadDataset(new File([], 'test.json'), 'My DS')
            expect(api.uploadEvalDataset).toHaveBeenCalledWith(expect.any(File), 'My DS')
            expect(store.datasets[0].name).toBe('Uploaded')
        })

        it('should call upload with undefined name when not provided', async () => {
            const store = createStore()
            await store.uploadDataset(new File([], 'test.json'))
            expect(api.uploadEvalDataset).toHaveBeenCalledWith(expect.any(File), undefined)
        })
    })

    // ============================================================
    // createDatasetFromJson
    // ============================================================
    describe('createDatasetFromJson', () => {
        it('should create dataset from JSON and reload', async () => {
            const store = createStore()
            const items = [{ description: 't1' }, { description: 't2' }]
            await store.createDatasetFromJson('Json DS', items)
            expect(api.createEvalDatasetJson).toHaveBeenCalledWith({ name: 'Json DS', items })
        })
    })

    // ============================================================
    // removeDataset
    // ============================================================
    describe('removeDataset', () => {
        it('should delete dataset and reload both', async () => {
            const store = createStore()
            await store.removeDataset('ds1')
            expect(api.deleteEvalDataset).toHaveBeenCalledWith('ds1', {})
        })

        it('should pass cascade option', async () => {
            const store = createStore()
            await store.removeDataset('ds1', { cascade: true })
            expect(api.deleteEvalDataset).toHaveBeenCalledWith('ds1', { cascade: true })
        })
    })

    // ============================================================
    // addTask
    // ============================================================
    describe('addTask', () => {
        it('should create task and reload tasks', async () => {
            const store = createStore()
            const payload = { name: 'New Eval', dataset_id: 'ds1', eval_method: 'result' }
            await store.addTask(payload)
            expect(api.createEvalTask).toHaveBeenCalledWith(payload)
        })
    })

    // ============================================================
    // removeTask
    // ============================================================
    describe('removeTask', () => {
        it('should delete task and reload tasks', async () => {
            const store = createStore()
            await store.removeTask('t1')
            expect(api.deleteEvalTask).toHaveBeenCalledWith('t1')
        })
    })

    // ============================================================
    // runTask / stopTask
    // ============================================================
    describe('runTask', () => {
        it('should start task and reload tasks', async () => {
            const store = createStore()
            await store.runTask('t1')
            expect(api.startEvalTask).toHaveBeenCalledWith('t1')
        })
    })

    describe('stopTask', () => {
        it('should cancel task and reload tasks', async () => {
            const store = createStore()
            await store.stopTask('t1')
            expect(api.cancelEvalTask).toHaveBeenCalledWith('t1')
        })
    })

    // ============================================================
    // fetchResults
    // ============================================================
    describe('fetchResults', () => {
        it('should fetch results for a task', async () => {
            const store = createStore()
            api.getEvalTaskResults.mockResolvedValue([{ id: 'r1', status: 'completed' }])
            const results = await store.fetchResults('t1')
            expect(api.getEvalTaskResults).toHaveBeenCalledWith('t1')
            expect(results).toHaveLength(1)
        })
    })

    // ============================================================
    // clearError
    // ============================================================
    describe('clearError', () => {
        it('should reset error to null', () => {
            const store = createStore()
            store.error = 'some error'
            store.clearError()
            expect(store.error).toBeNull()
        })
    })
})
