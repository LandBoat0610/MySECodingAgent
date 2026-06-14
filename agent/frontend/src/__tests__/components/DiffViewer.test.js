/**
 * components/DiffViewer.test.js
 * 测试 DiffViewer 组件：diff 内容解析、行渲染、统计信息
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import DiffViewer from '../../components/DiffViewer.vue'

describe('DiffViewer.vue', () => {
    describe('empty state', () => {
        it('should show empty message when content is empty', () => {
            const wrapper = mount(DiffViewer, {
                props: { content: '' }
            })
            expect(wrapper.find('.diff-empty').exists()).toBe(true)
            expect(wrapper.find('.diff-empty .empty-text').text()).toBe('暂无差异内容')
        })

        it('should show empty message when content is only whitespace', () => {
            const wrapper = mount(DiffViewer, {
                props: { content: '   \n  ' }
            })
            expect(wrapper.find('.diff-empty').exists()).toBe(true)
        })
    })

    describe('diff content rendering', () => {
        const sampleDiff = [
            'diff --git a/main.py b/main.py',
            'index abc123..def456 100644',
            '--- a/main.py',
            '+++ b/main.py',
            '@@ -1,3 +1,4 @@',
            ' def hello():',
            '-    print("old")',
            '+    print("new")',
            '+    print("extra")',
            ' def world():',
            '     pass'
        ].join('\n')

        it('should render diff content', () => {
            const wrapper = mount(DiffViewer, {
                props: { content: sampleDiff }
            })
            expect(wrapper.find('.diff-content').exists()).toBe(true)
            expect(wrapper.find('.diff-header').exists()).toBe(true)
            expect(wrapper.find('.diff-title').text()).toBe('Git Diff')
        })

        it('should show patch title when isPatch is true', () => {
            const wrapper = mount(DiffViewer, {
                props: { content: sampleDiff, isPatch: true }
            })
            expect(wrapper.find('.diff-title').text()).toBe('补丁 (Patch)')
            expect(wrapper.find('.diff-icon.diff-patch').exists()).toBe(true)
        })

        it('should render hunk header lines', () => {
            const wrapper = mount(DiffViewer, {
                props: { content: sampleDiff }
            })
            expect(wrapper.find('.diff-line.hunk-header').exists()).toBe(true)
        })

        it('should render added lines with green background', () => {
            const wrapper = mount(DiffViewer, {
                props: { content: sampleDiff }
            })
            const addLines = wrapper.findAll('.diff-line.add')
            expect(addLines.length).toBeGreaterThan(0)
        })

        it('should render deleted lines with red background', () => {
            const wrapper = mount(DiffViewer, {
                props: { content: sampleDiff }
            })
            const delLines = wrapper.findAll('.diff-line.del')
            expect(delLines.length).toBeGreaterThan(0)
        })

        it('should render meta lines', () => {
            const wrapper = mount(DiffViewer, {
                props: { content: sampleDiff }
            })
            const metaLines = wrapper.findAll('.diff-line.meta')
            expect(metaLines.length).toBeGreaterThan(0)
        })
    })

    describe('diff statistics', () => {
        it('should calculate additions, deletions, and file count', () => {
            const diff = [
                'diff --git a/a.py b/a.py',
                '--- a/a.py',
                '+++ b/a.py',
                '@@ -1,1 +1,2 @@',
                '-old',
                '+new',
                '+extra'
            ].join('\n')

            const wrapper = mount(DiffViewer, {
                props: { content: diff }
            })
            expect(wrapper.find('.stat-add').text()).toBe('+2')
            expect(wrapper.find('.stat-del').text()).toBe('-1')
        })

        it('should not show stats when no changes', () => {
            const wrapper = mount(DiffViewer, {
                props: { content: 'just some text\nno diff here' }
            })
            expect(wrapper.find('.diff-stats').exists()).toBe(false)
        })
    })

    describe('line numbers', () => {
        it('should show line numbers for context and changed lines', () => {
            const diff = [
                '@@ -1,2 +1,2 @@',
                ' unchanged',
                '-removed',
                '+added'
            ].join('\n')

            const wrapper = mount(DiffViewer, {
                props: { content: diff }
            })
            // Should have line number spans
            const numSpans = wrapper.findAll('.line-num-old, .line-num-new')
            expect(numSpans.length).toBeGreaterThan(0)
        })
    })

    describe('edge cases', () => {
        it('should handle diff with only hunk header', () => {
            const wrapper = mount(DiffViewer, {
                props: { content: '@@ -1,5 +1,5 @@' }
            })
            expect(wrapper.find('.diff-line.hunk-header').exists()).toBe(true)
        })

        it('should handle very long lines', () => {
            const longLine = '+ ' + 'x'.repeat(1000)
            const wrapper = mount(DiffViewer, {
                props: { content: `@@ -1,1 +1,1 @@\n${longLine}` }
            })
            expect(wrapper.find('.diff-line.add').exists()).toBe(true)
        })

        it('should handle empty diff after trim', () => {
            const wrapper = mount(DiffViewer, {
                props: { content: '\n\n\n' }
            })
            expect(wrapper.find('.diff-empty').exists()).toBe(true)
        })
    })
})
