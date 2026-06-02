<template>
  <div class="empty-state">
    <span v-if="icon" class="empty-icon">{{ icon }}</span>
    <span v-if="title" class="empty-title">{{ title }}</span>
    <span v-if="desc" class="empty-desc">{{ desc }}</span>
    <slot />
  </div>
</template>

<script setup>
defineProps({
  icon: { type: String, default: '📭' },
  title: { type: String, default: '暂无数据' },
  desc: { type: String, default: '' }
})
</script>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 32px 16px;
  color: var(--text-muted);
  text-align: center;
}

.empty-icon {
  font-size: 40px;
  opacity: 0.45;
  line-height: 1;
}

.empty-title {
  font-size: 15px;
  font-weight: 500;
  color: var(--text-secondary);
}

.empty-desc {
  font-size: 15px;
  max-width: 260px;
  line-height: 1.5;
}
</style>
