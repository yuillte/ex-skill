"""
ex-skill QQ Bot — NoneBot2 + DeepSeek API
使用蒸馏后的 persona 自动回复 QQ 消息
"""
import os
import re
from pathlib import Path
from collections import defaultdict
from dotenv import load_dotenv
from openai import OpenAI

# ============================================================
# 配置加载
# ============================================================
load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
BOT_QQ = os.getenv("BOT_QQ", "")
ALLOWED_USERS = os.getenv("ALLOWED_USERS", "").split(",") if os.getenv("ALLOWED_USERS", "") else []
MEMORY_ROUNDS = int(os.getenv("MEMORY_ROUNDS", "10"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.8"))
PERSONA_PROMPT_FILE = os.getenv("PERSONA_PROMPT_FILE", "../persona/system_prompt.md")

# ============================================================
# 加载 Persona System Prompt
# ============================================================
def load_persona_prompt() -> str:
    """加载蒸馏后的 persona system prompt"""
    prompt_path = Path(__file__).parent / PERSONA_PROMPT_FILE
    if prompt_path.exists():
        with open(prompt_path, 'r', encoding='utf-8') as f:
            content = f.read()
        print(f"[Persona] 已加载 persona prompt ({len(content)} 字符)")
        return content
    else:
        print(f"[Persona] WARNING: 未找到 persona prompt 文件: {prompt_path}")
        return "你是一个正在和男朋友聊天的女生，请自然地回复。"

SYSTEM_PROMPT = load_persona_prompt()

# ============================================================
# DeepSeek API 客户端（兼容 OpenAI SDK）
# ============================================================
client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL,
)

# ============================================================
# 对话记忆（简单的短期记忆）
# ============================================================
# 每个用户保留最近 N 轮对话
conversation_memory: dict[str, list[dict[str, str]]] = defaultdict(list)

def get_memory(user_id: str) -> list[dict[str, str]]:
    return conversation_memory[user_id]

def add_to_memory(user_id: str, role: str, content: str):
    memory = conversation_memory[user_id]
    memory.append({"role": role, "content": content})
    # 保留最近 N 轮（一轮 = 用户 + 助手各一条）
    max_messages = MEMORY_ROUNDS * 2
    if len(memory) > max_messages:
        conversation_memory[user_id] = memory[-max_messages:]

def clear_memory(user_id: str):
    conversation_memory[user_id] = []

# ============================================================
# AI 回复生成
# ============================================================
def generate_reply(user_id: str, user_message: str) -> str:
    """调用 DeepSeek 生成回复"""
    memory = get_memory(user_id)

    # 构建消息列表
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # 加入历史记忆
    for msg in memory:
        messages.append(msg)

    # 加入当前消息
    messages.append({"role": "user", "content": user_message})

    try:
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=messages,
            temperature=TEMPERATURE,
            max_tokens=150,  # 限制长度，匹配短消息风格
            top_p=0.9,
        )
        reply = response.choices[0].message.content.strip()

        # 过滤掉 AI 可能会说的不该说的话
        if any(kw in reply for kw in ["作为一个AI", "根据训练", "我是一个", "很抱歉"]):
            print(f"[Filter] 过滤了疑似AI回复: {reply[:50]}...")
            return "嗯？你刚说啥 [大表情]"

        return reply

    except Exception as e:
        print(f"[DeepSeek Error] {e}")
        return "等下噢 我这边有点卡 [大表情]"

# ============================================================
# 消息处理
# ============================================================
def is_allowed_user(user_id: str) -> bool:
    """检查用户是否在允许列表中"""
    if not ALLOWED_USERS or ALLOWED_USERS == ['']:
        return True  # 允许所有人
    return user_id in ALLOWED_USERS

def process_message(user_id: str, user_name: str, message: str) -> str | None:
    """
    处理收到的消息，返回 AI 回复。返回 None 表示不回复。
    """
    # 权限检查
    if not is_allowed_user(user_id):
        return None

    # 清理消息
    msg = message.strip()
    if not msg:
        return None

    # 特殊命令
    if msg == "/reset":
        clear_memory(user_id)
        return "嗯嗯 重新开始了 [大表情]"

    if msg == "/memory":
        mem = get_memory(user_id)
        return f"记得 {len(mem)//2} 轮对话呢"

    # 将用户消息加入记忆
    add_to_memory(user_id, "user", f"{user_name}: {msg}")

    # 生成回复
    reply = generate_reply(user_id, msg)

    # 将 AI 回复加入记忆
    add_to_memory(user_id, "assistant", reply)

    return reply

# ============================================================
# NoneBot2 适配器（OneBot v11）
# ============================================================
import nonebot
from nonebot import on_message, get_driver
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, GroupMessageEvent, PrivateMessageEvent
from nonebot.rule import Rule

driver = get_driver()

@driver.on_startup
async def on_startup():
    print("=" * 50)
    print("ex-skill QQ Bot 启动中...")
    print(f"  DeepSeek Model: {DEEPSEEK_MODEL}")
    print(f"  Memory Rounds: {MEMORY_ROUNDS}")
    print(f"  Allowed Users: {ALLOWED_USERS if ALLOWED_USERS else '所有人'}")
    print(f"  Temperature: {TEMPERATURE}")
    print("=" * 50)

# 只回复私聊消息的规则
async def is_private(event: MessageEvent) -> bool:
    return isinstance(event, PrivateMessageEvent)

async def is_group_mentioned(event: GroupMessageEvent) -> bool:
    """群聊中 @机器人 才回复"""
    return event.is_tome()

# 注册私聊处理器
private_msg = on_message(rule=Rule(is_private), priority=5, block=False)

@private_msg.handle()
async def handle_private(bot: Bot, event: PrivateMessageEvent):
    user_id = str(event.user_id)
    user_name = event.sender.nickname or f"用户{user_id}"
    message = event.get_plaintext()

    reply = process_message(user_id, user_name, message)
    if reply:
        await bot.send(event, reply)

# 注册群聊处理器（仅 @机器人 时回复）
group_msg = on_message(rule=Rule(is_group_mentioned), priority=5, block=False)

@group_msg.handle()
async def handle_group(bot: Bot, event: GroupMessageEvent):
    user_id = str(event.user_id)
    user_name = event.sender.nickname or f"用户{user_id}"
    message = event.get_plaintext()

    reply = process_message(user_id, user_name, message)
    if reply:
        await bot.send(event, reply, at_sender=True)

# ============================================================
# 启动入口
# ============================================================
if __name__ == "__main__":
    nonebot.init()
    nonebot.load_plugin("bot")  # 加载自身
    nonebot.run()
