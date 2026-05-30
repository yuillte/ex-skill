"""
ex-skill QQ Bot — 直连 NapCatQQ OneBot v11 WebSocket
使用蒸馏后的 persona + DeepSeek API 自动回复 QQ 消息
"""
import os
import json
import asyncio
import re
from pathlib import Path
from collections import defaultdict
from dotenv import load_dotenv
import websockets
from openai import OpenAI

# ============================================================
# 配置
# ============================================================
load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.8"))

# NapCatQQ OneBot WebSocket
NAPCAT_WS_URL = os.getenv("NAPCAT_WS_URL", "ws://127.0.0.1:3001")
# 如果 NapCat 配置了 access_token，在这里填
NAPCAT_TOKEN = os.getenv("NAPCAT_TOKEN", "")

# 权限
ALLOWED_USERS = os.getenv("ALLOWED_USERS", "").split(",") if os.getenv("ALLOWED_USERS", "") else []
BOT_QQ = os.getenv("BOT_QQ", "")

# 记忆
MEMORY_ROUNDS = int(os.getenv("MEMORY_ROUNDS", "10"))

# Persona
PERSONA_PROMPT_FILE = os.getenv("PERSONA_PROMPT_FILE", "../persona/system_prompt.md")

# ============================================================
# 加载 Persona
# ============================================================
def load_persona() -> str:
    path = Path(__file__).parent / PERSONA_PROMPT_FILE
    if path.exists():
        content = path.read_text(encoding='utf-8')
        print(f"[Persona] 已加载 ({len(content)} 字符)")
        return content
    print("[Persona] WARNING: 未找到 persona 文件，使用默认")
    return "你是一个正在和男朋友聊天的女生，请自然地回复。"

SYSTEM_PROMPT = load_persona()

# ============================================================
# DeepSeek 客户端
# ============================================================
client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

# ============================================================
# 对话记忆
# ============================================================
memory: dict[str, list[dict]] = defaultdict(list)

def get_memory(uid: str) -> list:
    return memory[uid]

def add_memory(uid: str, role: str, content: str):
    mem = memory[uid]
    mem.append({"role": role, "content": content})
    max_msgs = MEMORY_ROUNDS * 2
    if len(mem) > max_msgs:
        memory[uid] = mem[-max_msgs:]

def clear_memory(uid: str):
    memory[uid] = []

# ============================================================
# DeepSeek 回复生成
# ============================================================
AI_FILTER_PATTERNS = [
    r"作为一个AI", r"根据.*训练", r"我是一个.*(?:模型|AI|人工智能|语言模型)",
    r"很抱歉.*无法", r"对不起.*无法", r"As an AI",
    r"I am.*AI", r"I cannot", r"I apologize",
]

def generate_reply(uid: str, user_msg: str) -> str:
    mem = get_memory(uid)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + mem
    messages.append({"role": "user", "content": user_msg})

    try:
        resp = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=messages,
            temperature=TEMPERATURE,
            max_tokens=150,
            top_p=0.9,
        )
        reply = resp.choices[0].message.content.strip()

        # 过滤 AI 痕迹
        for pat in AI_FILTER_PATTERNS:
            if re.search(pat, reply):
                print(f"[Filter] AI痕迹: {reply[:60]}...")
                return "嗯？你说啥来着 [大表情]"

        return reply
    except Exception as e:
        print(f"[DeepSeek] Error: {e}")
        return "等下噢 我卡了 [大表情]"

# ============================================================
# OneBot v11 协议处理
# ============================================================
def is_allowed(uid: str) -> bool:
    if not ALLOWED_USERS or ALLOWED_USERS == ['']:
        return True
    return uid in ALLOWED_USERS

