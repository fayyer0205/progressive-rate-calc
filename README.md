# 对话分析与差额定率累进计算工具包

本仓库包含两个相对独立的功能模块：

| 功能 | 路径 | 说明 |
|------|------|------|
| **4S 店对话分析与提示词改写** | `/` | 上传对话 Excel，调用 Gemini 分析并改写 AI 电话机器人提示词 |
| **差额定率累进计算** | `/progressive-rate` | 按档位与费率计算总费用，可保存/加载档位模板 |
| **JSON 评分结果解析** | `/json-eval` | 上传 id+JSON 的 Excel，解析为表格并导出 CSV |

- **完整使用说明**：见 [使用说明.md](使用说明.md)（运行方式、各功能操作、分享给同事、常见问题）。
- **打包与交付**：见 [打包说明.md](打包说明.md)（交付物清单、打包命令、交付时说明）。
- **服务器部署**（同事通过链接直接访问）：见 [DEPLOY.md](DEPLOY.md)。

---

## 功能一：4S 店对话分析与提示词改写

将真实 4S 店电话销售顾问与客户的对话数据，转化为可用的 AI 电话机器人提示词。

1. **原始对话数据上传**：支持 Excel（.xlsx / .xls），表格格式为「对话ID」和「对话内容」两列
2. **数据处理及分析**：调用 Gemini #1，根据 System Instructions 分析对话，提取流程节点和话术
3. **原机器人提示词改写**：调用 Gemini #2，根据分析结果改写用户输入的初始提示词
4. **一键执行**：顺序执行「分析 → 改写」，输出最终提示词

## 快速开始

### 1. 安装依赖

```bash
cd conversation-analysis-tool
pip install -r requirements.txt
```

### 2. 配置 Gemini API 密钥

复制 `.env.example` 为 `.env`，填入您的 API 密钥：

```bash
cp .env.example .env
# 编辑 .env，将 your_api_key_here 替换为您的 Gemini API Key
```

API 密钥请在 [Google AI Studio](https://aistudio.google.com/app/apikey) 获取（登录 Google 账号后创建 API Key）。

### 3. 启动服务

```bash
python app.py
```

浏览器访问：http://127.0.0.1:5001

## Excel 格式说明

| 对话ID | 对话内容 |
|--------|----------|
| D001   | 销售：您好，这里是XX汽车4S店... 客户：我想了解一下新款 |
| D001   | 销售：好的，这款车有标准版和豪华版... |
| D002   | 销售：您好... |

- 必须包含「对话ID」「对话内容」两列（列名可含空格）
- 支持 .xlsx 和 .xls，建议使用 .xlsx

## 使用流程

1. 上传 Excel 对话数据
2. 可选：修改「模块2」和「模块3」的 System Instructions（留空则使用默认）
3. 在「模块3」输入您的 AI 电话机器人初始提示词
4. 点击「一键执行」，等待分析 + 改写完成
5. 复制或下载改写后的提示词

## 模型配置

本系统使用 Google Gemini 模型，默认 `gemini-2.0-flash`，可在 `.env` 中修改为其他可用模型，例如：

```
GEMINI_MODEL=gemini-1.5-pro
```

如需提高分析/改写结果长度上限，可在 `.env` 中设置 `GEMINI_MAX_OUTPUT_TOKENS=65536`（默认 65536；部分模型仅支持 8192 时改为 8192）。

## 技术栈

- 后端：Flask + Gemini REST API + pandas + openpyxl
- 前端：原生 HTML / CSS / JavaScript
