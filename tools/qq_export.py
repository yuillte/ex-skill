"""
QQ NT 聊天记录导出工具
从 QQ NT 加密数据库中提取和解析聊天记录
"""
import sys
import re
from pathlib import Path
import sqlcipher3
from google.protobuf.message import DecodeError

# QQ NT protobuf 消息结构需要 element_pb2
# 如果没有，可以从 https://github.com/lc6464/QQNT_Export 获取
try:
    from element_pb2 import Elements
    HAS_PROTOBUF = True
except ImportError:
    HAS_PROTOBUF = False
    print("[WARN] element_pb2 未安装，将使用简化解析模式")


def decrypt_database(db_path: str, key: str) -> str:
    """
    解密 QQ NT SQLCipher 数据库
    返回解密后的临时文件路径（实际是内存中的副本）
    """
    # QQ NT 数据库前 1024 字节是自定义头（非标准 SQLite），需要跳过
    clean_path = db_path.replace('.db', '_clean.db')

    with open(db_path, 'rb') as f:
        data = f.read()

    # 去掉前 1024 字节 QQ 自定义头
    with open(clean_path, 'wb') as f:
        f.write(data[1024:])

    print(f"[DB] 去头后大小: {len(data) - 1024} bytes")

    return clean_path


def open_database(clean_path: str, key: str):
    """打开解密后的数据库"""
    conn = sqlcipher3.connect(clean_path)
    conn.execute(f"PRAGMA key = '{key}'")
    conn.execute("PRAGMA cipher_page_size = 4096")
    conn.execute("PRAGMA kdf_iter = 4000")
    conn.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA1")
    conn.execute("PRAGMA cipher = 'aes-256-cbc'")
    return conn


def parse_protobuf_content(content: bytes) -> list[str]:
    """
    解析 protobuf 编码的消息内容
    返回 [文本, 图片标记, 表情标记, ...]
    """
    parts = []

    if not HAS_PROTOBUF:
        # 简化模式：尝试提取文本
        try:
            text = content.decode('utf-8', errors='replace')
            parts.append(text)
        except:
            parts.append("[非文本消息]")
        return parts

    try:
        elems = Elements()
        elems.ParseFromString(content)

        for elem in elems.elements:
            if elem.text and elem.text.text:
                parts.append(elem.text.text)
            elif elem.imageText:
                parts.append(f"[图片: {elem.imageText}]")
            elif elem.emojiText:
                parts.append(f"[{elem.emojiText}]")
            elif elem.face:
                parts.append(f"[QQ表情: {elem.face.faceIndex}]")
            elif elem.marketFace:
                name = getattr(elem.marketFace, 'faceName', '大表情')
                parts.append(f"[大表情: {name}]")
            elif elem.videoFile:
                parts.append("[视频]")
            elif elem.ptt:
                parts.append("[语音]")
            elif elem.reply:
                parts.append("[回复]")
            elif elem.file:
                name = getattr(elem.file, 'fileName', '文件')
                parts.append(f"[文件: {name}]")
            elif elem.arkElement:
                parts.append("[ARK消息]")
            else:
                # 尝试提取文本
                if elem.text:
                    parts.append(elem.text.text or "[其他]")
                else:
                    parts.append("[其他消息]")
    except DecodeError as e:
        parts.append(f"[解析失败: {e}]")
    except Exception as e:
        parts.append(f"[未知格式: {e}]")

    return parts if parts else ["[空消息]"]


