# GitHub 上传命令 — 一键复制

## ⚠️ 重要：先做这个

打开 VS Code 或任何文本编辑器，在项目根目录创建 `.env` 和 `frontend/.env.local` 文件（这些不会被上传）：

### `backend/.env`
```
OPENAI_API_KEY=sk-your-actual-key
# 或者用 Deepseek:
# DEEPSEEK_API_KEY=your-actual-key
```

### `frontend/.env.local`
```
NEXT_PUBLIC_API_BASE=http://localhost:8000/api
```

---

## 完整上传命令（按顺序执行）

### 1️⃣ 进入项目目录
```bash
cd "d:/vscode html/sales-multi-agent"
```

### 2️⃣ 配置 Git（第一次）
```bash
git config user.name "Your Name"
git config user.email "your.email@example.com"
```

### 3️⃣ 初始化 + 提交
```bash
git init
git add .
git commit -m "Initial commit: Multi-Agent Sales Coordination System for Deloitte 2026 Digital Camp Elite Challenge"
```

### 4️⃣ 添加远程仓库
```bash
# ⚠️ 替换 YOUR_USERNAME 和 YOUR_REPO
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git branch -M main
```

### 5️⃣ 推送到 GitHub
```bash
git push -u origin main
```

---

## 🚀 快速复制（一个命令块）

```bash
cd "d:/vscode html/sales-multi-agent" && \
git config user.name "Your Name" && \
git config user.email "your.email@example.com" && \
git init && \
git add . && \
git commit -m "Initial commit: Multi-Agent Sales Coordination System for Deloitte 2026 Digital Camp Elite Challenge" && \
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git && \
git branch -M main && \
git push -u origin main
```

**记得替换：**
- `Your Name` → 你的名字
- `your.email@example.com` → 你的邮箱
- `YOUR_USERNAME` → GitHub 用户名
- `YOUR_REPO` → 仓库名 (如: `sales-multi-agent`)

---

## ✅ 验证上传成功

上传后访问：
```
https://github.com/YOUR_USERNAME/YOUR_REPO
```

应该能看到：
- ✅ `README.md` — 中英文档
- ✅ `backend/` 和 `frontend/` — 完整代码
- ✅ `.env.example` 文件 — 环境模板
- ✅ `.gitignore` — 安全配置
- ❌ 无 `.env` 文件 — 敏感信息被排除

---

## 后续开发

```bash
# 修改代码后
cd "d:/vscode html/sales-multi-agent"
git add .
git commit -m "Your commit message"
git push origin main
```

---

## 🎯 部署到 Railway

1. 访问 https://railway.app
2. New Project → GitHub Repo
3. 连接你的 `sales-multi-agent` 仓库
4. 环境变量：`OPENAI_API_KEY=sk-...`
5. 自动部署完成！

---

**准备好了？开始上传吧！** 🚀
