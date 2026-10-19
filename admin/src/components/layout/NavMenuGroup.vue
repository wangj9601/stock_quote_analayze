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
        <span class="nav-code">{{ child.code }}</span>
      </router-link>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowDown } from '@element-plus/icons-vue'

type MenuChild = { path: string; name: string; code: string }

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
  @apply flex items-center px-3 py-2;
  min-height: 44px;
  box-sizing: border-box;
  font-size: 14px;
  line-height: 20px;
  color: var(--admin-nav-ink, #f3f1ec);
  border-radius: 2px;
  text-decoration: none;
  cursor: pointer;
  user-select: none;
  touch-action: manipulation;
  -webkit-tap-highlight-color: transparent;
  transition: background-color 0.15s ease, color 0.15s ease;
}

.nav-item:active {
  background: rgba(243, 241, 236, 0.12);
}

.nav-item.active {
  background: var(--admin-manila, #d7b56d);
  color: var(--admin-ink, #1a2332);
}

.nav-group-toggle.active {
  background: transparent;
  color: var(--admin-nav-ink, #f3f1ec);
}

.nav-group-toggle.active .nav-text {
  font-weight: 700;
}

.nav-item:focus-visible {
  outline: 2px solid var(--admin-manila, #d7b56d);
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
  background: rgba(243, 241, 236, 0.12);
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
  margin: 0 0 4px 8px;
  padding-left: 8px;
  border-left: 1px solid rgba(243, 241, 236, 0.28);
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.nav-code {
  margin-left: auto;
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  font-variant-numeric: tabular-nums;
}

.nav-child {
  @apply py-2;
  min-height: 44px;
}

.nav-child.active:active {
  background: #e4c98a;
}

.nav-child .nav-text {
  font-weight: 400;
}

.nav-child.active .nav-text {
  font-weight: 600;
}

@media (hover: hover) and (pointer: fine) {
  .nav-item {
    min-height: 32px;
    font-size: 13px;
    padding-top: 4px;
    padding-bottom: 4px;
  }
  .nav-item:hover {
    background: rgba(243, 241, 236, 0.1);
  }
  .nav-child.active:hover {
    background: var(--admin-manila, #d7b56d);
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