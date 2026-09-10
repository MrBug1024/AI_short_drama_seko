import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router'

// Seko 路由结构：首页(Explore) / 我的项目 / 技能社区 + 全屏无限画布
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
    // 无限画布：全屏独立页面（与 Seko 一致）
    path: '/canvas/:id',
    name: 'Canvas',
    component: () => import('@/views/CanvasView.vue'),
    meta: { title: '无限画布' },
  },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

router.afterEach((to) => {
  document.title = `${to.meta.title || 'Seko'} - Seko - World Class AI Video Generation Platform`
})

export default router
