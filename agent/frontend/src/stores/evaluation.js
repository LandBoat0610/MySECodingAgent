import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  listEvalDatasets,
  listEvalTasks,
  uploadEvalDataset,
  createEvalDatasetJson,
  deleteEvalDataset,
  createEvalTask,
  deleteEvalTask,
  startEvalTask,
  cancelEvalTask,
  getEvalTaskResults
} from '../api/index.js'

export const useEvaluationStore = defineStore('evaluation', () => {
  const datasets = ref([])
  const tasks = ref([])
  const loading = ref(false)
  const error = ref(null)

  function setErr(e) {
    const d = e.response?.data?.detail
    if (Array.isArray(d)) {
      error.value = d.map(x => (typeof x === 'object' && x?.msg ? x.msg : JSON.stringify(x))).join('; ')
    } else if (d != null && typeof d !== 'string') {
      error.value = JSON.stringify(d)
    } else {
      error.value = d || e.message || String(e)
    }
  }

  async function loadDatasets() {
    loading.value = true
    error.value = null
    try {
      datasets.value = await listEvalDatasets()
    } catch (e) {
      setErr(e)
    } finally {
      loading.value = false
    }
  }

  async function loadTasks() {
    loading.value = true
    error.value = null
    try {
      tasks.value = await listEvalTasks()
    } catch (e) {
      setErr(e)
    } finally {
      loading.value = false
    }
  }

  async function loadAll() {
    loading.value = true
    error.value = null
    try {
      const [ds, ts] = await Promise.all([listEvalDatasets(), listEvalTasks()])
      datasets.value = ds
      tasks.value = ts
    } catch (e) {
      setErr(e)
    } finally {
      loading.value = false
    }
  }

  async function uploadDataset(file, displayName) {
    await uploadEvalDataset(file, displayName || undefined)
    await loadDatasets()
  }

  async function createDatasetFromJson(name, items) {
    await createEvalDatasetJson({ name: name || '', items })
    await loadDatasets()
  }

  async function removeDataset(id, opts = {}) {
    await deleteEvalDataset(id, opts)
    await Promise.all([loadDatasets(), loadTasks()])
  }

  async function addTask(payload) {
    await createEvalTask(payload)
    await loadTasks()
  }

  async function removeTask(id) {
    await deleteEvalTask(id)
    await loadTasks()
  }

  async function runTask(id) {
    await startEvalTask(id)
    await loadTasks()
  }

  async function stopTask(id) {
    await cancelEvalTask(id)
    await loadTasks()
  }

  async function fetchResults(taskId) {
    return getEvalTaskResults(taskId)
  }

  function clearError() {
    error.value = null
  }

  return {
    datasets,
    tasks,
    loading,
    error,
    loadDatasets,
    loadTasks,
    loadAll,
    uploadDataset,
    createDatasetFromJson,
    removeDataset,
    addTask,
    removeTask,
    runTask,
    stopTask,
    fetchResults,
    clearError
  }
})
