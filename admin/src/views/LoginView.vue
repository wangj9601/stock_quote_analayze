<template>
  <div class="login-shell">
    <main class="login-stage">
      <div class="login-card">
        <header class="login-mast">
          <h1 class="login-brand">冰枫堂</h1>
          <p class="login-sub">管理端</p>
        </header>

        <form class="login-form" novalidate @submit.prevent="handleLogin">
          <div class="login-fields" :class="{ 'is-invalid': !!error }">
            <div>
              <label for="username" class="sr-only">用户名</label>
              <input
                id="username"
                v-model="form.username"
                name="username"
                type="text"
                required
                autocomplete="username"
                spellcheck="false"
                class="login-field"
                placeholder="用户名"
                :aria-invalid="error ? 'true' : undefined"
                :aria-describedby="error ? 'login-error' : undefined"
              />
            </div>
            <div>
              <label for="password" class="sr-only">密码</label>
              <input
                id="password"
                v-model="form.password"
                name="password"
                type="password"
                required
                autocomplete="current-password"
                class="login-field"
                placeholder="密码"
                :aria-invalid="error ? 'true' : undefined"
                :aria-describedby="error ? 'login-error' : undefined"
              />
            </div>
          </div>

          <p
            v-if="error"
            id="login-error"
            role="alert"
            data-testid="login-error"
            class="login-error"
          >
            {{ error }}
          </p>

          <button
            type="submit"
            class="login-submit"
            :disabled="loading"
            :aria-busy="loading"
          >
            <svg
              v-if="loading"
              class="login-spinner"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2" opacity="0.35" />
              <path
                d="M12 3a9 9 0 0 1 9 9"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="square"
              />
            </svg>
            {{ loading ? '登录中…' : '登录' }}
          </button>
        </form>
      </div>
    </main>

    <footer class="icp-footer">
      <a href="https://beian.miit.gov.cn/" target="_blank" rel="noopener noreferrer">
        京ICP备18061239号-1
      </a>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const form = reactive({
  username: '',
  password: ''
})

const loading = ref(false)
const error = ref('')

const handleLogin = async () => {
  if (!form.username || !form.password) {
    error.value = '请输入用户名和密码'
    return
  }

  loading.value = true
  error.value = ''

  try {
    await authStore.login({
      username: form.username,
      password: form.password
    })

    router.push('/dashboard')
  } catch (err) {
    error.value = err instanceof Error ? err.message : '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-shell {
  min-height: 100vh;
  min-height: 100dvh;
  display: flex;
  flex-direction: column;
  background: #f3f1ec;
  color: #1a2332;
  font-size: 14px;
  caret-color: #234e70;
  color-scheme: light;
  scrollbar-color: #234e70 #f3f1ec;
}

.login-shell ::selection {
  background: #d7b56d;
  color: #1a2332;
}

.login-stage {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px 16px;
}

.login-card {
  width: min(100%, 28rem);
  background: #fff;
  padding: 32px 28px;
  border: 1px solid #c9c3b8;
  border-radius: 2px;
}

.login-mast {
  text-align: center;
}

.login-brand {
  margin: 0;
  font-size: 28px;
  font-weight: 700;
  line-height: 1.2;
  letter-spacing: 0.12em;
  color: #234e70;
}

.login-sub {
  margin: 8px 0 0;
  font-size: 13px;
  line-height: 1.4;
  color: #3e4c59;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 28px;
}

.login-fields {
  border: 1px solid #c9c3b8;
  border-radius: 2px;
  background: #fff;
  overflow: hidden;
}

.login-fields.is-invalid {
  border-color: #c23b3b;
}

.login-fields:focus-within {
  border-color: #234e70;
  outline: 2px solid #234e70;
  outline-offset: 1px;
}

.login-field {
  display: block;
  width: 100%;
  box-sizing: border-box;
  min-height: 44px;
  padding: 11px 12px;
  border: 0;
  border-radius: 0;
  background: #fff;
  color: #1a2332;
  font: inherit;
  font-size: 14px;
  line-height: 1.4;
}

.login-fields > div + div .login-field {
  border-top: 1px solid #e4dfd6;
}

.login-field::placeholder {
  color: #5c6770;
  opacity: 1;
}

.login-field:focus {
  outline: none;
  background: #f6edd6;
}

.login-field:-webkit-autofill,
.login-field:-webkit-autofill:hover {
  -webkit-text-fill-color: #1a2332;
  caret-color: #234e70;
  box-shadow: 0 0 0 1000px #fff inset;
  transition: background-color 9999s ease-out 0s;
}

.login-field:-webkit-autofill:focus {
  -webkit-text-fill-color: #1a2332;
  caret-color: #234e70;
  box-shadow: 0 0 0 1000px #f6edd6 inset;
}

.login-error {
  margin: 0;
  color: #c23b3b;
  font-size: 13px;
  line-height: 1.5;
  text-align: center;
  overflow-wrap: anywhere;
}

.login-submit {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  min-height: 44px;
  padding: 10px 16px;
  border: 1px solid #234e70;
  border-radius: 2px;
  background: #234e70;
  color: #f3f1ec;
  font: inherit;
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.08em;
  cursor: pointer;
}

.login-submit:hover:not(:disabled) {
  background: #1b3d58;
  border-color: #1b3d58;
}

.login-submit:active:not(:disabled) {
  background: #163044;
  border-color: #163044;
}

.login-submit:disabled {
  cursor: wait;
}

.login-submit:focus-visible {
  outline: 2px solid #234e70;
  outline-offset: 2px;
}

.login-spinner {
  width: 16px;
  height: 16px;
  animation: login-spin 0.7s linear infinite;
}

@keyframes login-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .login-spinner {
    animation: none;
  }
}

.icp-footer {
  padding: 16px 16px 20px;
  text-align: center;
}

.icp-footer a {
  color: #3e4c59;
  font-size: 12px;
  line-height: 1.4;
  text-decoration: underline;
  text-decoration-thickness: 1px;
  text-underline-offset: 3px;
  text-decoration-color: #c9c3b8;
}

.icp-footer a:hover {
  color: #234e70;
  text-decoration-color: #234e70;
}

.icp-footer a:focus-visible {
  outline: 2px solid #234e70;
  outline-offset: 2px;
}

@media (max-width: 480px) {
  .login-stage {
    padding: 24px 16px;
  }

  .login-card {
    padding: 28px 20px;
  }

  .login-brand {
    font-size: 26px;
  }
}
</style>
