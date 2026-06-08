/**
 * composables/useExpandedDirs.test.js
 * 测试文件树目录展开状态持久化 composable
 *
 * 注意：useExpandedDirs 使用模块级单例 _expandedPaths，
 * 测试之间会共享状态。使用 vi.resetModules() 重置。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'

describe('useExpandedDirs', () => {
    beforeEach(async () => {
        vi.resetModules()
        localStorage.clear()
    })

    async function getModule() {
        const mod = await import('../../composables/useExpandedDirs.js')
        return mod.useExpandedDirs
    }

    it('should return isExpanded and toggle functions', async () => {
        const useExpandedDirs = await getModule()
        const { isExpanded, toggle } = useExpandedDirs()
        expect(typeof isExpanded).toBe('function')
        expect(typeof toggle).toBe('function')
    })

    it('should start with no expanded paths (empty localStorage)', async () => {
        const useExpandedDirs = await getModule()
        const { isExpanded } = useExpandedDirs()
        // With empty localStorage, nothing should be expanded
        expect(isExpanded('/any/dir')).toBe(false)
    })

    it('should toggle a path from collapsed to expanded', async () => {
        const useExpandedDirs = await getModule()
        const { isExpanded, toggle } = useExpandedDirs()
        expect(isExpanded('/fresh-path')).toBe(false)
        toggle('/fresh-path')
        expect(isExpanded('/fresh-path')).toBe(true)
    })

    it('should toggle a path from expanded back to collapsed', async () => {
        const useExpandedDirs = await getModule()
        const { isExpanded, toggle } = useExpandedDirs()
        toggle('/unique')
        expect(isExpanded('/unique')).toBe(true)
        toggle('/unique')
        expect(isExpanded('/unique')).toBe(false)
    })

    it('should support multiple expanded paths', async () => {
        const useExpandedDirs = await getModule()
        const { isExpanded, toggle } = useExpandedDirs()
        toggle('/a')
        toggle('/b')
        expect(isExpanded('/a')).toBe(true)
        expect(isExpanded('/b')).toBe(true)
        expect(isExpanded('/c')).toBe(false)
    })

    it('should persist expanded paths to localStorage', async () => {
        const useExpandedDirs = await getModule()
        const { toggle } = useExpandedDirs()
        toggle('/persist-a')
        toggle('/persist-b')

        const stored = localStorage.getItem('agent_filetree_expanded')
        expect(stored).toBeTruthy()
        const parsed = JSON.parse(stored)
        expect(parsed).toContain('/persist-a')
        expect(parsed).toContain('/persist-b')
    })

    it('should restore expanded paths from localStorage on new instance', async () => {
        // Pre-populate localStorage
        localStorage.setItem('agent_filetree_expanded', JSON.stringify(['/restored-dir']))

        const useExpandedDirs = await getModule()
        const { isExpanded } = useExpandedDirs()

        // After resetModules + fresh import, it should read from localStorage
        expect(isExpanded('/restored-dir')).toBe(true)
    })
})
