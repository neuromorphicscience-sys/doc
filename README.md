# 公文格式智能规范化系统

本项目采用“GitHub Pages 前端 + 本机 FastAPI 后端”的部署方式。浏览器上传 DOCX 后，本机后端负责安全解析、DeepSeek 结构识别、模板化重建和内容一致性校验。

## 已实现

- 20 MB 以内 `.docx` 上传与 ZIP/DOCX 安全检查
- 段落、表格、图片和内联语义格式的有序抽取
- DeepSeek V4 Flash 结构识别，失败后重试并切换 V4 Pro
- 模型输出 JSON 校验、来源 ID 保留和本地规则降级
- 疑难结构确认界面
- 山东大学简化规则的重建式 DOCX 生成
- 文本、表格和图片一致性校验
- 格式报告、结果下载、立即删除和定时清理
- GitHub Pages 自动构建工作流

## 本机启动

1. 从 `.env.example` 创建本机 `.env`，填写 `DEEPSEEK_API_KEY`。
2. 启动后端：

```bash
./scripts/start-backend.sh
```

3. 另开终端启动前端：

```bash
export PATH="/path/to/node/bin:$PATH"
./scripts/start-frontend.sh
```

本地访问地址为 `http://127.0.0.1:5173`，API 文档为 `http://127.0.0.1:8000/docs`。

## GitHub Pages

仓库的 `Settings > Pages` 中选择 GitHub Actions 作为发布源，并在 `Settings > Secrets and variables > Actions > Variables` 添加：

```text
API_BASE_URL=https://api.example.com/api
```

推送到 `main` 后，`.github/workflows/pages.yml` 会构建并发布前端。前端仓库和构建变量中不得放置 DeepSeek API Key。

## 本机 API 域名

推荐使用 Cloudflare Tunnel，不开放路由器入站端口：

```bash
cloudflared tunnel login
cloudflared tunnel create official-document-api
cloudflared tunnel route dns official-document-api api.example.com
cloudflared tunnel --config deploy/cloudflared-config.yml run official-document-api
```

将 `deploy/cloudflared-config.example.yml` 复制为本机配置并替换域名、Tunnel UUID 和凭据路径。随后把 `.env` 中的 `ALLOWED_ORIGINS` 改为 GitHub Pages 的正式 HTTPS 地址。

## 安全边界

- API Key 只存在本机 `.env`，该文件已被 Git 忽略。
- 文件保存在随机任务目录，默认 24 小时后清理，也可由用户立即删除。
- 文档正文不会作为模型指令执行，但结构识别所需文字会发送给 DeepSeek。
- 当前版本只处理非涉密文档，不支持宏、加密文件、PDF、复杂公式、活动对象和多文档自动拆分。

