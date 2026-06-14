<template>
  <div class="loading-spinner" role="status" aria-label="加载中">
    <span class="spinner"></span>
    <span v-if="text" class="loading-text">{{ text }}</span>
  </div>
</template>

<script setup>
defineProps({
  text: { type: String, default: 'Loading...' }
})
</script>

<style scoped>
.loading-spinner {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 24px;
  color: var(--text-muted);
  font-size: 15px;
}

.spinner {
  width: 28px;
  height: 28px;
  border: 3px solid var(--border-color);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.loading-text {
  font-size: 15px;
}
</style>
