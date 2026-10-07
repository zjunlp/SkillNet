# 在 JiuwenClaw 中使用 SkillNet 技能库

本教程将指导你在 JiuwenClaw 中通过 SkillNet 技能库搜索、安装并使用海量技能，让你的 AI Agent 能力无限扩展。


https://github.com/user-attachments/assets/28a460c8-45a3-44b6-b34f-bed4a49f2e32


## 简介

**SkillNet** 是一个大规模智能体技能知识库，收录了超过 40 万项高质量技能，将分散的实践经验沉淀为可计算、可检索、可组合的结构化知识网络。

**JiuwenClaw** 是基于 openJiuwen 开源平台开发的智能 AI Agent，现已深度集成 SkillNet，让你在前端"技能"栏目中即可一键搜索、安装和管理技能，真正实现"技能难找、安装繁琐"的痛点。

## 前提条件

- 已安装 JiuwenClaw（安装方式见下方）
- 能够访问 JiuwenClaw 前端界面（支持 Web UI 或客户端）

## 快速安装 JiuwenClaw

如果你尚未安装 JiuwenClaw，请按以下步骤操作：

```bash
# 安装 JiuwenClaw
pip install jiuwenclaw

# 初始化配置（首次启动）
jiuwenclaw-init

# 启动服务
jiuwenclaw-start
```

启动成功后，访问前端界面。

## 使用 SkillNet 搜索并安装技能

### 1. 进入"技能"栏目

在 JiuwenClaw 前端主界面，找到并点击 **技能**（Skills）栏目。

### 2. 打开 SkillNet 搜索弹窗

点击"添加技能"或"搜索技能"按钮，系统将弹出 **SkillNet 搜索窗口**。

### 3. 搜索技能

在搜索框中输入关键词（如"天气"、"浏览器自动化"、"PDF 处理"等），SkillNet 会实时返回匹配的技能列表。每个技能会显示名称、描述、作者等信息。

### 4. 安装技能

- 点击技能右侧的 **安装** 按钮。
- 如果已安装过同名技能，系统会自动进行 **默认覆盖**（保留最新版本）。
- 安装过程中，界面会显示进度提示，并自动禁用重复请求，避免误操作。
- 若安装失败，会精准透传后端错误信息，帮助你快速定位问题。

### 5. 使用技能

安装完成后，该技能会出现在你的本地技能列表中。你可以在与 JiuwenClaw 的对话中直接调用它，或将其纳入任务规划中执行。

## 技能管理

- **更新技能**：当 SkillNet 中有新版本时，重新安装同名技能即可覆盖升级。
- **卸载技能**：在本地技能列表中找到对应技能，点击"卸载"即可移除。
- **查看技能详情**：点击技能可查看其说明、参数、示例等。

## 示例：安装并使用"天气查询"技能

1. 打开 SkillNet 搜索窗口，输入 `weather`。
2. 找到 `weather-forecast` 技能（示例名称），点击安装。
3. 安装成功后，在对话中发送：
   ```
   使用 weather-forecast 技能查询北京未来 7 天的天气并生成简报
   ```
4. JiuwenClaw 会自动调用该技能，并返回结果。

## 更多能力

JiuwenClaw 不仅集成了 SkillNet，还具备以下核心特性，与技能系统协同工作，让智能体更强大：

- **任务自主管理**：支持动态打断、任务追加、优先级调整。
- **Skills 自主演进**：系统会记录执行错误和用户反馈，自动优化技能。
- **上下文压缩与卸载**：显著降低 Token 消耗。
- **持久化记忆系统**：让智能体越来越懂你。
- **原生浏览器操控**：复用现有浏览器状态，避免重复登录验证。
- **多通道接入**：支持小艺、飞书、钉钉、Discord、Telegram、WhatsApp 等。

## 相关链接

- [SkillNet GitHub 仓库](https://github.com/zjunlp/SkillNet)
- [JiuwenClaw 项目地址](https://github.com/openJiuwen-ai/jiuwenclaw)
- [openJiuwen 组织主页](https://github.com/openJiuwen-ai)
- [快速开始指南](https://gitcode.com/openJiuwen/jiuwenclaw/blob/develop/docs/Quickstart.md)

---

通过 SkillNet 与 JiuwenClaw 的深度融合，你将轻松拥有一个"懂你所想、自主演进"的专属 AI 助手。赶快体验吧！
