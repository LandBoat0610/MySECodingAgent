import { ref } from 'vue'

// 全局单例状态
const isOpen = ref(false)
const title = ref('')
const message = ref('')
const confirmText = ref('确定')
const cancelText = ref('取消')
const variant = ref('danger') // 'danger' | 'warning' | 'info'

let _resolve = null

/**
 * 打开确认弹窗，返回 Promise<boolean>。
 * 用户点「确定」→ resolve(true)，点「取消」/关闭 → resolve(false)
 */
export function showConfirm(opts = {}) {
    title.value = opts.title || '确认操作'
    message.value = opts.message || '确定要执行此操作吗？'
    confirmText.value = opts.confirmText || '确定'
    cancelText.value = opts.cancelText || '取消'
    variant.value = opts.variant || 'danger'
    isOpen.value = true

    return new Promise((resolve) => {
        _resolve = resolve
    })
}

export function useConfirmDialog() {
    function confirmResult(value) {
        isOpen.value = false
        if (_resolve) {
            _resolve(value)
            _resolve = null
        }
    }

    return {
        isOpen,
        title,
        message,
        confirmText,
        cancelText,
        variant,
        onConfirm: () => confirmResult(true),
        onCancel: () => confirmResult(false)
    }
}
