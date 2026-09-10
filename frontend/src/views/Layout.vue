<template>
  <div class="h-screen flex flex-col bg-ink-950 text-slate-100 overflow-hidden">
    <!-- 顶部公告栏（LBP_M 青绿色） -->
    <div class="h-9 shrink-0 bg-brand-400 text-black flex items-center justify-center gap-3 text-[13px] font-medium relative z-20">
      <span class="hidden sm:inline">LBP_M 1.0 上线：登录后开启你的 AI 短剧创作之旅，致敬电影之父卢米埃尔兄弟</span>
      <span class="sm:hidden">LBP_M 1.0 上线</span>
      <button class="px-3 py-0.5 rounded-full bg-black text-white text-xs hover:bg-ink-800 transition" @click="goExplore">
        立即体验
      </button>
    </div>

    <div class="flex-1 flex min-h-0">
      <!-- 左侧细图标栏（LBP_M 风格） -->
      <aside class="w-[76px] shrink-0 bg-black border-r border-ink-800 flex flex-col items-center py-4 z-10">
        <!-- Logo -->
        <div class="mb-6 cursor-pointer select-none" @click="goExplore" title="LBP_M - 致敬卢米埃尔兄弟">
          <div class="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-400 to-brand-600 flex items-center justify-center">
            <span class="text-black font-black text-lg">L</span>
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

        <!-- 底部：登录 / 用户菜单 -->
        <div class="flex flex-col items-center gap-3">
          <!-- 未登录：跳转到登录页 -->
          <button
            v-if="!auth.isLoggedIn"
            class="w-[52px] py-1.5 rounded-full bg-white text-black text-xs font-medium hover:bg-slate-200 transition"
            @click="$router.push('/login')"
          >
            登录
          </button>
          <!-- 已登录：头像下拉（点击显示用户名 + 登出） -->
          <el-dropdown v-else trigger="click" @command="handleUserCommand">
            <div class="w-9 h-9 rounded-full bg-gradient-to-br from-brand-400 to-brand-600 flex items-center justify-center cursor-pointer hover:ring-2 hover:ring-brand-500/40 transition" :title="auth.user?.email">
              <span class="text-black font-bold text-sm">{{ avatarText }}</span>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item disabled>
                  <div class="flex flex-col items-start">
                    <span class="text-xs text-slate-500">已登录</span>
                    <span class="text-sm text-slate-100 truncate max-w-[180px]">{{ auth.user?.email }}</span>
                  </div>
                </el-dropdown-item>
                <el-dropdown-item command="logout">
                  <el-icon><SwitchButton /></el-icon>
                  <span>退出登录</span>
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
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
import { ElMessage } from 'element-plus'
import { HomeFilled, FolderOpened, Reading, Menu, SwitchButton } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const navItems = [
  { path: '/explore', label: '首页', icon: HomeFilled },
  { path: '/projects', label: '项目', icon: FolderOpened },
  { path: '/skills', label: '技能社区', icon: Reading },
]

const isActive = (item: { path: string }) => route.path.startsWith(item.path)
const goExplore = () => router.push('/explore')

// 头像首字（display_name 第一字符或 email 首字母）
const avatarText = computed(() => {
  const u = auth.user
  if (!u) return 'L'
  const name = (u.display_name || u.email || 'L').trim()
  return name.charAt(0).toUpperCase()
})

// 顶部下拉菜单：仅处理登出
function handleUserCommand(cmd: string) {
  if (cmd === 'logout') {
    auth.logout()
    ElMessage.success('已退出登录')
    router.push('/explore')
  }
}
</script>
