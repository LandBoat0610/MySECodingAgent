/**
 * 全局测试 setup
 * - 配置 jsdom 环境的浏览器 API mock
 * - 配置全局 Pinia 测试插件
 */
import { config } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach } from 'vitest'

// ---- 浏览器 API mock ------------------------------------------------

// localStorage mock (jsdom 自带，此处确保可用)
if (!globalThis.localStorage) {
    globalThis.localStorage = {
        _data: {},
        getItem(key) { return this._data[key] ?? null },
        setItem(key, value) { this._data[key] = String(value) },
        removeItem(key) { delete this._data[key] },
        clear() { this._data = {} }
    }
}

// WebSocket mock
class MockWebSocket {
    constructor(url) {
        this.url = url
        this.readyState = 0 // CONNECTING
        this.onopen = null
        this.onmessage = null
        this.onclose = null
        this.onerror = null
    }
    send(data) { /* no-op */ }
    close() {
        this.readyState = 3 // CLOSED
        if (this.onclose) this.onclose({ code: 1000 })
    }
    // 测试辅助：模拟收到消息
    _mockMessage(data) {
        if (this.onmessage) this.onmessage({ data: JSON.stringify(data) })
    }
    // 测试辅助：模拟连接成功
    _mockOpen() {
        this.readyState = 1 // OPEN
        if (this.onopen) this.onopen()
    }
}
globalThis.WebSocket = MockWebSocket

// window.location mock（jsdom 环境固定为 localhost）
Object.defineProperty(window, 'location', {
    value: {
        protocol: 'http:',
        host: 'localhost:3000',
        href: 'http://localhost:3000/'
    },
    writable: true,
    configurable: true
})

// ---- Pinia 初始化 ------------------------------------------------

// 每个测试用例前创建全新的 pinia 实例，保证状态隔离
beforeEach(() => {
    const pinia = createPinia()
    setActivePinia(pinia)

    // 清空 localStorage
    localStorage.clear()
})

// ---- Vue Test Utils 全局配置 ------------------------------------------------

// 将 data-testid 属性作为默认的测试选择器
config.plugins.DOMWrapper.install((wrapper) => {
    // 可在测试中使用 wrapper.findByTestId('xxx')
    return {}
})
