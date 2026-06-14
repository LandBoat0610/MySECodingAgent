/**
 * components/RagSources.test.js
 * 测试 RagSources 组件：RAG 来源展示
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import RagSources from '../../components/RagSources.vue'

describe('RagSources.vue', () => {
    describe('empty state', () => {
        it('should not render when sources array is empty', () => {
            const wrapper = mount(RagSources, {
                props: { sources: [] }
            })
            expect(wrapper.find('.rag-sources').exists()).toBe(false)
        })
    })

    describe('sources display', () => {
        const sampleSources = [
            {
                type: 'file',
                title: 'API 文档',
                source: '/docs/api.md',
                snippet: 'This endpoint returns user data...',
                score: 0.95
            },
            {
                type: 'url',
                title: 'Python 官方文档',
                source: 'https://docs.python.org/3/library/os.html',
                snippet: 'The os module provides...',
                score: 0.82
            }
        ]

        it('should render source items', () => {
            const wrapper = mount(RagSources, {
                props: { sources: sampleSources }
            })
            expect(wrapper.find('.rag-sources').exists()).toBe(true)
            expect(wrapper.findAll('.rag-item')).toHaveLength(2)
            expect(wrapper.find('.rag-header').exists()).toBe(true)
        })

        it('should show source count', () => {
            const wrapper = mount(RagSources, {
                props: { sources: sampleSources }
            })
            expect(wrapper.find('.rag-count').text()).toBe('2 条')
        })

        it('should show source titles', () => {
            const wrapper = mount(RagSources, {
                props: { sources: sampleSources }
            })
            const titles = wrapper.findAll('.rag-item-title')
            expect(titles[0].text()).toBe('API 文档')
            expect(titles[1].text()).toBe('Python 官方文档')
        })

        it('should show relevance scores as percentage', () => {
            const wrapper = mount(RagSources, {
                props: { sources: sampleSources }
            })
            const scores = wrapper.findAll('.rag-score')
            expect(scores[0].text()).toBe('95%')
            expect(scores[1].text()).toBe('82%')
        })

        it('should show snippets', () => {
            const wrapper = mount(RagSources, {
                props: { sources: sampleSources }
            })
            const contents = wrapper.findAll('.rag-item-content')
            expect(contents[0].text()).toContain('This endpoint returns user data')
        })

        it('should show source paths', () => {
            const wrapper = mount(RagSources, {
                props: { sources: sampleSources }
            })
            const sources = wrapper.findAll('.rag-item-source code')
            expect(sources[0].text()).toBe('/docs/api.md')
            expect(sources[1].text()).toBe('https://docs.python.org/3/library/os.html')
        })
    })

    describe('expand/collapse toggle', () => {
        it('should be expanded by default', () => {
            const wrapper = mount(RagSources, {
                props: {
                    sources: [{ type: 'file', title: 'Test', source: '/test.md', snippet: 'test' }]
                }
            })
            expect(wrapper.find('.rag-body').exists()).toBe(true)
        })

        it('should toggle collapse on header click', async () => {
            const wrapper = mount(RagSources, {
                props: {
                    sources: [{ type: 'file', title: 'Test', source: '/test.md', snippet: 'test' }]
                }
            })
            await wrapper.find('.rag-header').trigger('click')
            expect(wrapper.find('.rag-body').exists()).toBe(false)
            await wrapper.find('.rag-header').trigger('click')
            expect(wrapper.find('.rag-body').exists()).toBe(true)
        })
    })

    describe('edge cases', () => {
        it('should handle source without score', () => {
            const wrapper = mount(RagSources, {
                props: {
                    sources: [{ type: 'file', title: 'No Score', source: '/test.md' }]
                }
            })
            expect(wrapper.find('.rag-score').exists()).toBe(false)
        })

        it('should handle source without snippet', () => {
            const wrapper = mount(RagSources, {
                props: {
                    sources: [{ type: 'url', title: 'Link Only', source: 'https://example.com' }]
                }
            })
            expect(wrapper.find('.rag-item-content').exists()).toBe(false)
        })

        it('should truncate long snippets to 300 chars', () => {
            const longText = 'x'.repeat(500)
            const wrapper = mount(RagSources, {
                props: {
                    sources: [{ type: 'file', title: 'Long', snippet: longText }]
                }
            })
            const content = wrapper.find('.rag-item-content')
            expect(content.text().length).toBeLessThanOrEqual(300)
        })

        it('should handle source without title using fallback', () => {
            const wrapper = mount(RagSources, {
                props: {
                    sources: [{ type: 'file', source: '/docs/readme.md' }]
                }
            })
            // When no title, shows the source path as fallback
            expect(wrapper.find('.rag-item-title').text()).toBe('/docs/readme.md')
        })

        it('should show different icons for different types', () => {
            const wrapper = mount(RagSources, {
                props: {
                    sources: [
                        { type: 'file', title: 'F', source: '/f' },
                        { type: 'url', title: 'U', source: 'https://u' },
                        { type: 'other', title: 'O', source: '/o' }
                    ]
                }
            })
            const icons = wrapper.findAll('.rag-item-icon')
            expect(icons[0].text()).toBe('📄')
            expect(icons[1].text()).toBe('🔗')
            expect(icons[2].text()).toBe('📌')
        })
    })
})
