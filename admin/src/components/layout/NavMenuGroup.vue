<template>
  <div class="nav-group">
    <button
      type="button"
      class="nav-item nav-group-toggle"
      :class="{ active: isActive }"
      :aria-expanded="expanded"
      :aria-controls="panelId"
      @click="expanded = !expanded"
    >
      <el-icon class="nav-icon">
        <component :is="icon" />
      </el-icon>
      <span class="nav-text">{{ name }}</span>
      <el-icon class="nav-chevron" :class="{ expanded }" aria-hidden="true">
        <ArrowDown />
      </el-icon>
    </button>
    <div v-show="expanded" :id="panelId" class="nav-children">
      <router-link
        v-for="child in children"
        :key="child.path"
        :to="child.path"
        class="nav-item nav-child"
        :class="{ active: isChildActive(child.path) }"
        :aria-current="isChildActive(child.path) ? 'page' : undefined"
        @click="emit('navigate')"
      >
        <span class="nav-text">{{ child.name }}</span>
      </router-link>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowDown } from '@element-plus/icons-vue'

type MenuChild = { path: string; name: string }

const props = defineProps<{
  name: string
  icon: object
  children: MenuChild[]
  isChildActive: (path: string) => boolean
}>()

const emit = defineEmits<{
  navigate: []
}>()

const route = useRoute()
const expanded = ref(false)
const panelId = `nav-group-${props.name}`

const isActive = computed(() => props.children.some((child) => props.isChildActive(child.path)))

watch(
  () => route.path,
  () => {
    if (isActive.value) expanded.value = true
  },
  { immediate: true }
)
</script>

<style scoped lang="postcss">
.nav-item {
  @apply flex items-center px-4 py-3 text-gray-700 rounded-lg;
  min-height: 44px;
  box-sizing: border-box;
  font-size: 16px;
  line-height: 20px;
  text-decoration: none;
  cursor: pointer;
  user-select: none;
  touch-action: manipulation;
  -webkit-tap-highlight-color: transparent;
  transition: background-color 0.15s ease, color 0.15s ease;
}

.nav-item:active {
  background: #e5e7eb;
}

.nav-item.active {
  background: var(--admin-brand-soft, #f4efe3);
  color: var(--admin-brand, #6b5420);
}

.nav-group-toggle.active {
  background: transparent;
  color: var(--admin-brand, #6b5420);
}

.nav-group-toggle.active .nav-text {
  font-weight: 600;
}

.nav-item:focus-visible {
  outline: 2px solid var(--admin-brand, #6b5420);
  outline-offset: 2px;
}

.nav-icon {
  @apply mr-3 text-lg;
  flex-shrink: 0;
}

.nav-text {
  @apply font-medium;
  min-width: 0;
  font-size: inherit;
  line-height: inherit;
  overflow-wrap: break-word;
}

.nav-group-toggle {
  width: 100%;
  border: none;
  background: transparent;
  text-align: left;
  font-family: inherit;
  font-weight: inherit;
  color: inherit;
}

.nav-group-toggle.active:active {
  background: #e5e7eb;
}

.nav-chevron {
  margin-left: auto;
  flex-shrink: 0;
  font-size: 14px;
}

.nav-chevron.expanded {
  transform: rotate(180deg);
}

.nav-children {
  @apply ml-3 pl-3 border-l border-gray-200 mb-1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nav-child {
  @apply py-2;
  min-height: 44px;
}

.nav-child.active:active {
  background: #e7dcc4;
}

.nav-child .nav-text {
  font-weight: 400;
}

.nav-child.active .nav-text {
  font-weight: 600;
}

@media (hover: hover) and (pointer: fine) {
  .nav-item {
    font-size: 14px;
  }
  .nav-item:hover {
    background: #f3f4f6;
  }
  .nav-child.active:hover {
    background: var(--admin-brand-soft, #f4efe3);
  }
  .nav-child .nav-text {
    font-size: 13px;
  }
}

@media (pointer: coarse) {
  .nav-item,
  .nav-child {
    min-height: 48px;
  }
  .nav-children {
    gap: 8px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .nav-item,
  .nav-chevron {
    transition: none;
  }
}
</style>