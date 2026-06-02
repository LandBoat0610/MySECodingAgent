<template>
  <Transition name="confirm-fade">
    <div v-if="isOpen" class="confirm-mask" @click.self="onCancel">
      <div class="confirm-dialog" role="alertdialog" aria-modal="true">
        <div class="confirm-head">
          <span class="confirm-icon">
            {{ variant === 'danger' ? '⚠️' : variant === 'warning' ? '⚡' : 'ℹ️' }}
          </span>
          <span class="confirm-title">{{ title }}</span>
        </div>
        <div class="confirm-body">
          <p>{{ message }}</p>
        </div>
        <div class="confirm-actions">
          <button class="btn btn-cancel" @click="onCancel">{{ cancelText }}</button>
          <button
            :class="['btn', variant === 'danger' ? 'btn-danger' : 'btn-primary']"
            @click="onConfirm"
          >
            {{ confirmText }}
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { useConfirmDialog } from '../composables/useConfirm.js'

const { isOpen, title, message, confirmText, cancelText, variant, onConfirm, onCancel } = useConfirmDialog()
</script>

<style scoped>
.confirm-mask {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.55);
}

.confirm-dialog {
  width: 380px;
  max-width: 92vw;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 14px;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.4);
  overflow: hidden;
}

.confirm-head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 18px 20px 10px;
}

.confirm-icon {
  font-size: 20px;
  line-height: 1;
}

.confirm-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.confirm-body {
  padding: 6px 20px 18px;
}

.confirm-body p {
  font-size: 15px;
  color: var(--text-secondary);
  line-height: 1.6;
}

.confirm-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 12px 20px;
  border-top: 1px solid var(--border-color);
}

.btn {
  padding: 8px 20px;
  border-radius: 8px;
  font-size: 15px;
  font-weight: 500;
  cursor: pointer;
  border: none;
}

.btn-cancel {
  background: var(--bg-surface);
  color: var(--text-secondary);
}

.btn-cancel:hover {
  background: var(--border-color);
  color: var(--text-primary);
}

.btn-danger {
  background: var(--danger);
  color: #1e1e2e;
}

.btn-danger:hover {
  opacity: 0.88;
}

.btn-primary {
  background: var(--accent);
  color: #1e1e2e;
}

.btn-primary:hover {
  opacity: 0.88;
}

/* Transition */
.confirm-fade-enter-active,
.confirm-fade-leave-active {
  transition: opacity 0.2s ease;
}

.confirm-fade-enter-active .confirm-dialog,
.confirm-fade-leave-active .confirm-dialog {
  transition: transform 0.2s ease, opacity 0.2s ease;
}

.confirm-fade-enter-from,
.confirm-fade-leave-to {
  opacity: 0;
}

.confirm-fade-enter-from .confirm-dialog {
  transform: scale(0.92);
  opacity: 0;
}

.confirm-fade-leave-to .confirm-dialog {
  transform: scale(0.92);
  opacity: 0;
}
</style>
