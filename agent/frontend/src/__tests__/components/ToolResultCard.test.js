/**
 * components/ToolResultCard.test.js
 * 测试 ToolResultCard 组件：各类工具结果的渲染
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ToolResultCard from '../../components/ToolResultCard.vue'

describe('ToolResultCard.vue', () => {
    describe('status bar', () => {
        it('should show success status bar', () => {
            const wrapper = mount(ToolResultCard, {
                props: {
                    toolName: 'execute_bash',
                    content: JSON.stringify({ status: 'success', success: true, output: 'ok', summary: '命令成功' })
                }
            })
            expect(wrapper.find('.result-status-bar.success').exists()).toBe(true)
            expect(wrapper.find('.status-label').text()).toBe('成功')
            expect(wrapper.find('.status-icon').text()).toBe('✅')
        })

        it('should show error status bar', () => {
            const wrapper = mount(ToolResultCard, {
                props: {
                    toolName: 'execute_bash',
                    content: JSON.stringify({ status: 'error', success: false, output: 'failed', error_type: 'execution_error' })
                }
            })
            expect(wrapper.find('.result-status-bar.error').exists()).toBe(true)
            expect(wrapper.find('.status-label').text()).toBe('失败')
            expect(wrapper.find('.status-icon').text()).toBe('❌')
            expect(wrapper.find('.error-type').text()).toBe('execution_error')
        })
    })

    describe('execute_bash result', () => {
        it('should show stdout and stderr', () => {
            const wrapper = mount(ToolResultCard, {
                props: {
                    toolName: 'execute_bash',
                    content: JSON.stringify({
                        status: 'success', success: true,
                        stdout: 'hello world',
                        stderr: 'warning: deprecated',
                        returncode: 0
                    })
                }
            })
            expect(wrapper.find('.stdio-block.stdout').exists()).toBe(true)
            expect(wrapper.find('.stdio-content').text()).toContain('hello world')
            expect(wrapper.find('.stdio-block.stderr').exists()).toBe(true)
        })

        it('should handle command without stderr', () => {
            const wrapper = mount(ToolResultCard, {
                props: {
                    toolName: 'execute_bash',
                    content: JSON.stringify({
                        status: 'success', success: true,
                        stdout: 'test passed',
                        stderr: '',
                        returncode: 0
                    })
                }
            })
            // stdout block should exist, stderr block should not
            expect(wrapper.find('.stdio-block.stdout').exists()).toBe(true)
            expect(wrapper.find('.stdio-block.stderr').exists()).toBe(false)
        })
    })

    describe('list_files result', () => {
        it('should render file entries from JSON output', () => {
            const inner = {
                path: '.',
                count: 3,
                entries: [
                    { name: 'main.py', type: 'file', path: 'main.py' },
                    { name: 'tests', type: 'dir', path: 'tests' },
                    { name: 'README.md', type: 'file', path: 'README.md' }
                ]
            }
            const wrapper = mount(ToolResultCard, {
                props: {
                    toolName: 'list_files',
                    content: JSON.stringify({ status: 'success', output: JSON.stringify(inner), summary: '3 条' })
                }
            })
            expect(wrapper.find('.result-files').exists()).toBe(true)
            expect(wrapper.findAll('.file-entry')).toHaveLength(3)
            expect(wrapper.find('.file-entry.dir').exists()).toBe(true)
        })

        it('should handle empty file list', () => {
            const inner = { path: '.', count: 0, entries: [] }
            const wrapper = mount(ToolResultCard, {
                props: {
                    toolName: 'list_files',
                    content: JSON.stringify({ status: 'success', output: JSON.stringify(inner), summary: '0 条' })
                }
            })
            expect(wrapper.findAll('.file-entry')).toHaveLength(0)
        })
    })

    describe('web_search result', () => {
        it('should render search results', () => {
            const inner = {
                query: 'python',
                results: [
                    { title: 'Python.org', url: 'https://python.org', snippet: 'Official site' },
                    { title: 'Python Docs', url: 'https://docs.python.org', snippet: 'Documentation' }
                ]
            }
            const wrapper = mount(ToolResultCard, {
                props: {
                    toolName: 'web_search',
                    content: JSON.stringify({ status: 'success', output: JSON.stringify(inner), summary: '搜索完成: 2 条' })
                }
            })
            expect(wrapper.find('.result-search').exists()).toBe(true)
            expect(wrapper.findAll('.search-item')).toHaveLength(2)
            expect(wrapper.find('.search-title a').text()).toBe('Python.org')
        })
    })

    describe('search_code result', () => {
        it('should render code matches', () => {
            const inner = {
                pattern: 'def test_',
                count: 2,
                matches: [
                    { file: 'test_main.py', line: 10, text: 'def test_foo():' },
                    { file: 'test_utils.py', line: 5, text: 'def test_bar():' }
                ]
            }
            const wrapper = mount(ToolResultCard, {
                props: {
                    toolName: 'search_code',
                    content: JSON.stringify({ status: 'success', output: JSON.stringify(inner), summary: '搜索: 2 条' })
                }
            })
            expect(wrapper.find('.result-code-search').exists()).toBe(true)
            expect(wrapper.findAll('.code-match')).toHaveLength(2)
        })
    })

    describe('get_git_diff result', () => {
        it('should render diff viewer', () => {
            const diffContent = 'diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@ -1,1 +1,1 @@\n-old\n+new'
            const wrapper = mount(ToolResultCard, {
                props: {
                    toolName: 'get_git_diff',
                    content: JSON.stringify({ status: 'success', output: diffContent, summary: 'diff 完成' })
                }
            })
            // DiffViewer 是子组件，这里验证 diff 区域存在
            expect(wrapper.find('.result-diff').exists()).toBe(true)
        })
    })

    describe('apply_patch result', () => {
        it('should show patch diff viewer with isPatch flag', () => {
            const wrapper = mount(ToolResultCard, {
                props: {
                    toolName: 'apply_patch',
                    content: JSON.stringify({ status: 'success', output: '已应用 2 个hunk', summary: 'patch 成功' })
                }
            })
            expect(wrapper.find('.result-diff').exists()).toBe(true)
        })
    })

    describe('read_file result', () => {
        it('should render file content', () => {
            const wrapper = mount(ToolResultCard, {
                props: {
                    toolName: 'read_file',
                    content: JSON.stringify({ status: 'success', output: 'print("hello")\nprint("world")', summary: '已读取 main.py' })
                }
            })
            expect(wrapper.find('.result-file-read').exists()).toBe(true)
            expect(wrapper.find('.file-content').text()).toContain('print("hello")')
        })
    })

    describe('write_file result', () => {
        it('should show write confirmation', () => {
            const wrapper = mount(ToolResultCard, {
                props: {
                    toolName: 'write_file',
                    content: JSON.stringify({ status: 'success', output: '已写入 main.py (3 行)', summary: '已写入 main.py' })
                }
            })
            expect(wrapper.find('.result-write').exists()).toBe(true)
            expect(wrapper.find('.write-msg').text()).toContain('已写入 main.py')
        })
    })

    describe('run_tests result', () => {
        it('should show test results with stdout', () => {
            const wrapper = mount(ToolResultCard, {
                props: {
                    toolName: 'run_tests',
                    content: JSON.stringify({
                        status: 'success', stdout: '5 passed in 2.34s', stderr: '', returncode: 0
                    })
                }
            })
            expect(wrapper.find('.result-stdio').exists()).toBe(true)
        })

        it('should show failed test results', () => {
            const wrapper = mount(ToolResultCard, {
                props: {
                    toolName: 'run_tests',
                    content: JSON.stringify({
                        status: 'error', stdout: '3 passed, 2 failed', stderr: 'FAILED test_foo', returncode: 1,
                        error_type: 'execution_error'
                    })
                }
            })
            expect(wrapper.find('.result-status-bar.error').exists()).toBe(true)
            expect(wrapper.find('.result-stdio').exists()).toBe(true)
        })
    })

    describe('run_lint result', () => {
        it('should show lint results', () => {
            const wrapper = mount(ToolResultCard, {
                props: {
                    toolName: 'run_lint',
                    content: JSON.stringify({
                        status: 'success', stdout: '', stderr: '', returncode: 0,
                        summary: 'lint 通过: 0 错误'
                    })
                }
            })
            expect(wrapper.find('.result-status-bar.success').exists()).toBe(true)
        })
    })

    describe('modified_files display', () => {
        it('should show modified files list', () => {
            const wrapper = mount(ToolResultCard, {
                props: {
                    toolName: 'write_file',
                    content: JSON.stringify({
                        status: 'success', output: 'ok',
                        modified_files: ['main.py', 'test_main.py', 'README.md']
                    })
                }
            })
            expect(wrapper.find('.result-modified').exists()).toBe(true)
            expect(wrapper.findAll('.modified-file')).toHaveLength(3)
        })

        it('should not show modified files when empty', () => {
            const wrapper = mount(ToolResultCard, {
                props: {
                    toolName: 'write_file',
                    content: JSON.stringify({ status: 'success', output: 'ok', modified_files: [] })
                }
            })
            expect(wrapper.find('.result-modified').exists()).toBe(false)
        })
    })

    describe('generic fallback output', () => {
        it('should show generic output for unknown tool', () => {
            const wrapper = mount(ToolResultCard, {
                props: {
                    toolName: 'unknown_tool',
                    content: JSON.stringify({ status: 'success', output: 'some result text' })
                }
            })
            expect(wrapper.find('.result-generic').exists()).toBe(true)
        })

        it('should handle non-JSON content gracefully', () => {
            const wrapper = mount(ToolResultCard, {
                props: {
                    toolName: 'some_tool',
                    content: 'plain text result, not JSON'
                }
            })
            // Should still render something without crashing
            expect(wrapper.find('.result-status-bar').exists()).toBe(true)
        })
    })

    describe('summary and path display', () => {
        it('should show summary in status bar', () => {
            const wrapper = mount(ToolResultCard, {
                props: {
                    toolName: 'read_file',
                    content: JSON.stringify({ status: 'success', output: 'content', summary: '已读取 main.py' })
                }
            })
            expect(wrapper.find('.status-summary').text()).toBe('已读取 main.py')
        })

        it('should show path when available', () => {
            const wrapper = mount(ToolResultCard, {
                props: {
                    toolName: 'read_file',
                    content: JSON.stringify({ status: 'success', output: 'content', path: '/workspace/main.py' })
                }
            })
            expect(wrapper.find('.status-path').text()).toContain('/workspace/main.py')
        })
    })
})
