/**
 * utils/highlight.test.js
 * 测试语法高亮工具函数
 */
import { describe, it, expect } from 'vitest'
import { highlightCode, inferLangFromPath, markedHighlight } from '../../utils/highlight.js'

describe('highlight utils', () => {
    describe('highlightCode', () => {
        it('should return empty string for falsy input', () => {
            expect(highlightCode('')).toBe('')
            expect(highlightCode(null)).toBe('')
            expect(highlightCode(undefined)).toBe('')
        })

        it('should highlight code with specified language', () => {
            const result = highlightCode('console.log("hello")', 'javascript')
            expect(result).toBeTruthy()
            expect(typeof result).toBe('string')
            expect(result.length).toBeGreaterThan(0)
        })

        it('should auto-detect language when none specified', () => {
            const result = highlightCode('def hello(): pass')
            expect(result).toBeTruthy()
            expect(typeof result).toBe('string')
        })

        it('should fallback to escaped HTML on error', () => {
            // Passing an invalid language that highlight.js rejects might not throw,
            // but if it does, we capture the escaped result
            const result = highlightCode('<script>alert("xss")</script>')
            expect(result).toBeTruthy()
            expect(typeof result).toBe('string')
        })
    })

    describe('inferLangFromPath', () => {
        it('should return python for .py files', () => {
            expect(inferLangFromPath('main.py')).toBe('python')
        })

        it('should return javascript for .js files', () => {
            expect(inferLangFromPath('app.js')).toBe('javascript')
        })

        it('should return typescript for .ts files', () => {
            expect(inferLangFromPath('component.ts')).toBe('typescript')
        })

        it('should return typescript for .tsx files', () => {
            expect(inferLangFromPath('Component.tsx')).toBe('typescript')
        })

        it('should return json for .json files', () => {
            expect(inferLangFromPath('config.json')).toBe('json')
        })

        it('should return yaml for .yaml files', () => {
            expect(inferLangFromPath('workflow.yaml')).toBe('yaml')
        })

        it('should return yaml for .yml files', () => {
            expect(inferLangFromPath('config.yml')).toBe('yaml')
        })

        it('should return markdown for .md files', () => {
            expect(inferLangFromPath('README.md')).toBe('markdown')
        })

        it('should return bash for .sh files', () => {
            expect(inferLangFromPath('run.sh')).toBe('bash')
        })

        it('should return bash for .bat files', () => {
            expect(inferLangFromPath('script.bat')).toBe('bash')
        })

        it('should return sql for .sql files', () => {
            expect(inferLangFromPath('query.sql')).toBe('sql')
        })

        it('should return xml for .xml files', () => {
            expect(inferLangFromPath('config.xml')).toBe('xml')
        })

        it('should return xml for .svg files', () => {
            expect(inferLangFromPath('icon.svg')).toBe('xml')
        })

        it('should return css for .css files', () => {
            expect(inferLangFromPath('style.css')).toBe('css')
        })

        it('should return css for .scss files', () => {
            expect(inferLangFromPath('theme.scss')).toBe('css')
        })

        it('should return css for .less files', () => {
            expect(inferLangFromPath('theme.less')).toBe('css')
        })

        it('should return html for .vue files', () => {
            expect(inferLangFromPath('Component.vue')).toBe('html')
        })

        it('should return diff for .diff files', () => {
            expect(inferLangFromPath('changes.diff')).toBe('diff')
        })

        it('should return diff for .patch files', () => {
            expect(inferLangFromPath('fix.patch')).toBe('diff')
        })

        it('should return ini for .cfg files', () => {
            expect(inferLangFromPath('setup.cfg')).toBe('ini')
        })

        it('should return ini for .ini files', () => {
            expect(inferLangFromPath('config.ini')).toBe('ini')
        })

        it('should return ini for .toml files', () => {
            expect(inferLangFromPath('pyproject.toml')).toBe('ini')
        })

        it('should return empty string for unknown extension', () => {
            expect(inferLangFromPath('data.xyz')).toBe('')
        })

        it('should return empty string for empty input', () => {
            expect(inferLangFromPath('')).toBe('')
        })

        it('should return empty string for null input', () => {
            expect(inferLangFromPath(null)).toBe('')
        })

        it('should be case insensitive', () => {
            expect(inferLangFromPath('MAIN.PY')).toBe('python')
            expect(inferLangFromPath('App.JS')).toBe('javascript')
        })
    })

    describe('markedHighlight', () => {
        it('should return highlighted code for known language', () => {
            const result = markedHighlight('print("hello")', 'python')
            expect(result).toBeTruthy()
            expect(typeof result).toBe('string')
        })

        it('should auto-detect when language is unknown', () => {
            const result = markedHighlight('function test() {}', 'madeup')
            expect(result).toBeTruthy()
            expect(typeof result).toBe('string')
        })

        it('should return empty string for falsy input', () => {
            expect(markedHighlight('')).toBe('')
            expect(markedHighlight(null)).toBe('')
        })

        it('should handle edge case gracefully', () => {
            const result = markedHighlight('Some plain text', 'plaintext')
            expect(result).toBeTruthy()
            expect(typeof result).toBe('string')
        })
    })
})
