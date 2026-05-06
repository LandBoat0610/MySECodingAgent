import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
    plugins: [vue()],
    test: {
        // 测试环境：jsdom 模拟浏览器 DOM
        environment: 'jsdom',
        // 全局变量（无需在每个测试文件中 import { describe, it, expect }）
        globals: true,
        // setup 文件：在测试运行前执行
        setupFiles: ['./src/__tests__/setup.js'],
        // 测试文件匹配模式
        include: ['src/__tests__/**/*.test.{js,ts}'],
        // 覆盖率配置
        coverage: {
            provider: 'v8',
            reporter: ['text', 'text-summary', 'lcov', 'cobertura'],
            reportsDirectory: './coverage',
            include: ['src/**/*.{js,vue}'],
            exclude: [
                'src/__tests__/**',
                'src/main.js',
                'node_modules/'
            ]
        },
        // CSS 处理（测试时不处理 CSS）
        css: false,
        // 测试超时
        testTimeout: 10000,
        // CI 报告输出
        reporters: process.env.CI
            ? ['default', 'junit']
            : ['default'],
        outputFile: process.env.CI
            ? { junit: './junit.xml' }
            : undefined
    },
    resolve: {
        alias: {
            '@': resolve(__dirname, 'src')
        }
    }
})