def export_c2c_chat(conn, partner_uid: str, partner_qq: int,
                    user_qq: int, output_path: str, output_format: str = "txt"):
    """
    导出私聊 (C2C) 消息
    """
    USER_QQ = user_qq
    PARTNER_QQ = partner_qq
    PARTNER_UID = partner_uid

    # 双向消息查询
    query = """
        SELECT "40050", "40033", "40800", "40021"
        FROM c2c_msg_table
        WHERE "40033" = ?
           OR ("40033" = ? AND "40021" = ?)
        ORDER BY "40050" ASC
    """

    rows = conn.execute(query, (PARTNER_QQ, USER_QQ, PARTNER_UID)).fetchall()
    print(f"[Export] 查询到 {len(rows)} 条消息")

    if not rows:
        print("[Export] ERROR: 未查询到消息，请检查 QQ 号和 UID 是否正确")
        return

    # 区分说话人
    output_lines = []
    stats = {"text": 0, "image": 0, "emoji": 0, "other": 0, "call": 0}

    from datetime import datetime

    for row in rows:
        timestamp = row[0]
        sender_qq = row[1]
        content_blob = row[2]

        # 时间戳转换（QQ 使用毫秒时间戳）
        try:
            dt = datetime.fromtimestamp(timestamp / 1000)
            time_str = dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            time_str = f"timestamp:{timestamp}"

        # 说话人
        label = "我" if sender_qq == USER_QQ else "TA"

        # 解析内容
        if content_blob is None:
            continue

        parts = parse_protobuf_content(content_blob)
        content = ' '.join(parts)

        # 统计
        for part in parts:
            if part.startswith('[图片'):
                stats['image'] += 1
            elif part.startswith('[大表情') or part.startswith('[QQ表情'):
                stats['emoji'] += 1
            elif part.startswith('['):
                stats['other'] += 1
            else:
                stats['text'] += 1

        output_lines.append(f"[{time_str}] {label}: {content}")

    # 写入文件
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_lines))

    print(f"[Export] 导出完成: {output_path}")
    print(f"[Export] 文本: {stats['text']}, 图片: {stats['image']}, "
          f"表情: {stats['emoji']}, 其他: {stats['other']}")

    return stats


def main():
    import argparse

    parser = argparse.ArgumentParser(description='QQ NT 聊天记录导出')
    parser.add_argument('--db-path', required=True, help='nt_msg.db 路径')
    parser.add_argument('--key', required=True, help='数据库加密密钥')
    parser.add_argument('--partner-qq', type=int, required=True, help='对方 QQ 号')
    parser.add_argument('--partner-uid', default='', help='对方 UID (可选，QQ NT 格式)')
    parser.add_argument('--user-qq', type=int, required=True, help='你的 QQ 号')
    parser.add_argument('--output', required=True, help='输出文件路径')
    parser.add_argument('--format', default='txt', choices=['txt'], help='输出格式')

    args = parser.parse_args()

    # 解密数据库
    print(f"[DB] 解密数据库: {args.db_path}")
    clean_path = decrypt_database(args.db_path, args.key)

    try:
        conn = open_database(clean_path, args.key)

        # 检测 UID（如果未提供）
        partner_uid = args.partner_uid
        if not partner_uid:
            # 尝试从数据库获取
            try:
                uid_query = "SELECT DISTINCT \"40021\" FROM c2c_msg_table WHERE \"40033\" = ? LIMIT 1"
                result = conn.execute(uid_query, (args.partner_qq,)).fetchone()
                if result and result[0]:
                    partner_uid = result[0]
                    print(f"[DB] 检测到 partner UID: {partner_uid}")
            except:
                pass

        if not partner_uid:
            # 尝试获取用户 UID
            try:
                uid_query = "SELECT DISTINCT \"40020\" FROM c2c_msg_table WHERE \"40033\" = ? LIMIT 1"
                result = conn.execute(uid_query, (args.user_qq,)).fetchone()
                if result and result[0]:
                    partner_uid = result[0]
                    print(f"[DB] 从用户 UID 推断: {partner_uid}")
            except:
                pass

        if not partner_uid:
            print("[DB] WARNING: 无法获取 UID，可能只能导出部分消息")
            partner_uid = f"u_placeholder_{args.partner_qq}"

        # 导出
        stats = export_c2c_chat(
            conn=conn,
            partner_uid=partner_uid,
            partner_qq=args.partner_qq,
            user_qq=args.user_qq,
            output_path=args.output,
            output_format=args.format,
        )

    finally:
        conn.close()
        # 清理临时文件
        import os
        if os.path.exists(clean_path):
            print(f"[DB] 保留解密数据库: {clean_path}")


if __name__ == '__main__':
    main()
