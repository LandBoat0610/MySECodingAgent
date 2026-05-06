/**
 * utils/persistence.test.js
 * 测试 localStorage 持久化工具函数
 */
import { describe, it, expect, beforeEach } from 'vitest'
import {
    persistProjectId,
    getPersistedProjectId,
    persistSessionId,
    getPersistedSessionId,
    clearPersistence
} from '../../utils/persistence.js'

describe('persistence utils', () => {
    beforeEach(() => {
        localStorage.clear()
    })

    describe('persistProjectId / getPersistedProjectId', () => {
        it('should return null when no project id is stored', () => {
            expect(getPersistedProjectId()).toBeNull()
        })

        it('should store and retrieve a project id', () => {
            persistProjectId('proj-abc-123')
            expect(getPersistedProjectId()).toBe('proj-abc-123')
        })

        it('should store null as string "null" and return it', () => {
            persistProjectId(null)
            // localStorage stores null as "null"
            expect(getPersistedProjectId()).toBe('null')
        })

        it('should overwrite existing project id', () => {
            persistProjectId('first')
            persistProjectId('second')
            expect(getPersistedProjectId()).toBe('second')
        })
    })

    describe('persistSessionId / getPersistedSessionId', () => {
        it('should return null when no session id is stored', () => {
            expect(getPersistedSessionId()).toBeNull()
        })

        it('should store and retrieve a session id', () => {
            persistSessionId('sess-xyz-456')
            expect(getPersistedSessionId()).toBe('sess-xyz-456')
        })
    })

    describe('clearPersistence', () => {
        it('should remove both project and session ids', () => {
            persistProjectId('p1')
            persistSessionId('s1')
            clearPersistence()
            expect(getPersistedProjectId()).toBeNull()
            expect(getPersistedSessionId()).toBeNull()
        })
    })

    describe('storage keys independence', () => {
        it('project and session ids should use different keys', () => {
            persistProjectId('p1')
            persistSessionId('s1')
            expect(getPersistedProjectId()).toBe('p1')
            expect(getPersistedSessionId()).toBe('s1')
        })
    })
})
