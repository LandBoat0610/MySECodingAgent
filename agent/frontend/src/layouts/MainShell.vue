<template>
  <div class="main-shell">
    <RouterView />
    <WorkspaceSwitcher />
    <ConfirmDialog />
  </div>
</template>

<script setup>
import { RouterView } from 'vue-router'
import WorkspaceSwitcher from '../components/WorkspaceSwitcher.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
</script>

<style scoped>
.main-shell {
  height: 100%;
  position: relative;
  overflow: hidden;
}
</style>
