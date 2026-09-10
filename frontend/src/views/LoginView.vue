<template>
  <div class="min-h-screen bg-ink-950 text-slate-100 flex items-center justify-center dot-grid px-4">
    <div class="w-full max-w-md">
      <!-- 顶部品牌 -->
      <div class="flex items-center justify-center gap-3 mb-8">
        <div class="w-12 h-12 rounded-xl bg-gradient-to-br from-brand-400 to-brand-600 flex items-center justify-center shadow-glow-brand">
          <span class="text-black font-black text-2xl">L</span>
        </div>
        <div class="flex flex-col">
          <span class="text-2xl font-black tracking-tight">LBP_M</span>
          <span class="text-xs text-slate-500">AI 短剧创作平台 · 致敬卢米埃尔兄弟</span>
        </div>
      </div>

      <div class="lbp-card p-8 shadow-card">
        <h1 class="text-xl font-semibold mb-1">欢迎回来</h1>
        <p class="text-sm text-slate-500 mb-6">登录后开启你的 AI 短剧创作之旅</p>

        <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent>
          <el-form-item label="邮箱" prop="email">
            <el-input
              v-model="form.email"
              type="email"
              placeholder="your@email.com"
              autocomplete="email"
              size="large"
              :prefix-icon="Message"
            />
          </el-form-item>

          <el-form-item label="密码" prop="password">
            <el-input
              v-model="form.password"
              type="password"
              placeholder="••••••••"
              autocomplete="current-password"
              size="large"
              show-password
              :prefix-icon="Lock"
              @keyup.enter="handleSubmit"
            />
          </el-form-item>

          <el-button
            type="primary"
            size="large"
            class="w-full mt-2"
            :loading="submitting"
            @click="handleSubmit"
          >
            {{ submitting ? '登录中...' : '登录' }}
          </el-button>
        </el-form>

        <div class="mt-6 text-center text-sm text-slate-500">
          还没有账号？
          <router-link to="/register" class="text-brand-400 hover:text-brand-300">立即注册</router-link>
        </div>
      </div>

      <div class="mt-6 text-center text-xs text-slate-600">
        <router-link to="/explore" class="hover:text-slate-400">先逛逛首页</router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { Message, Lock } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const formRef = ref<FormInstance>()
const submitting = ref(false)

const form = reactive({
  email: '',
  password: '',
})

const rules: FormRules = {
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' },
  ],
}

async function handleSubmit() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }
  submitting.value = true
  try {
    await auth.login(form.email, form.password)
    ElMessage.success('登录成功')
    // 跳转到 redirect 参数指定的页面，或首页
    const redirect = (route.query.redirect as string) || '/projects'
    router.replace(redirect)
  } catch (e: any) {
    // axios 拦截器已经弹过错误，这里只打印
    console.error('login failed', e)
  } finally {
    submitting.value = false
  }
}
</script>