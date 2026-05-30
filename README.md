# ex-skill — QQ Chat Persona Distillation

从 QQ 聊天记录蒸馏一个人的 AI persona，让 DeepSeek 模仿 Ta 的语气、价值观和思维模式，集成到 QQ 机器人中自动回复。

## 项目结构

```
ex-skill/
├── tools/
│   ├── persona_distill.py     # 聊天记录分析 + persona 蒸馏
│   └── qq_export.py           # QQ 数据库解密导出
├── persona/
│   ├── system_prompt.md       # 蒸馏后的 persona → DeepSeek system prompt
│   ├── persona_report.md      # 详细人格分析报告
│   └── analysis_data.json     # 量化分析数据（JSON）
├── bot/
│   ├── bot.py                 # NoneBot2 机器人主程序
│   ├── .env.example           # 环境变量示例
│   └── requirements.txt       # Python 依赖
└── README.md
```

## 快速开始

### 第一步：导出 QQ 聊天记录

> **前提条件**：Windows + QQ NT 版本（v9.9+），需要知道对方的 QQ 号

```bash
# 1. 从运行中的 QQ 进程提取数据库密钥（PowerShell 管理员权限）
powershell -ExecutionPolicy Bypass -File tools/windows_ntqq_get_key.ps1

# 2. 运行导出脚本
python tools/qq_export.py \
  --db-path "C:\Users\<用户名>\Documents\Tencent Files\<QQ号>\nt_qq\nt_db\nt_msg.db" \
  --key "<从步骤1获取的密钥>" \
  --partner-qq "<对方QQ号>" \
  --output "chat-data/full_chat.txt"
```

### 第二步：蒸馏 Persona

```bash
# 分析聊天记录，生成 persona
python tools/persona_distill.py \
  --input chat-data/full_chat.txt \
  --output persona/
```

这会生成：
- `persona/system_prompt.md` — 可直接用于 DeepSeek API 的 system prompt
- `persona/persona_report.md` — 人格特征分析报告
- `persona/analysis_data.json` — 词频、情感分布等量化数据

### 第三步：部署 QQ 机器人

#### 3.1 安装 LLOneBot（QQ 连接层）

1. 下载 [LLOneBot](https://github.com/LLOneBot/LLOneBot) 最新 Release
2. 将 `.dll` 文件放入 QQ 安装目录的 `plugins` 文件夹
3. 重启 QQ，进入 LLOneBot 设置 → 启用反向 WebSocket → 地址填 `ws://127.0.0.1:8080/onebot/v11/ws`

#### 3.2 配置并启动机器人

```bash
cd bot/
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 文件，填入你的 DeepSeek API Key
python bot.py
```

### 第四步：和"Ta"聊天

在 QQ 中给机器人的 QQ 号发消息，它会用蒸馏后的 persona 自动回复。

## 技术栈

| 层级 | 组件 | 说明 |
|------|------|------|
| QQ 连接层 | [LLOneBot](https://github.com/LLOneBot/LLOneBot) | QQ NT 插件，提供 OneBot v11 API |
| 机器人框架 | [NoneBot2](https://v2.nonebot.dev/) | Python 异步机器人框架 |
| AI 引擎 | [DeepSeek API](https://platform.deepseek.com/) | deepseek-chat 模型 |
| 数据导出 | SQLCipher + Protobuf | QQ NT 数据库解密与消息解析 |

## Persona 蒸馏原理

双层蒸馏架构：

1. **表层特征**：语气词频率、消息长度、标点偏好、表情包使用率
2. **深层特征**：情感反应模式、思维逻辑倾向、价值观线索、对话节奏

分析方法：
- 词频 + N-gram 分析 → 语言风格
- 情感关键词分类 → 情感模式
- 逻辑连接词统计 → 思维模式
- 对话片段聚类 → 互动模式

## 自定义

如果你想让 persona 更偏向某种风格，编辑 `persona/system_prompt.md` 中的 system prompt。

关键调整参数：
- **日常对话权重**：提高 `## 对话习惯细节` 中的日常场景描述
- **表情包权重**：增加 `## 表情包/emoji 使用` 中的频率和种类
- **语气强度**：调整 `## 语言风格` 中的用词密度

## 隐私说明

- 所有数据处理都在本地进行
- 聊天记录不会上传到任何服务器
- DeepSeek API 调用只包含当前对话上下文 + system prompt
- 建议在对方知情同意的前提下使用

## License

MIT
