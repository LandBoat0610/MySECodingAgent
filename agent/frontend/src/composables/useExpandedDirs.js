import { ref } from 'vue'

const STORAGE_KEY = 'agent_filetree_expanded'

// 全局单例：从 localStorage 恢复的展开目录路径集合（延迟初始化）
let _expandedPaths = null

function getExpandedPaths() {
    if (!_expandedPaths) {
        _expandedPaths = ref(loadFromStorage())
    }
    return _expandedPaths
}

function loadFromStorage() {
    try {
        const raw = localStorage.getItem(STORAGE_KEY)
        return raw ? new Set(JSON.parse(raw)) : new Set()
    } catch {
        return new Set()
    }
}

function saveToStorage(paths) {
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify([...paths]))
    } catch { /* quota exceeded, ignore */ }
}

/**
 * 文件树目录展开状态持久化 composable
 */
export function useExpandedDirs() {
    const expandedPaths = getExpandedPaths()

    function isExpanded(path) {
        return expandedPaths.value.has(path)
    }

    function toggle(path) {
        const next = new Set(expandedPaths.value)
        if (next.has(path)) {
            next.delete(path)
        } else {
            next.add(path)
        }
        expandedPaths.value = next
        saveToStorage(next)
    }

    return { isExpanded, toggle }
}
