import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

// LBP_M 路由结构：首页(Explore) / 我的项目 / 技能社区 + 全屏无限画布
// 鉴权：未登录访问需要登录的页面（meta.requiresAuth）会重定向到 /login
const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: () => import('@/views/Layout.vue'),
    redirect: '/explore',
    children: [
      {
        path: 'explore',
        name: 'Explore',
        component: () => import('@/views/HomeView.vue'),
        meta: { title: '首页' },
      },
      {
        path: 'projects',
        name: 'Projects',
        component: () => import('@/views/ProjectsView.vue'),
        meta: { title: '我的项目' },
      },
      {
        path: 'skills',
        name: 'Skills',
        component: () => import('@/views/SkillsView.vue'),
        meta: { title: '技能社区' },
      },
    ],
  },
  {
    // 无限画布：全屏独立页面（与 OiiOii 一致）
    path: '/canvas/:id',
    name: 'Canvas',
    component: () => import('@/views/CanvasView.vue'),
    meta: { title: '无限画布', requiresAuth: true },
  },
  {
    // 登录/注册：全屏独立页面（不要顶栏/侧栏）
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginView.vue'),
    meta: { title: '登录' },
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/RegisterView.vue'),
    meta: { title: '注册' },
  },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

// 路由守卫：meta.requiresAuth 的页面未登录则跳转登录页
router.beforeEach((to) => {
  if (to.meta.requiresAuth) {
    const auth = useAuthStore()
    if (!auth.isLoggedIn) {
      return { path: '/login', query: { redirect: to.fullPath } }
    }
  }
  return true
})

router.afterEach((to) => {
  document.title = `${to.meta.title || 'LBP_M'} - LBP_M · AI 短剧创作平台`
})

export default router
