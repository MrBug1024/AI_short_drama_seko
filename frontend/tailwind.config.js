/** @type {import('tailwindcss').Config} */
// Seko 官网视觉规范：纯黑背景 + 青绿(brand) 强调色；rgb() 三元组支持 /80 透明度修饰符
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // 背景色阶（Seko 纯黑深色主题）
        ink: {
          950: 'rgb(5 5 5)',
          900: 'rgb(10 10 10)',
          850: 'rgb(16 16 16)',
          800: 'rgb(24 24 24)',
          750: 'rgb(30 30 30)',
          700: 'rgb(42 42 42)',
          600: 'rgb(64 64 64)',
        },
        // 主品牌色 - Seko 青绿（公告条/强调/输入框高亮）
        brand: {
          50: 'rgb(240 253 250)',
          100: 'rgb(204 251 241)',
          200: 'rgb(153 246 228)',
          300: 'rgb(94 234 212)',
          400: 'rgb(45 224 200)',
          500: 'rgb(20 200 178)',
          600: 'rgb(13 168 150)',
          700: 'rgb(15 134 120)',
          800: 'rgb(17 108 98)',
          900: 'rgb(19 89 82)',
        },
        // 强调色 - 暖黄（会员/皇冠标识）
        accent: {
          300: 'rgb(253 224 138)',
          400: 'rgb(250 204 21)',
          500: 'rgb(234 179 8)',
        },
      },
      fontFamily: {
        sans: ['"PingFang SC"', '"Microsoft YaHei"', '"Helvetica Neue"', 'Helvetica', 'Arial', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"Consolas"', 'monospace'],
      },
      boxShadow: {
        'glow-brand': '0 0 24px rgb(45 224 200 / 0.25)',
        'card': '0 4px 16px rgb(0 0 0 / 0.4)',
      },
      animation: {
        'fade-in': 'fadeIn 0.4s ease-out',
        'slide-up': 'slideUp 0.4s ease-out',
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
}
