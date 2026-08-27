<template>
  <div class="nav-group">
    <button
      type="button"
      class="nav-item nav-group-toggle"
      :class="{ active: isActive }"
      @click="expanded = !expanded"
    >
      <el-icon class="nav-icon">
        <component :is="icon" />
      </el-icon>
      <span class="nav-text">{{ name }}</span>
      <el-icon class="nav-chevron" :class="{ expanded }">
        <ArrowDown />
      </el-icon>
    </button>
    <div v-show="expanded" class="nav-children">
      <router-link
        v-for="child in children"
        :key="child.path"
        :to="child.path"
        class="nav-item nav-child"
        :class="{ active: isChildActive(child.path) }"
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
  @apply flex items-center px-4 py-3 text-gray-700 rounded-lg transition-colors hover:bg-gray-100;
  font-size: 14px;
  line-height: 20px;
  text-decoration: none;
  cursor: pointer;
  user-select: none;
}

.nav-item.active {
  @apply bg-blue-50 text-blue-700;
}

.nav-icon {
  @apply mr-3 text-lg;
}

.nav-text {
  @apply font-medium;
  font-size: inherit;
  line-height: inherit;
}

.nav-group-toggle {
  width: 100%;
  border: none;
  background: transparent;
  text-align: left;
  font: inherit;
  color: inherit;
}

.nav-chevron {
  margin-left: auto;
  font-size: 14px;
}

.nav-chevron.expanded {
  transform: rotate(180deg);
}

.nav-children {
  @apply ml-3 pl-3 border-l border-gray-200 space-y-1 mb-1;
}

.nav-child {
  @apply py-2;
}

.nav-child .nav-text {
  font-size: 13px;
  font-weight: 400;
}
</style>