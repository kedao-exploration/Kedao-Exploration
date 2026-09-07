# 科道书院 · 探索盲盒

静态单页应用，通过 Supabase REST API 保存每次提交的完整表单数据与生成结果。

## 首次部署

1. 打开 Supabase Dashboard 的 **SQL Editor**。
2. 完整执行 [`supabase.sql`](./supabase.sql)。
3. 打开 GitHub Pages 地址，填写并提交一次测试数据。
4. 在 Supabase **Table Editor → exploration_submissions** 中确认记录。

## 数据安全

- 浏览器仅使用可公开的 Publishable Key。
- 数据表启用 RLS；匿名访问者只能新增，不能读取、修改或删除。
- Secret Key 不应出现在源代码、GitHub 或浏览器中。

## 本地预览

直接打开 `index.html`，或在本目录启动任意静态文件服务器。
