// 登录页面功能模块
const LoginPage = {
    // 初始化
    init() {
        this.bindEvents();
        this.checkRememberedUser();
        this.initFormValidation();
        this.checkIfAlreadyLoggedIn();
    },

    // 检查是否已登录，如果已登录则跳转到首页
    async checkIfAlreadyLoggedIn() {
        try {
            const token = localStorage.getItem('access_token');
            const response = await fetch(`${API_BASE_URL}/api/auth/status`, {
                headers: token ? { 'Authorization': 'Bearer ' + token } : {},
                // credentials: 'include', // 不需要 cookie
            });
            const result = await response.json();
            
            if (result.success && result.logged_in) {
                // 已登录，跳转到首页
                window.location.href = 'index.html';
            }
        } catch (error) {
            console.error('检查登录状态失败:', error);
        }
    },

    // 绑定事件
    bindEvents() {
        // 登录表单提交
        document.getElementById('loginForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleLogin();
        });

        // 演示登录按钮（如果存在）
        const demoBtn = document.getElementById('demoLoginBtn');
        if (demoBtn) {
            demoBtn.addEventListener('click', () => {
                this.demoLogin();
            });
        }

        // 密码显示切换
        const passwordToggle = document.getElementById('passwordToggle');
        if (passwordToggle) {
            passwordToggle.addEventListener('click', () => {
                this.togglePasswordVisibility();
            });
        }

        // 注册相关事件
        const registerLink = document.getElementById('registerLink');
        if (registerLink) {
            registerLink.addEventListener('click', (e) => {
                e.preventDefault();
                this.showRegisterModal();
            });
        }

        const closeRegister = document.getElementById('closeRegister');
        if (closeRegister) {
            closeRegister.addEventListener('click', () => {
                this.hideRegisterModal();
            });
        }

        const registerForm = document.getElementById('registerForm');
        if (registerForm) {
            registerForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.handleRegister();
            });
        }

        // 模态框外部点击关闭
        const registerModal = document.getElementById('registerModal');
        if (registerModal) {
            registerModal.addEventListener('click', (e) => {
                if (e.target.id === 'registerModal') {
                    this.hideRegisterModal();
                }
            });
        }

        // 忘记密码
        const forgotPassword = document.querySelector('.forgot-password');
        if (forgotPassword) {
            forgotPassword.addEventListener('click', (e) => {
                e.preventDefault();
                this.handleForgotPassword();
            });
        }

        // 回车键登录
        document.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !document.getElementById('registerModal')?.style.display) {
                const loginBtn = document.getElementById('loginBtn');
                if (!loginBtn.disabled) {
                    loginBtn.click();
                }
            }
        });
    },

    // 处理登录
    async handleLogin() {
        const form = document.getElementById('loginForm');
        const formData = new FormData(form);
        const username = formData.get('username').trim();
        const password = formData.get('password');
        const rememberMe = document.getElementById('rememberMe').checked;

        // 表单验证
        if (!this.validateLoginForm(username, password)) {
            return;
        }

        // 显示加载状态
        this.setLoginButtonLoading(true);

        try {
            // 调用后端登录API
            const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                // credentials: 'include', // 不需要 cookie
                body: JSON.stringify({
                    username: username,
                    password: password
                })
            });

            const result = await response.json();
            
            if (response.ok && result.access_token && result.user) {
                // 登录成功，保存token
                this.handleLoginSuccess(result.user, rememberMe, result.access_token);
            } else {
                // 登录失败
                this.showToast(result.message || '登录失败', 'error');
                this.setLoginButtonLoading(false);
            }
        } catch (error) {
            console.error('登录请求失败:', error);
            this.showToast('网络连接失败，请检查网络后重试', 'error');
            this.setLoginButtonLoading(false);
        }
    },

    // 演示登录
    async demoLogin() {
        document.getElementById('username').value = 'demo';
        document.getElementById('password').value = 'demo123';
        
        this.showToast('已填入演示账户信息，点击登录按钮继续', 'success');
        
        // 自动聚焦到登录按钮
        setTimeout(() => {
            document.getElementById('loginBtn').focus();
        }, 500);
    },

    // 登录成功处理
    handleLoginSuccess(user, rememberMe, accessToken) {
        // 添加登录成功动画效果
        this.playSuccessAnimation();
        
        // 保存用户信息到 localStorage
        const userInfo = {
            username: user.username,
            id: user.id,
            loginTime: new Date().toISOString(),
            isLoggedIn: true
        };
        localStorage.setItem('userInfo', JSON.stringify(userInfo));
        // 保存 access_token
        if (accessToken) {
            localStorage.setItem('access_token', accessToken);
        }
        // 如果记住我，保存用户名
        if (rememberMe) {
            localStorage.setItem('rememberedUsername', user.username);
        } else {
            localStorage.removeItem('rememberedUsername');
        }

        this.showToast(`登录成功，欢迎回来！`, 'success');

        // 延迟跳转到首页
        setTimeout(() => {
            window.location.href = 'index.html';
        }, 1500);
    },

    // 播放登录成功动画
    playSuccessAnimation() {
        const logo = document.querySelector('.logo h1');
        const loginBox = document.querySelector('.login-box');
        
        if (logo) {
            // 为logo添加成功动画类
            logo.style.transition = 'all 0.8s cubic-bezier(0.25, 0.46, 0.45, 0.94)';
            logo.style.transform = 'scale(1.05)';
            logo.style.filter = 'drop-shadow(0 0 20px rgba(102, 126, 234, 0.3))';
        }
        
        if (loginBox) {
            // 为登录框添加轻微的浮动效果
            loginBox.style.transition = 'all 0.8s cubic-bezier(0.25, 0.46, 0.45, 0.94)';
            loginBox.style.transform = 'translateY(-5px)';
            loginBox.style.boxShadow = '0 25px 50px rgba(0, 0, 0, 0.15)';
        }
        
        // 800ms后恢复原状
        setTimeout(() => {
            if (logo) {
                logo.style.transform = 'scale(1)';
                logo.style.filter = 'none';
            }
            if (loginBox) {
                loginBox.style.transform = 'translateY(0)';
                loginBox.style.boxShadow = '0 20px 40px rgba(0, 0, 0, 0.1)';
            }
        }, 800);
    },

    // 表单验证
    validateLoginForm(username, password) {
        if (!username) {
            this.showToast('请输入用户名', 'warning');
            document.getElementById('username').focus();
            return false;
        }

        if (!password) {
            this.showToast('请输入密码', 'warning');
            document.getElementById('password').focus();
            return false;
        }

        if (username.length < 2) {
            this.showToast('用户名至少需要2个字符', 'warning');
            document.getElementById('username').focus();
            return false;
        }

        if (password.length < 6) {
            this.showToast('密码至少需要6个字符', 'warning');
            document.getElementById('password').focus();
            return false;
        }

        return true;
    },

    // 设置登录按钮加载状态
    setLoginButtonLoading(loading) {
        const btn = document.getElementById('loginBtn');
        const btnText = btn.querySelector('.btn-text');
        const btnLoading = btn.querySelector('.btn-loading');

        if (loading) {
            btn.classList.add('loading');
            btn.disabled = true;
            if (btnText) btnText.style.display = 'none';
            if (btnLoading) btnLoading.style.display = 'inline';
        } else {
            btn.classList.remove('loading');
            btn.disabled = false;
            if (btnText) btnText.style.display = 'inline';
            if (btnLoading) btnLoading.style.display = 'none';
        }
    },

    // 切换密码可见性
    togglePasswordVisibility() {
        const passwordInput = document.getElementById('password');
        const toggleBtn = document.getElementById('passwordToggle');
        
        if (passwordInput.type === 'password') {
            passwordInput.type = 'text';
            toggleBtn.textContent = '🙈';
        } else {
            passwordInput.type = 'password';
            toggleBtn.textContent = '👁️';
        }
    },

    // 显示注册模态框
    showRegisterModal() {
        const modal = document.getElementById('registerModal');
        if (modal) {
            modal.style.display = 'flex';
            const usernameInput = document.getElementById('regUsername');
            if (usernameInput) usernameInput.focus();
        }
    },

    // 隐藏注册模态框
    hideRegisterModal() {
        const modal = document.getElementById('registerModal');
        const form = document.getElementById('registerForm');
        if (modal) modal.style.display = 'none';
        if (form) form.reset();
    },

    // 处理注册
    async handleRegister() {
        const form = document.getElementById('registerForm');
        const formData = new FormData(form);
        
        const username = formData.get('username').trim();
        const email = formData.get('email').trim();
        const password = formData.get('password');
        const confirmPassword = formData.get('confirmPassword');

        // 注册表单验证
        if (!this.validateRegisterForm(username, email, password, confirmPassword)) {
            return;
        }

        try {
            // 调用后端注册API
            const response = await fetch(`${API_BASE_URL}/api/auth/register`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'include',
                body: JSON.stringify({
                    username: username,
                    email: email,
                    password: password
                })
            });

            const result = await response.json();
            
            if (result.success) {
                this.showToast('注册成功！请使用新账户登录', 'success');
                this.hideRegisterModal();
                
                // 自动填入用户名
                document.getElementById('username').value = username;
                document.getElementById('password').focus();
            } else {
                this.showToast(result.message || '注册失败', 'error');
            }
            
        } catch (error) {
            console.error('注册请求失败:', error);
            this.showToast('网络连接失败，请检查网络后重试', 'error');
        }
    },

    // 注册表单验证
    validateRegisterForm(username, email, password, confirmPassword) {
        if (!username) {
            this.showToast('请输入用户名', 'warning');
            return false;
        }

        if (username.length < 3) {
            this.showToast('用户名至少需要3个字符', 'warning');
            return false;
        }

        if (!email) {
            this.showToast('请输入邮箱地址', 'warning');
            return false;
        }

        if (!this.isValidEmail(email)) {
            this.showToast('请输入有效的邮箱地址', 'warning');
            return false;
        }

        if (!password) {
            this.showToast('请输入密码', 'warning');
            return false;
        }

        if (password.length < 6) {
            this.showToast('密码至少需要6个字符', 'warning');
            return false;
        }

        if (password !== confirmPassword) {
            this.showToast('两次输入的密码不一致', 'warning');
            return false;
        }

        return true;
    },

    // 邮箱格式验证
    isValidEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    },

    // 忘记密码处理
    handleForgotPassword() {
        this.showToast('忘记密码功能暂未开放，请联系管理员', 'warning');
    },

    // 检查记住的用户
    checkRememberedUser() {
        const rememberedUsername = localStorage.getItem('rememberedUsername');
        if (rememberedUsername) {
            const usernameInput = document.getElementById('username');
            const rememberMeCheckbox = document.getElementById('rememberMe');
            const passwordInput = document.getElementById('password');
            
            if (usernameInput) usernameInput.value = rememberedUsername;
            if (rememberMeCheckbox) rememberMeCheckbox.checked = true;
            if (passwordInput) passwordInput.focus();
        }
    },

    // 初始化表单验证
    initFormValidation() {
        // 实时验证用户名
        const usernameInput = document.getElementById('username');
        if (usernameInput) {
            usernameInput.addEventListener('input', (e) => {
                this.validateInputField(e.target, this.validateUsername);
            });
        }

        // 实时验证密码
        const passwordInput = document.getElementById('password');
        if (passwordInput) {
            passwordInput.addEventListener('input', (e) => {
                this.validateInputField(e.target, this.validatePassword);
            });
        }

        // 注册表单实时验证
        const regUsernameInput = document.getElementById('regUsername');
        if (regUsernameInput) {
            regUsernameInput.addEventListener('input', (e) => {
                this.validateInputField(e.target, this.validateUsername);
            });
        }

        const regEmailInput = document.getElementById('regEmail');
        if (regEmailInput) {
            regEmailInput.addEventListener('input', (e) => {
                this.validateInputField(e.target, this.validateEmail);
            });
        }

        const regPasswordInput = document.getElementById('regPassword');
        if (regPasswordInput) {
            regPasswordInput.addEventListener('input', (e) => {
                this.validateInputField(e.target, this.validatePassword);
            });
        }

        const confirmPasswordInput = document.getElementById('confirmPassword');
        if (confirmPasswordInput) {
            confirmPasswordInput.addEventListener('input', (e) => {
                this.validateConfirmPassword();
            });
        }
    },

    // 验证输入字段
    validateInputField(input, validator) {
        const value = input.value.trim();
        const isValid = validator.call(this, value);
        
        if (value && !isValid) {
            input.style.borderColor = '#dc2626';
        } else {
            input.style.borderColor = '#e5e7eb';
        }
    },

    // 用户名验证规则
    validateUsername(username) {
        return username.length >= 3;
    },

    // 密码验证规则
    validatePassword(password) {
        return password.length >= 6;
    },

    // 邮箱验证规则
    validateEmail(email) {
        return this.isValidEmail(email);
    },

    // 确认密码验证
    validateConfirmPassword() {
        const passwordInput = document.getElementById('regPassword');
        const confirmPasswordInput = document.getElementById('confirmPassword');
        
        if (!passwordInput || !confirmPasswordInput) return;
        
        const password = passwordInput.value;
        const confirmPassword = confirmPasswordInput.value;
        
        if (confirmPassword && password !== confirmPassword) {
            confirmPasswordInput.style.borderColor = '#dc2626';
        } else {
            confirmPasswordInput.style.borderColor = '#e5e7eb';
        }
    },

    // 显示提示消息
    showToast(message, type = 'info') {
        const toast = document.getElementById('toast');
        if (toast) {
            toast.textContent = message;
            toast.className = `toast ${type}`;
            toast.classList.add('show');

            setTimeout(() => {
                toast.classList.remove('show');
            }, 3000);
        } else {
            // 如果没有toast元素，使用alert作为后备
            alert(message);
        }
    }
};

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    // 初始化登录页面
    LoginPage.init();
}); 