/**
 * IDE 布局：左侧栏、预览与 Agent 面板
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import IdeLayout from '../../layouts/IdeLayout.vue'
import { useAgentStore } from '../../stores/agent.js'
import { useAgentConfigStore } from '../../stores/agentConfig.js'

vi.mock('../../components/ProjectPanel.vue', () => ({
  default: { name: 'ProjectPanel', template: '<div class="mock-project-panel"></div>' }
}))
vi.mock('../../components/FileTreePanel.vue', () => ({
  default: { name: 'FileTreePanel', template: '<div class="mock-filetree-panel"></div>', emits: ['select-file'] }
}))
vi.mock('../../components/FilePreview.vue', () => ({
  default: { name: 'FilePreview', template: '<div class="mock-file-preview"></div>', emits: [], expose: [] }
}))
vi.mock('../../components/ChatPanel.vue', () => ({
  default: { name: 'ChatPanel', template: '<div class="mock-chat-panel"></div>' }
}))
vi.mock('../../components/LiveEvalHud.vue', () => ({
  default: { name: 'LiveEvalHud', template: '<div class="mock-live-hud"></div>' }
}))

vi.mock('../../stores/agent.js', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    useAgentStore: vi.fn()
  }
})

vi.mock('../../stores/agentConfig.js', () => ({
  useAgentConfigStore: vi.fn()
}))

function createMockAgentStore(overrides = {}) {
  return {
    selectedProjectId: null,
    selectedSessionId: null,
    sessionStatus: 'idle',
    fileTree: [],
    projects: [],
    sessions: [],
    pendingPlans: [],
    chatMessages: [],
    traceLogs: [],
    finalAnswer: '',
    agentRunning: false,
    error: null,
    loading: false,
    agentRunStartedAt: null,
    livePerf: {
      tokensTotal: 0,
      toolEventsCount: 0,
      toolSuccessRate: null,
      toolAvgLatencyMs: null
    },
    fetchProjects: vi.fn(),
    fetchSessions: vi.fn(),
    fetchFileTree: vi.fn(),
    restoreSessionState: vi.fn(),
    ...overrides
  }
}

function createMockConfigStore() {
  return {
    model: '',
    load: vi.fn().mockResolvedValue(undefined)
  }
}

describe('IdeLayout.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    const pinia = createPinia()
    setActivePinia(pinia)
    useAgentConfigStore.mockReturnValue(createMockConfigStore())
  })

  it('should mount successfully', () => {
    useAgentStore.mockReturnValue(createMockAgentStore())
    const wrapper = mount(IdeLayout, {
      global: {
        stubs: {
          RouterLink: {
            template: '<a><slot /></a>',
            props: ['to']
          }
        }
      }
    })
    expect(wrapper.find('.app-container').exists()).toBe(true)
  })

  it('should render sidebars and panels', () => {
    useAgentStore.mockReturnValue(createMockAgentStore())
    const wrapper = mount(IdeLayout, {
      global: {
        stubs: {
          RouterLink: { template: '<a><slot /></a>', props: ['to'] }
        }
      }
    })
    expect(wrapper.find('.left-sidebar').exists()).toBe(true)
    expect(wrapper.find('.center-preview').exists()).toBe(true)
    expect(wrapper.find('.right-panel').exists()).toBe(true)
    expect(wrapper.find('.sidebar-footer').exists()).toBe(true)
    expect(wrapper.find('.mock-live-hud').exists()).toBe(true)
  })

  it('should call fetchProjects and agentConfig.load on mount', async () => {
    const mockStore = createMockAgentStore()
    useAgentStore.mockReturnValue(mockStore)
    const cfg = createMockConfigStore()
    useAgentConfigStore.mockReturnValue(cfg)
    mount(IdeLayout, {
      global: {
        stubs: {
          RouterLink: { template: '<a><slot /></a>', props: ['to'] }
        }
      }
    })
    await new Promise(r => setTimeout(r, 50))
    expect(mockStore.fetchProjects).toHaveBeenCalled()
    expect(cfg.load).toHaveBeenCalled()
  })

  it('should fetch sessions and file tree if project is selected on mount', async () => {
    const mockStore = createMockAgentStore({ selectedProjectId: 'p1' })
    useAgentStore.mockReturnValue(mockStore)
    mount(IdeLayout, {
      global: {
        stubs: {
          RouterLink: { template: '<a><slot /></a>', props: ['to'] }
        }
      }
    })
    await new Promise(r => setTimeout(r, 50))
    expect(mockStore.fetchProjects).toHaveBeenCalled()
    expect(mockStore.fetchSessions).toHaveBeenCalled()
    expect(mockStore.fetchFileTree).toHaveBeenCalled()
  })

  it('should embed live eval panel in sidebar footer', () => {
    useAgentStore.mockReturnValue(createMockAgentStore())
    const wrapper = mount(IdeLayout)
    expect(wrapper.find('.sidebar-footer .mock-live-hud').exists()).toBe(true)
  })
})
