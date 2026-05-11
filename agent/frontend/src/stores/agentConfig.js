import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getAgentConfig, updateAgentConfig } from '../api/index.js'

export const useAgentConfigStore = defineStore('agentConfig', () => {
  const model = ref('')
  const versionLabel = ref('')
  const loading = ref(false)
  const error = ref(null)

  async function load() {
    loading.value = true
    error.value = null
    try {
      const data = await getAgentConfig()
      model.value = data.model || ''
      versionLabel.value = data.version_label || ''
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
    loading,
    error,
    load,
    save
  }
})
