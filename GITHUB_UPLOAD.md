# 上传到 GitHub 完整步骤

## 前置要求

1. **安装 Git** — https://git-scm.com/
2. **GitHub 账户** — https://github.com
3. **生成 SSH key 或使用 Personal Access Token**

## 步骤 1: 初始化本地 Git 仓库

```bash
cd "d:/vscode html/delotiee_agent"

# 初始化 git
git init

# 配置 Git 用户信息（第一次使用时）
git config user.name "Your Name"
git config user.email "your.email@example.com"

# 全局配置（可选，之后所有仓库都使用）
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

## 步骤 2: 添加所有文件并提交

```bash
# 添加所有文件到 staging
git add .

# 查看要提交的文件（可选）
git status

# 首次提交
git commit -m "Initial commit: Sales Multi-Agent Coordination System for Deloitte Digital Camp Elite Challenge"
```

## 步骤 3: 在 GitHub 上创建新仓库

1. 访问 https://github.com/new
2. **Repository name**: `delotiee-agent` (或自定义名称)
3. **Description**: `Multi-Agent Sales Coordination System | Deloitte 2026 Digital Camp`
4. **Public** (推荐，便于展示)
5. **不勾选** "Initialize this repository with" 选项（我们已有本地代码）
6. 点击 **Create repository**

## 步骤 4: 连接远程仓库并推送

```bash
# 添加远程仓库
# ⚠️ 将 YOUR_USERNAME 替换为你的 GitHub 用户名，YOUR_REPO 为仓库名
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git

# 重命名默认分支为 main（如果当前是 master）
git branch -M main

# 推送代码到 GitHub
git push -u origin main
```

## 步骤 5: 验证

访问 `https://github.com/YOUR_USERNAME/YOUR_REPO` 确认代码已上传。

---

## 完整一键命令（复制粘贴）

```bash
cd "d:/vscode html/delotiee_agent"

git init
git config user.name "Your Name"
git config user.email "your.email@example.com"

git add .
git commit -m "Initial commit: Sales Multi-Agent Coordination System for Deloitte Digital Camp Elite Challenge"

git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git branch -M main
git push -u origin main
```

---

## 常见问题

### Q1: 推送时报 "fatal: unable to access ... 401"

**解决**: 使用 Personal Access Token 而非密码
- 访问 https://github.com/settings/tokens
- 生成新 token（勾选 `repo`）
- 推送时输入 token 而非密码

### Q2: "refusing to merge unrelated histories"

**解决**:
```bash
git pull origin main --allow-unrelated-histories
git push origin main
```

### Q3: 想修改 commit 历史？

```bash
# 修改最后一个 commit 信息
git commit --amend -m "New message"

# 重新推送（注意：会覆盖远程历史，只在未被他人基于该分支工作时使用）
git push --force-with-lease origin main
```

---

## 之后的开发流程

```bash
# 修改代码后
git add .
git commit -m "Add feature / Fix bug"
git push origin main

# 或者创建特性分支
git checkout -b feature/your-feature
git commit -m "Add your-feature"
git push origin feature/your-feature
# 然后在 GitHub 上提 PR
```

---

## 推荐的 README 顶部徽章（可选）

在 README.md 顶部添加：

```markdown
[![Python](https://img.shields.io/badge/Backend-Python%203.11+-blue?logo=python)](backend/requirements.txt)
[![TypeScript](https://img.shields.io/badge/Frontend-TypeScript%205-blue?logo=typescript)](frontend)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?logo=fastapi)](backend)
[![Next.js](https://img.shields.io/badge/Next.js-14-black?logo=next.js)](frontend)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

**For Deloitte 2026 Digital Camp Elite Challenge | Team D**
```

---

## 后续优化

1. 添加 LICENSE 文件（MIT）
2. 设置 GitHub Pages（从 frontend/.next 的静态文件）
3. 添加 Actions CI/CD（自动测试 + 构建）
4. 设置 branch protection rules

---

**准备好了吗？** 按照上面的步骤一步一步来，5分钟内上传到 GitHub 🚀