def handle_message(data: dict) -> str | None:
    """处理私聊/群聊消息，返回回复文本。None 表示不回复。"""
    msg_type = data.get("message_type", "")

    if msg_type == "private":
        uid = str(data.get("user_id", ""))
        raw_msg = data.get("raw_message", data.get("message", ""))
        nickname = data.get("sender", {}).get("nickname", uid)

        if not is_allowed(uid):
            return None

        text = str(raw_msg).strip()
        if not text:
            return None

        # 命令
        if text == "/reset":
            clear_memory(uid)
            return "嗯嗯 重来了 [大表情]"
        if text == "/memory":
            m = get_memory(uid)
            return f"记得 {len(m)//2} 轮呢"

        add_memory(uid, "user", f"{nickname}: {text}")
        reply = generate_reply(uid, text)
        add_memory(uid, "assistant", reply)
        return reply

    elif msg_type == "group":
        # 群聊中检查是否 @ 了自己
        uid = str(data.get("user_id", ""))
        raw_msg = data.get("raw_message", data.get("message", ""))
        group_id = data.get("group_id", "")

        if not is_allowed(uid):
            return None

        text = str(raw_msg).strip()
        # 检查是否 @机器人
        at_bot = f"[CQ:at,qq={BOT_QQ}]" if BOT_QQ else "@"
        if at_bot not in text and BOT_QQ not in text:
            return None

        # 去掉 @ 部分
        text = re.sub(r'\[CQ:at,qq=\d+\]', '', text).strip()
        if not text:
            return None

        add_memory(uid, "user", text)
        reply = generate_reply(uid, text)
        add_memory(uid, "assistant", reply)
        return f"[CQ:reply,id={data.get('message_id', 0)}]{reply}"

    return None

# ============================================================
# WebSocket 客户端
# ============================================================
async def napcat_loop():
    """连接 NapCatQQ WebSocket 并保持连接"""
    ws_url = NAPCAT_WS_URL
    headers = {}
    if NAPCAT_TOKEN:
        headers["Authorization"] = f"Bearer {NAPCAT_TOKEN}"

    echo_counter = 0

    while True:
        try:
            print(f"[WS] 连接 {ws_url} ...")
            async with websockets.connect(ws_url, extra_headers=headers) as ws:
                print("[WS] 已连接 NapCatQQ ✓")

                while True:
                    raw = await ws.recv()
                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    # OneBot v11 事件处理
                    post_type = data.get("post_type", "")
                    if post_type == "meta_event":
                        meta = data.get("meta_event_type", "")
                        if meta == "heartbeat":
                            # 心跳
                            continue
                        elif meta == "lifecycle":
                            print(f"[NapCat] 生命周期: {data.get('sub_type')}")
                            continue

                    if post_type == "message":
                        reply_text = handle_message(data)
                        if reply_text:
                            # 调用 send_msg API
                            msg_type = data.get("message_type")
                            echo_counter += 1
                            echo = f"exskill_{echo_counter}"

                            if msg_type == "private":
                                send_data = {
                                    "action": "send_private_msg",
                                    "params": {
                                        "user_id": data["user_id"],
                                        "message": reply_text,
                                    },
                                    "echo": echo,
                                }
                            elif msg_type == "group":
                                send_data = {
                                    "action": "send_group_msg",
                                    "params": {
                                        "group_id": data["group_id"],
                                        "message": reply_text,
                                    },
                                    "echo": echo,
                                }
                            else:
                                continue

                            await ws.send(json.dumps(send_data))
                            print(f"[Send] → {data.get('user_id')}: {reply_text[:50]}...")

        except websockets.exceptions.ConnectionClosed:
            print("[WS] 连接断开，5秒后重连...")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"[WS] 错误: {e}，5秒后重连...")
            await asyncio.sleep(5)

# ============================================================
# 主入口
# ============================================================
async def main():
    if not DEEPSEEK_API_KEY:
        print("=" * 50)
        print("ERROR: 请先设置 DEEPSEEK_API_KEY")
        print("编辑 bot/.env 文件，填入你的 DeepSeek API Key")
        print("=" * 50)
        return

    print("=" * 50)
    print("ex-skill QQ Bot")
    print(f"  DeepSeek: {DEEPSEEK_MODEL}")
    print(f"  NapCat WS: {NAPCAT_WS_URL}")
    print(f"  Memory: {MEMORY_ROUNDS} 轮")
    print(f"  Temp: {TEMPERATURE}")
    print("=" * 50)

    await napcat_loop()

if __name__ == "__main__":
    asyncio.run(main())
