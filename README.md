# 科道书院 · 学生成长画像与活动推荐

这是科道书院内部试点系统，包含：

- GitHub Pages 学生端：首次画像采集与动态跟进问卷；
- Supabase：一次性邀请、版本化问卷、画像、活动和推送名单；
- FastAPI advisor 后台：学生画像、群体洞察、活动匹配、名单确认与网页内复制；
- SiliconFlow `deepseek-ai/DeepSeek-V4-Flash`：结构化、带证据的画像与推荐；
- systemd worker、每日快照和群体报告。

首次采集的第六步采用“三版本奥德赛计划”：当前轨迹延续、原路径失效后的备选，以及暂不考虑金钱和社会期待时最想尝试的人生。三个版本均以结构化字段保存，并在画像中作为假设可能性而非既定承诺处理。

## 学生端

```bash
npm install
cp .env.example .env.local
npm run dev
npm run build
```

入口：

- `/#/onboarding?token=...`
- `/#/survey?token=...`

GitHub Pages workflow 从仓库 Variables 读取：

- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_PUBLISHABLE_KEY`

这两个值可以公开在浏览器中；`SECRET_KEY` 与模型 API Key 绝不能进入 GitHub Variables、前端代码或构建产物。

## Supabase

在 SQL Editor 按文件名顺序执行迁移。新项目先执行
[`202610260001_student_modeling.sql`](supabase/migrations/202610260001_student_modeling.sql)，
已有项目继续执行
[`202610260002_odyssey_plans.sql`](supabase/migrations/202610260002_odyssey_plans.sql)。

匿名用户不能直接操作任何数据表，只能调用：

- `claim_invite_and_submit_onboarding`
- `get_survey_by_token`
- `submit_survey_response`

## Advisor 后台

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/python scripts/hash_password.py
.venv/bin/pytest
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

把生成的 Argon2 字符串保存到 `.env` 的 `ADVISOR_PASSWORD_HASH`。初始凭据为用户指定的 `kedao_college / 123456`，但后台只保存哈希。

生产目录约定为 `/home/eddie-cui/code/discover-backend`。部署配置位于：

- `backend/deploy/systemd/`
- `backend/deploy/nginx/kedao-discover.conf`

后台仅监听内网 `10.19.94.156:8080`。当前是 HTTP 内网试点，严禁直接映射公网；公网开放前必须增加 HTTPS 和更强认证。

## 隐私与模型边界

- 姓名、邮箱、学号只保存在 Supabase，不发送给模型。
- onboarding RPC 会在保存问卷答案前移除上述直接标识。
- 后端再次清洗邮箱、手机号和长数字编号。
- 幸福感数据只用于自愿支持，不作医学诊断，也不能用于普通活动的负面筛选。
- 每个模型结论包含 `evidence_refs`、置信度、生成时间、输入快照和 prompt 版本。
- 邮件发送未实现；系统保存 advisor 确认后的名单，并在受保护页面内提供复制功能。
