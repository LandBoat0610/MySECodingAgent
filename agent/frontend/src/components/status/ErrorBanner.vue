<template>
  <div v-if="message" class="error-banner" role="alert">
    <span class="error-icon">⚠️</span>
    <span class="error-text">{{ message }}</span>
    <button
      v-if="dismissible"
      class="error-dismiss"
      @click="$emit('dismiss')"
      aria-label="关闭错误提示"
    >×</button>
  </div>
</template>

<script setup>
defineProps({
  message: { type: String, default: '' },
  dismissible: { type: Boolean, default: true }
})

defineEmits(['dismiss'])
</script>

<style scoped>
.error-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  margin: 8px 12px;
  border-radius: 8px;
  background: rgba(243, 139, 168, 0.12);
  border: 1px solid rgba(243, 139, 168, 0.3);
  color: var(--danger);
  font-size: 15px;
}

.error-icon {
  flex-shrink: 0;
  font-size: 15px;
}

.error-text {
  flex: 1;
  min-width: 0;
  line-height: 1.4;
  word-break: break-word;
}

.error-dismiss {
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  border-radius: 4px;
  background: transparent;
  color: var(--danger);
  font-size: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  border: none;
}

.error-dismiss:hover {
  background: rgba(243, 139, 168, 0.2);
}
</style>
