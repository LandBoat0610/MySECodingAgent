import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getAgentConfig, updateAgentConfig } from '../api/index.js'

export const useAgentConfigStore = defineStore('agentConfig', () => {
  const model = ref('')
  const versionLabel = ref('')
  const crossSessionEnabled = ref(true)
  const loading = ref(false)
  const error = ref(null)

  async function load() {
    loading.value = true
    error.value = null
    try {
      const data = await getAgentConfig()
      model.value = data.model || ''
      versionLabel.value = data.version_label || ''
      crossSessionEnabled.value = data.cross_session_enabled !== false
    } catch (e) {
      error.value = e.response?.data?.detail || e.message || '加载失败'
    } finally {
      loading.value = false
    }
  }

  async function save(partial) {
    loading.value = true
    error.value = null
    try {
      const data = await updateAgentConfig(partial)
      model.value = data.model || ''
      versionLabel.value = data.version_label || ''
      crossSessionEnabled.value = data.cross_session_enabled !== false
    } catch (e) {
      error.value = e.response?.data?.detail || e.message || '保存失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  return {
    model,
    versionLabel,
    crossSessionEnabled,
    loading,
    error,
    load,
    save
  }
})
