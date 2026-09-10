<template>
  <div class="px-6 py-8 max-w-6xl mx-auto">
    <div class="flex items-center justify-between mb-2">
      <h1 class="seko-section-title !mb-0">技能社区</h1>
    </div>
    <p class="text-sm text-slate-500 mb-6">安装创作技能，让 AI 按你的流程自动策划、分镜、生成。</p>

    <!-- 分类筛选 -->
    <div class="flex flex-wrap items-center gap-2 mb-6">
      <button
        v-for="c in categoryTabs"
        :key="c.key"
        class="px-3 py-1.5 rounded-full text-xs transition-colors"
        :class="category === c.key ? 'bg-white text-black font-medium' : 'bg-ink-800 text-slate-400 hover:text-white'"
        @click="category = c.key"
      >
        {{ c.label }}
      </button>
    </div>

    <!-- 技能卡片 -->
    <div v-if="filtered.length" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <div v-for="s in filtered" :key="s.id" class="seko-card seko-card-hover p-5 flex flex-col">
        <div class="flex items-start gap-3">
          <div class="w-11 h-11 shrink-0 rounded-xl bg-brand-500/10 border border-brand-500/30 flex items-center justify-center text-brand-400 text-lg font-bold">
            {{ s.name.slice(0, 1) }}
          </div>
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2">
              <span class="text-sm font-medium text-slate-100 truncate">{{ s.name }}</span>
              <span v-if="s.is_builtin" class="seko-tag shrink-0">官方</span>
            </div>
            <div class="text-xs text-slate-500 mt-0.5">{{ categoryLabel(s.category) }}</div>
          </div>
        </div>

        <p class="text-xs text-slate-400 leading-relaxed mt-3 line-clamp-3 flex-1">{{ s.description }}</p>

        <div class="flex items-center justify-between mt-4">
          <span class="text-xs text-slate-500">使用 {{ s.usage_count }} 次</span>
          <button
            class="px-4 py-1.5 rounded-full text-xs font-medium transition-colors"
            :class="s.installed ? 'bg-ink-750 text-slate-300 hover:text-white' : 'bg-white text-black hover:bg-slate-200'"
            @click="toggle(s)"
          >
            {{ s.installed ? '已安装' : '安装' }}
          </button>
        </div>
      </div>
    </div>

    <div v-else class="py-24 text-center text-slate-600 text-sm">该分类下暂无技能</div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { skillsApi } from '@/api'
import type { Skill } from '@/api/types'

const skills = ref<Skill[]>([])
const category = ref('')

const categoryTabs = [
  { key: '', label: '全部' },
  { key: 'drama', label: '短剧' },
  { key: 'comic', label: '漫剧' },
  { key: 'knowledge', label: '知识' },
  { key: 'ecommerce', label: '电商广告' },
  { key: 'animation', label: '动画' },
  { key: 'translate', label: '出海转绘' },
]

const categoryLabel = (c: string) =>
  categoryTabs.find((t) => t.key === c)?.label || c || '通用'

const filtered = computed(() =>
  category.value ? skills.value.filter((s) => s.category === category.value) : skills.value,
)

const load = async () => {
  try {
    skills.value = await skillsApi.list()
  } catch {
    /* ignore */
  }
}

const toggle = async (s: Skill) => {
  try {
    await skillsApi.toggle(s.id, !s.installed)
    s.installed = !s.installed
    ElMessage.success(s.installed ? `已安装「${s.name}」` : `已卸载「${s.name}」`)
  } catch {
    /* ignore */
  }
}

onMounted(load)
</script>
