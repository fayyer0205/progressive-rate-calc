# 部署到 GitHub 并获取可分享链接（GitHub Pages）

按以下步骤完成后，他人可通过一个固定链接打开「差额定率累进计算」页面。

---

## 一、在 GitHub 上创建仓库

1. 登录 [GitHub](https://github.com)，用户名：fayyer0205
2. 点击右上角 **+** → **New repository**
3. **Repository name** 填：`progressive-rate-calc`（或任意英文名，例如 `conversation-analysis-tool`）
4. 选择 **Public**，不勾选 “Add a README”
5. 点击 **Create repository**

记下仓库地址，形如：`https://github.com/fayyer0205/progressive-rate-calc`

---

## 二、本地初始化并推送（在项目目录执行）

GitHub 已不再支持用账号密码执行 git 推送，请使用 **Personal Access Token**：

1. 在 GitHub：**Settings** → **Developer settings** → **Personal access tokens** → **Tokens (classic)** → **Generate new token**，勾选 `repo`，生成后复制 token（只显示一次）。
2. 在终端执行（将 `progressive-rate-calc` 换成你上一步的仓库名）：

```bash
cd /Users/huanghaichao/conversation-analysis-tool

git init
git add .gitignore .env.example README.md 使用说明.md 打包说明.md DEPLOY.md GITHUB_PAGES.md
git add app.py gemini_rest.py requirements.txt sample_data.py
git add templates/ static/ docs/
git add progressive_rate_standalone.html
git status
git commit -m "Add progressive rate calculator and GitHub Pages docs"
git branch -M main
git remote add origin https://github.com/fayyer0205/progressive-rate-calc.git
git push -u origin main
```

3. 推送时 **Username** 填：`fayyer0205`，**Password** 处粘贴刚才的 **Token**（不是登录密码）。

---

## 三、开启 GitHub Pages

1. 打开仓库页面：`https://github.com/fayyer0205/progressive-rate-calc`
2. 点击 **Settings** → 左侧 **Pages**
3. **Source** 选 **Deploy from a branch**
4. **Branch** 选 `main`，**Folder** 选 **/docs**，点 **Save**
5. 等待 1～2 分钟，页面上会显示绿色提示和访问地址

---

## 四、你的可分享链接

部署成功后，访问地址为（把 `progressive-rate-calc` 换成你的仓库名）：

**https://fayyer0205.github.io/progressive-rate-calc/**

把上述链接发给同事，对方用浏览器打开即可使用，无需安装任何东西。

---

## 安全提醒

- **不要在聊天或代码里写登录密码。** 已提供的密码请尽快在 GitHub 修改。
- 推送代码请使用 **Personal Access Token**，不要用账号密码；Token 泄露可随时在 GitHub 撤销后重新生成。
