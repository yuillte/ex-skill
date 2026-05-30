"""
本地终端测试 — 在命令行中和蒸馏后的 persona 对话
无需 QQ，直接测试 DeepSeek persona 效果
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

# 加载配置
sys.path.insert(0, str(Path(__file__).parent))
load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.8"))

# 加载 persona
PERSONA_PROMPT_FILE = Path(__file__).parent / os.getenv("PERSONA_PROMPT_FILE", "../persona/system_prompt.md")
if PERSONA_PROMPT_FILE.exists():
    SYSTEM_PROMPT = PERSONA_PROMPT_FILE.read_text(encoding='utf-8')
    print(f"已加载 persona: {PERSONA_PROMPT_FILE}")
else:
    SYSTEM_PROMPT = "你是一个正在和男朋友聊天的女生，请自然地回复。"
    print("警告: persona 文件未找到，使用默认")

# DeepSeek 客户端
client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

def chat():
    print("=" * 50)
    print("ex-skill 本地对话测试")
    print("输入消息和 persona 对话，输入 /reset 重置记忆")
    print("输入 /quit 退出")
    print("=" * 50)
    print()
    print("💬 你现在在跟「她」聊天——")

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    memory_limit = 20  # 保留最近 20 条

    while True:
        try:
            user_input = input("\n你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n拜拜~")
            break

        if not user_input:
            continue

        if user_input == "/quit":
            print("拜拜~")
            break

        if user_input == "/reset":
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            print("[记忆已重置]")
            continue

        # 构建消息
        messages.append({"role": "user", "content": user_input})

        try:
            response = client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=messages,
                temperature=TEMPERATURE,
                max_tokens=150,
                top_p=0.9,
            )
            reply = response.choices[0].message.content.strip()
            messages.append({"role": "assistant", "content": reply})

            # 保持记忆在限额内
            if len(messages) > memory_limit + 1:
                messages = [messages[0]] + messages[-(memory_limit):]

            print(f"TA: {reply}")

        except Exception as e:
            print(f"[错误] {e}")


if __name__ == "__main__":
    if not DEEPSEEK_API_KEY:
        print("错误：请先设置 DEEPSEEK_API_KEY 环境变量")
        sys.exit(1)
    chat()
