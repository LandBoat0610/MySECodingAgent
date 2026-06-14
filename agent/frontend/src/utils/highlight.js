/**
 * 代码语法高亮工具
 * 基于 highlight.js，支持常用编程语言
 */
import hljs from 'highlight.js/lib/core'
import python from 'highlight.js/lib/languages/python'
import javascript from 'highlight.js/lib/languages/javascript'
import typescript from 'highlight.js/lib/languages/typescript'
import bash from 'highlight.js/lib/languages/bash'
import json from 'highlight.js/lib/languages/json'
import xml from 'highlight.js/lib/languages/xml'
import css from 'highlight.js/lib/languages/css'
import yaml from 'highlight.js/lib/languages/yaml'
import markdown from 'highlight.js/lib/languages/markdown'
import sql from 'highlight.js/lib/languages/sql'
import diff from 'highlight.js/lib/languages/diff'
import plaintext from 'highlight.js/lib/languages/plaintext'
import 'highlight.js/styles/github-dark.css'

hljs.registerLanguage('python', python)
hljs.registerLanguage('javascript', javascript)
hljs.registerLanguage('typescript', typescript)
hljs.registerLanguage('bash', bash)
hljs.registerLanguage('shell', bash)
hljs.registerLanguage('json', json)
hljs.registerLanguage('xml', xml)
hljs.registerLanguage('html', xml)
hljs.registerLanguage('css', css)
hljs.registerLanguage('yaml', yaml)
hljs.registerLanguage('markdown', markdown)
hljs.registerLanguage('sql', sql)
hljs.registerLanguage('diff', diff)
hljs.registerLanguage('plaintext', plaintext)

/**
 * 对代码进行语法高亮
 * @param {string} code - 源代码
 * @param {string} [lang] - 语言标识（可选，不传则自动检测）
 * @returns {string} 高亮后的 HTML
 */
export function highlightCode(code, lang) {
    if (!code) return ''
    try {
        if (lang && hljs.getLanguage(lang)) {
            return hljs.highlight(code, { language: lang }).value
        }
        return hljs.highlightAuto(code).value
    } catch {
        return escapeHtml(code)
    }
}

/**
 * 从文件路径推断语言
 */
export function inferLangFromPath(filePath) {
    if (!filePath) return ''
    const ext = (filePath.split('.').pop() || '').toLowerCase()
    const map = {
        py: 'python', js: 'javascript', ts: 'typescript', tsx: 'typescript',
        jsx: 'javascript', vue: 'html', json: 'json', html: 'html', htm: 'html',
        css: 'css', scss: 'css', less: 'css',
        yaml: 'yaml', yml: 'yaml', md: 'markdown',
        sh: 'bash', bat: 'bash', ps1: 'bash',
        sql: 'sql', xml: 'xml', svg: 'xml',
        diff: 'diff', patch: 'diff',
        cfg: 'ini', ini: 'ini', toml: 'ini',
    }
    return map[ext] || ''
}

/**
 * HTML 转义（作为高亮失败的降级方案）
 */
function escapeHtml(text) {
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
}

/**
 * Markdown 代码块高亮回调（用于 marked）
 */
export function markedHighlight(code, lang) {
    if (!code) return ''
    if (lang && hljs.getLanguage(lang)) {
        try {
            return hljs.highlight(code, { language: lang }).value
        } catch { /* fallback */ }
    }
    try {
        return hljs.highlightAuto(code).value
    } catch {
        return escapeHtml(code)
    }
}

export default hljs
