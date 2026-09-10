<template>
  <div class="h-screen flex flex-col bg-ink-950 text-slate-100 overflow-hidden">
    <!-- 顶部公告栏（Seko 青绿色） -->
    <div class="h-9 shrink-0 bg-brand-400 text-black flex items-center justify-center gap-3 text-[13px] font-medium relative z-20">
      <span class="hidden sm:inline">Seko 2.0 全新升级：创作 Agent + 无限画布，输入灵感自动策划生成视频</span>
      <span class="sm:hidden">Seko 2.0 全新升级</span>
      <button class="px-3 py-0.5 rounded-full bg-black text-white text-xs hover:bg-ink-800 transition" @click="goExplore">
        立即体验
      </button>
    </div>

    <div class="flex-1 flex min-h-0">
      <!-- 左侧细图标栏（Seko 风格） -->
      <aside class="w-[76px] shrink-0 bg-black border-r border-ink-800 flex flex-col items-center py-4 z-10">
        <!-- Logo -->
        <div class="mb-6 cursor-pointer select-none" @click="goExplore">
          <div class="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-400 to-brand-600 flex items-center justify-center">
            <span class="text-black font-black text-lg">S</span>
          </div>
        </div>

        <!-- 导航 -->
        <nav class="flex flex-col items-center gap-1 flex-1">
          <button
            v-for="item in navItems"
            :key="item.path"
            class="w-[60px] py-2.5 rounded-xl flex flex-col items-center gap-1 transition-colors"
            :class="isActive(item) ? 'bg-ink-800 text-brand-400' : 'text-slate-400 hover:text-white hover:bg-ink-850'"
            @click="$router.push(item.path)"
          >
            <el-icon :size="20"><component :is="item.icon" /></el-icon>
            <span class="text-[11px]">{{ item.label }}</span>
          </button>
        </nav>

        <!-- 底部：登录 / 菜单 -->
        <div class="flex flex-col items-center gap-3">
          <button class="w-[52px] py-1.5 rounded-full bg-white text-black text-xs font-medium hover:bg-slate-200 transition">
            登录
          </button>
          <el-icon :size="18" class="text-slate-500 hover:text-white cursor-pointer"><Menu /></el-icon>
        </div>
      </aside>

      <!-- 主内容 -->
      <main class="flex-1 min-w-0 overflow-y-auto">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { HomeFilled, FolderOpened, Reading, Menu } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()

const navItems = [
  { path: '/explore', label: '首页', icon: HomeFilled },
  { path: '/projects', label: '项目', icon: FolderOpened },
  { path: '/skills', label: '技能社区', icon: Reading },
]

const isActive = (item: { path: string }) => route.path.startsWith(item.path)
const goExplore = () => router.push('/explore')
</script>
