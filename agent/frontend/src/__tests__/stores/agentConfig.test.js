/**
 * stores/agentConfig.test.js
 * 测试 agentConfig Pinia store
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

// Mock API module
vi.mock('../../api/index.js', () => ({
    getAgentConfig: vi.fn(),
    updateAgentConfig: vi.fn()
}))

import * as api from '../../api/index.js'
import { useAgentConfigStore } from '../../stores/agentConfig.js'

describe('agentConfig store', () => {
    beforeEach(() => {
        const pinia = createPinia()
        setActivePinia(pinia)
        vi.clearAllMocks()
    })

    it('should have correct default values', () => {
        const store = useAgentConfigStore()
        expect(store.model).toBe('')
        expect(store.versionLabel).toBe('')
        expect(store.loading).toBe(false)
        expect(store.error).toBeNull()
    })

    describe('load', () => {
        it('should load config successfully', async () => {
            api.getAgentConfig.mockResolvedValue({
                model: 'gpt-4o',
                version_label: 'v2'
            })
            const store = useAgentConfigStore()
            await store.load()

            expect(store.model).toBe('gpt-4o')
            expect(store.versionLabel).toBe('v2')
            expect(store.loading).toBe(false)
            expect(store.error).toBeNull()
        })

        it('should handle empty response gracefully', async () => {
            api.getAgentConfig.mockResolvedValue({})
            const store = useAgentConfigStore()
            await store.load()

            expect(store.model).toBe('')
            expect(store.versionLabel).toBe('')
        })

        it('should set error on failure', async () => {
            api.getAgentConfig.mockRejectedValue(new Error('Network error'))
            const store = useAgentConfigStore()
            await store.load()

            expect(store.error).toBeTruthy()
            expect(store.loading).toBe(false)
        })

        it('should handle axios-like error response', async () => {
            api.getAgentConfig.mockRejectedValue({
                response: { data: { detail: 'Not authorized' } }
            })
            const store = useAgentConfigStore()
            await store.load()

            expect(store.error).toBe('Not authorized')
        })

        it('should set loading to true during load', async () => {
            let loadingWasTrue = false
            api.getAgentConfig.mockImplementation(async () => {
                loadingWasTrue = store.loading
                return { model: 'test' }
            })
            const store = useAgentConfigStore()
            await store.load()
            expect(loadingWasTrue).toBe(true)
        })
    })

    describe('save', () => {
        it('should save config successfully', async () => {
            api.updateAgentConfig.mockResolvedValue({
                model: 'gpt-4-turbo',
                version_label: 'v3'
            })
            const store = useAgentConfigStore()
            await store.save({ model: 'gpt-4-turbo' })

            expect(store.model).toBe('gpt-4-turbo')
            expect(store.versionLabel).toBe('v3')
            expect(api.updateAgentConfig).toHaveBeenCalledWith({ model: 'gpt-4-turbo' })
        })

        it('should throw on failure and set error', async () => {
            api.updateAgentConfig.mockRejectedValue(new Error('Save failed'))
            const store = useAgentConfigStore()
            await expect(store.save({ model: 'bad' })).rejects.toThrow('Save failed')
            expect(store.error).toBeTruthy()
        })
    })
})
