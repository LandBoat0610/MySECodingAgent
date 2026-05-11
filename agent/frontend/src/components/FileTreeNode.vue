<template>
  <div>
    <div
      :class="['tree-node', { 'is-file': node.type === 'file' }]"
      :style="{ paddingLeft: (depth * 16 + 8) + 'px' }"
      @click="handleClick"
    >
      <span class="node-arrow" v-if="node.type === 'directory'" @click.stop="toggle">
        {{ expanded ? '▾' : '▸' }}
      </span>
      <span class="node-icon">{{ node.type === 'directory' ? (expanded ? '📂' : '📁') : '📄' }}</span>
      <span class="node-name">{{ node.path.split('/').pop() }}</span>
    </div>
    <template v-if="node.type === 'directory' && expanded && node.children">
      <FileTreeNode
        v-for="child in node.children"
        :key="child.path"
        :node="child"
        :depth="depth + 1"
        @select="$emit('select', $event)"
      />
    </template>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  node: { type: Object, required: true },
  depth: { type: Number, default: 0 }
})

const emit = defineEmits(['select'])
const expanded = ref(false)

function toggle() {
  expanded.value = !expanded.value
}

function handleClick() {
  if (props.node.type === 'directory') {
    toggle()
  } else {
    emit('select', props.node)
  }
}
</script>

<style scoped>
.tree-node {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 5px 8px;
  cursor: pointer;
  font-size: 13px;
  transition: background 0.15s;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tree-node:hover {
  background: var(--bg-surface);
}

.tree-node.is-file:hover {
  color: var(--accent);
}

.node-arrow {
  width: 14px;
  font-size: 10px;
  color: var(--text-muted);
  flex-shrink: 0;
}

.node-icon {
  font-size: 13px;
  flex-shrink: 0;
}

.node-name {
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
