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
        // 报告器：CI 环境输出 junit XML
        reporters: process.env.CI
            ? ['verbose', 'junit']
            : ['verbose'],
        outputFile: process.env.CI
            ? { junit: './junit.xml' }
            : undefined,
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
        testTimeout: 10000
    },
    resolve: {
        alias: {
            '@': resolve(__dirname, 'src')
        }
    }
})
