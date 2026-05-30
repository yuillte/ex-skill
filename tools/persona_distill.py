"""
Persona 蒸馏脚本
从 QQ 聊天记录中提取一个人的语气、价值观、思维逻辑、情感反应模式
"""
import re
import json
from collections import Counter, defaultdict
from pathlib import Path

CHAT_FILE = Path("C:/Users/ASUS/chat-data/full_chat.txt")
OUTPUT_DIR = Path("C:/Users/ASUS/chat-data/persona")

# ========== 1. 解析消息 ==========
def parse_messages(filepath):
    """解析聊天记录，提取 TA 的文本消息"""
    ta_texts = []       # TA 的纯文本
    ta_emojis = []      # TA 的表情使用
    ta_images = []      # TA 的图片标记
    my_texts = []       # 用户的纯文本
    conversations = []  # 完整对话片段

    pattern = re.compile(r'^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] (我|TA): (.*)$')

    current_conv = []
    last_time = None

    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            m = pattern.match(line)
            if not m:
                continue

            timestamp = m.group(1)
            speaker = m.group(2)
            content = m.group(3)

            # 解析时间
            try:
                dt = timestamp.split(' ')[0]  # date part
                time = timestamp.split(' ')[1]
            except:
                continue

            # 对话分片：间隔超过 30 分钟算新对话
            if current_conv and last_time:
                try:
                    from datetime import datetime, timedelta
                    curr_dt = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                    last_dt = datetime.strptime(last_time, '%Y-%m-%d %H:%M:%S')
                    if (curr_dt - last_dt) > timedelta(minutes=30):
                        if len(current_conv) >= 3:  # 至少 3 轮对话
                            conversations.append(current_conv)
                        current_conv = []
                except:
                    pass

            current_conv.append({'speaker': speaker, 'content': content, 'time': timestamp})
            last_time = timestamp

            if speaker == 'TA':
                # 分类消息类型
                if content.startswith('[通话]') or content.startswith('[媒体'):
                    continue  # 跳过通话和媒体
                elif content.startswith('[图片'):
                    ta_images.append(content)
                elif content.startswith('[大表情]') or content.startswith('[表情]') or content.startswith('[动画表情]'):
                    ta_emojis.append(content)
                elif content.startswith('['):
                    continue  # 跳过其他标记
                else:
                    ta_texts.append(content)
            else:
                if not content.startswith('['):
                    my_texts.append(content)

    # 最后一个对话
    if len(current_conv) >= 3:
        conversations.append(current_conv)

    return {
        'ta_texts': ta_texts,
        'ta_emojis': ta_emojis,
        'ta_images': ta_images,
        'my_texts': my_texts,
        'conversations': conversations
    }

# ========== 2. 语言风格分析 ==========
def analyze_language_style(texts):
    """分析语言风格：常用词、语气词、句式特征"""

    # 2a. 词频统计 (1-4 字词)
    word_counter = Counter()
    bigram_counter = Counter()
    trigram_counter = Counter()

    # 语气词
    tone_words = ['嘛', '呢', '吧', '啊', '呀', '哦', '噢', '嗯', '呃', '哈',
                  '啦', '咯', '呗', '哇', '嘿', '唉', '哎', '嘶', '啧', '嘻',
                  '嗯嗯', '哈哈', '嘿嘿', '呵呵', '呜呜', '啊啊', '嗷嗷']
    tone_counter = Counter()

    # 标点习惯
    punctuation_style = Counter()

    total_chars = 0

    for text in texts:
        # 跳过纯标记
        clean = text.strip()
        if not clean:
            continue

        total_chars += len(clean)

        # 标点统计
        puncts = re.findall(r'[。，、；：？！…～.!?,;:…~]+', clean)
        for p in puncts:
            punctuation_style[p] += 1

        # 感叹号/问号密度
        exclamation = clean.count('！') + clean.count('!')
        question = clean.count('？') + clean.count('?')

        # 使用 jieba 分词（如果可用），否则用字符级分析
        # 提取 2-gram 和 3-gram（字符级）
        chars = list(clean.replace(' ', ''))
        for i in range(len(chars) - 1):
            bigram_counter[chars[i] + chars[i+1]] += 1
        for i in range(len(chars) - 2):
            trigram_counter[chars[i] + chars[i+1] + chars[i+2]] += 1

        # 语气词统计
        for tw in tone_words:
            if tw in clean:
                tone_counter[tw] += clean.count(tw)

        # 消息长度
        word_counter['__MSG_LEN__'] += len(clean)
        word_counter['__MSG_COUNT__'] += 1

    avg_msg_len = word_counter['__MSG_LEN__'] / max(word_counter['__MSG_COUNT__'], 1)

    # 2b. 常用句式模板
    sentence_patterns = []
    for text in texts:
        # 检测常见句式
        patterns_found = []
        if re.search(r'(嗯|额|呃|啊)[,，。.!！]*$', text):
            patterns_found.append('语气词结尾')
        if re.search(r'(嘛|呢|吧|啊|呀)[？?!！。.,，]*$', text):
            patterns_found.append('语气助词结尾')
        if re.search(r'[?？]', text) and len(text) < 15:
            patterns_found.append('短问句')
        if re.search(r'[!！]', text) and len(text) < 15:
            patterns_found.append('短感叹句')
        if text.endswith('…') or text.endswith('...'):
            patterns_found.append('省略号结尾')
        if re.search(r'(哈哈|嘿嘿|呵呵|嘻嘻|hhhh)', text):
            patterns_found.append('带笑声')
        if re.search(r'(笑死|难绷|蚌埠|乐|草|艹|绝了|绷不住)', text):
            patterns_found.append('网络感叹')
        sentence_patterns.extend(patterns_found)

    pattern_counter = Counter(sentence_patterns)

    return {
        'avg_message_length': round(avg_msg_len, 1),
        'total_texts': word_counter['__MSG_COUNT__'],
        'total_chars': total_chars,
        'tone_words': tone_counter.most_common(20),
        'punctuation_top': punctuation_style.most_common(15),
        'sentence_patterns': pattern_counter.most_common(15),
        'top_bigrams': bigram_counter.most_common(30),
        'top_trigrams': trigram_counter.most_common(20),
    }


# ========== 3. 情感反应模式分析 ==========
def analyze_emotional_patterns(texts, conversations):
    """分析情感反应模式"""

    # 情感关键词分类
    emotion_categories = {
        '开心/兴奋': ['哈哈', '嘿嘿', '嘻嘻', '开心', '高兴', '快乐', '笑死', '好耶', 'nice', '棒',
                     '太好了', '真不错', '有意思', 'hhhh', '好好好', '可爱', '喜欢'],
        '难过/低落': ['难过', '伤心', '难受', '想哭', '哭', '呜呜', 'emo', '抑郁', '低落', '不开心',
                     '烦', '累', '疲惫', '困', '唉', '哎'],
        '生气/不满': ['生气', '气死', '烦死', '无语', '受不了', '有病', '离谱', '傻逼', 'sb',
                     '恶心', '呸', '过分', '凭什么'],
        '焦虑/担心': ['担心', '害怕', '紧张', '焦虑', '慌', '不安', '怕怕', '吓死', '完了',
                     '怎么办', '救命', '糟糕', '坏了'],
        '温柔/关心': ['想你', '爱你', '抱抱', '亲亲', 'mua', '晚安', '早安', '想你啦', '心疼',
                     '注意安全', '照顾好', '乖乖', '摸摸', '贴贴'],
        '惊讶/好奇': ['啊？', '什么', '真的假的', '天哪', '我靠', '卧槽', '离谱', '震惊',
                     '不可思议', '为啥', '好奇', '居然'],
        '撒娇/俏皮': ['哼', '呸', '切', '略', '略略略', '不听', '不要', '就要', '笨蛋', '傻瓜',
                     '猪', '臭', '坏蛋', '讨厌', '烦人'],
        '敷衍/回避': ['嗯', '哦', '好', '行吧', '随便', '无所谓', '再说吧', '不知道',
                     '也许', '可能吧', '大概'],
    }

    emotion_counts = defaultdict(int)

    for text in texts:
        for category, keywords in emotion_categories.items():
            for kw in keywords:
                if kw in text:
                    emotion_counts[category] += 1
                    break  # 每条消息每个类别只计一次

    # 计算比例
    total = sum(emotion_counts.values()) or 1
    sorted_emotions = sorted(emotion_counts.items(), key=lambda x: x[1], reverse=True)
    emotion_ratios = {k: round(v/total*100, 1) for k, v in sorted_emotions}

    return {
        'emotion_distribution': dict(sorted(emotion_ratios.items(), key=lambda x: x[1], reverse=True)),
        'emotion_raw_counts': dict(sorted(emotion_counts.items(), key=lambda x: x[1], reverse=True)),
    }


# ========== 4. 对话习惯分析 ==========
def analyze_conversation_habits(conversations, ta_texts):
    """分析对话习惯：回复速度、对话节奏、话题偏好"""

    # 消息时间分布
    hour_dist = Counter()
    day_dist = Counter()
    month_dist = Counter()

    time_pattern = re.compile(r'(\d{4})-(\d{2})-(\d{2}) (\d{2}):\d{2}:\d{2}')

    for conv in conversations:
        for msg in conv:
            m = time_pattern.match(msg['time'])
            if m:
                hour = int(m.group(4))
                month = int(m.group(2))
                hour_dist[hour] += 1
                month_dist[month] += 1

    # 消息长度分布
    len_dist = Counter()
    for text in ta_texts:
        l = len(text)
        if l <= 5:
            len_dist['极短(1-5字)'] += 1
        elif l <= 15:
            len_dist['短(6-15字)'] += 1
        elif l <= 30:
            len_dist['中(16-30字)'] += 1
        elif l <= 60:
            len_dist['长(31-60字)'] += 1
        else:
            len_dist['超长(60+字)'] += 1

    # 对话开场方式
    openers = []
    for conv in conversations:
        if conv and conv[0]['speaker'] == 'TA':
            text = conv[0]['content']
            if len(text) < 30:
                openers.append(text)

    # 对话结束方式
    closers = []
    for conv in conversations:
        if conv and conv[-1]['speaker'] == 'TA':
            text = conv[-1]['content']
            if len(text) < 30:
                closers.append(text)

    return {
        'hour_distribution': dict(sorted(hour_dist.items())),
        'peak_hours': [h for h, c in hour_dist.most_common(5)],
        'message_length_distribution': dict(len_dist.most_common()),
        'sample_openers': openers[:50],
        'sample_closers': closers[:50],
    }


# ========== 5. 口语特征提取 ==========
def extract_speech_patterns(texts):
    """提取独特口语特征"""

    # 高频口语词
    spoken_markers = {
        '句首语气词': [],
        '句尾语气词': [],
        '叠词': [],
        '口头禅候选': [],
    }

    # 句尾语气词统计
    ending_particles = Counter()
    for text in texts:
        text = text.strip()
        if text and text[-1] in '嘛呢吧啊呀哦噢嗯哈啦咯呗哇嘿唉嘻':
            ending_particles[text[-1]] += 1

    spoken_markers['句尾语气词'] = ending_particles.most_common(15)

    # 叠词检测 (AA, AABB, ABAB 等)
    redup_pattern = re.compile(r'(.)\1')
    redup_count = 0
    for text in texts:
        if redup_pattern.search(text):
            redup_count += 1

    # 常见缩写/网络用语
    internet_slang = Counter()
    slang_list = [
        '笑死', '难绷', '蚌埠', '草', '艹', '乐', '绝了', '雀食', '确实',
        '有一说一', 'u1s1', '只能说', '绷不住', '真的会谢', '栓Q', '无语子',
        '就是说', '咱就是说', '属于是', '一整个', '大无语', '离大谱',
        'emmm', 'umm', 'hhh', 'www', '草草草', '好好好', '行行行',
        '好家伙', '太真实了', '确实确实', '笑不活了', '救命',
        '是的呢', '好的呢', 'okk', 'okok', '嗯嗯', '对对对',
        '啊这', '确实', '没办法', '就是说啊', '真的',
    ]
    for text in texts:
        for slang in slang_list:
            if slang in text:
                internet_slang[slang] += 1

    return {
        'ending_particles': ending_particles.most_common(15),
        'internet_slang': internet_slang.most_common(25),
        'reduplication_ratio': round(redup_count / max(len(texts), 1) * 100, 1),
    }


# ========== 6. 表情包使用分析 ==========
def analyze_emoji_usage(emojis, images, texts):
    """分析表情包/emoji 使用习惯"""
    total_msgs = len(texts) + len(emojis) + len(images)

    return {
        'text_count': len(texts),
        'emoji_count': len(emojis),
        'image_count': len(images),
        'total_count': total_msgs,
        'emoji_ratio': round(len(emojis) / max(total_msgs, 1) * 100, 1),
        'image_ratio': round(len(images) / max(total_msgs, 1) * 100, 1),
        'non_text_ratio': round((len(emojis) + len(images)) / max(total_msgs, 1) * 100, 1),
    }


# ========== 7. 价值观和思维逻辑提取 ==========
def extract_values_and_logic(conversations, ta_texts):
    """从对话中提取价值观和思维逻辑线索"""

    # 关键词线索
    value_indicators = {
        '亲密关系观': ['感情', '恋爱', '喜欢', '爱', '在一起', '结婚', '对象', '男朋友', '女朋友',
                      '前任', '分手', '吵架', '冷战', '哄', '约会', '异地', '出轨', '专一'],
        '自我认知': ['我这个人', '我觉得我', '我的性格', '我适合', '我不适合', '我讨厌自己',
                    '我挺', '我比较', '我特别', '我一直', '我从小'],
        '人生观': ['人生', '活法', '意义', '目标', '追求', '理想', '现实', '努力', '躺平',
                  '摆烂', '奋斗', '生活', '未来', '规划', '方向'],
        '社交态度': ['朋友', '社恐', '社交', '聚会', '宅', '出门', '内向', '外向',
                    '尴尬', '懒得', '不想去', '约'],
        '消费观念': ['买', '钱', '贵', '便宜', '值不值', '浪费', '省', '花销', '价格',
                    '想买', '舍不得', '消费'],
        '家庭观念': ['家', '爸妈', '爸爸', '妈妈', '父母', '家里人', '回家', '亲戚',
                    '弟弟', '妹妹', '姐姐', '哥哥'],
    }

    # 提取包含这些关键词的典型句子
    typical_sentences = defaultdict(list)

    for text in ta_texts:
        for category, keywords in value_indicators.items():
            for kw in keywords:
                if kw in text and len(text) > 5 and len(text) < 150:
                    if len(typical_sentences[category]) < 20:
                        typical_sentences[category].append(text)
                    break

    # 思维逻辑模式
    logic_patterns = {
        '因果推理': 0,
        '对比分析': 0,
        '条件假设': 0,
        '举例说明': 0,
        '自我反思': 0,
    }

    for text in ta_texts:
        if re.search(r'(因为|所以|因此|导致|原因)', text):
            logic_patterns['因果推理'] += 1
        if re.search(r'(但是|不过|然而|虽然|可是|但)', text):
            logic_patterns['对比分析'] += 1
        if re.search(r'(如果|要是|万一|假如|的话)', text):
            logic_patterns['条件假设'] += 1
        if re.search(r'(比如|例如|就像|好比|相当于)', text):
            logic_patterns['举例说明'] += 1
        if re.search(r'(我是不是|我太|我总是|我老是|我怎么|我不该|我以后)', text):
            logic_patterns['自我反思'] += 1

    return {
        'value_sentences': {k: v for k, v in typical_sentences.items() if v},
        'logic_patterns': logic_patterns,
    }


# ========== 8. 生成 Persona 报告 ==========
def generate_persona_report(all_analysis):
    """汇总所有分析，生成 persona 报告"""

    lang = all_analysis['language']
    emotion = all_analysis['emotion']
    habits = all_analysis['habits']
    speech = all_analysis['speech']
    emoji_usage = all_analysis['emoji']
    values = all_analysis['values']

    report = []
    report.append("# Persona 蒸馏报告\n")
    report.append(f"## 基础数据\n")
    report.append(f"- 分析消息数（纯文本）：{lang['total_texts']} 条")
    report.append(f"- 总字符数：{lang['total_chars']}")
    report.append(f"- 平均消息长度：{lang['avg_message_length']} 字/条\n")

    report.append(f"## 语言风格\n")
    report.append(f"### 高频语气词")
    for word, count in lang['tone_words'][:15]:
        report.append(f"- {word}: {count}次")

    report.append(f"\n### 句尾语气词偏好")
    for word, count in speech['ending_particles'][:10]:
        report.append(f"- {word}: {count}次")

    report.append(f"\n### 网络用语/口头禅")
    for word, count in speech['internet_slang'][:20]:
        if count >= 3:
            report.append(f"- {word}: {count}次")

    report.append(f"\n### 消息长度分布")
    for length_type, count in habits['message_length_distribution'].items():
        report.append(f"- {length_type}: {count}条")

    report.append(f"\n## 情感模式\n")
    report.append(f"### 情感表达分布")
    for emo, ratio in emotion['emotion_distribution'].items():
        bar = '█' * int(ratio / 2)
        report.append(f"- {emo}: {ratio}% {bar}")

    report.append(f"\n## 表情包使用\n")
    report.append(f"- 文字消息: {emoji_usage['text_count']}条")
    report.append(f"- 表情/emoji: {emoji_usage['emoji_count']}条 ({emoji_usage['emoji_ratio']}%)")
    report.append(f"- 图片: {emoji_usage['image_count']}条 ({emoji_usage['image_ratio']}%)")
    report.append(f"- 非文字占比: {emoji_usage['non_text_ratio']}%")

    report.append(f"\n## 价值观线索\n")
    for category, sentences in values['value_sentences'].items():
        report.append(f"\n### {category}")
        for s in sentences[:5]:
            report.append(f"- \"{s}\"")

    report.append(f"\n## 思维逻辑模式\n")
    for pattern, count in values['logic_patterns'].items():
        report.append(f"- {pattern}: {count}次")

    report.append(f"\n## 对话习惯\n")
    report.append(f"### 活跃时段")
    peak_hours = sorted(habits['peak_hours'])
    report.append(f"- 最活跃时段: {peak_hours} 时")

    return '\n'.join(report)


# ========== MAIN ==========
def main():
    OUTPUT_DIR.mkdir(exist_ok=True)

    print("=" * 60)
    print("Persona 蒸馏分析")
    print("=" * 60)

    # 1. 解析
    print("\n[1/7] 解析聊天记录...")
    data = parse_messages(CHAT_FILE)
    print(f"  TA 文本消息: {len(data['ta_texts'])} 条")
    print(f"  TA 表情/emoji: {len(data['ta_emojis'])} 条")
    print(f"  TA 图片: {len(data['ta_images'])} 条")
    print(f"  对话片段: {len(data['conversations'])} 个")

    # 2. 语言风格
    print("\n[2/7] 分析语言风格...")
    lang_style = analyze_language_style(data['ta_texts'])
    print(f"  平均消息长度: {lang_style['avg_message_length']} 字")
    print(f"  最高频语气词: {lang_style['tone_words'][:5]}")

    # 3. 情感模式
    print("\n[3/7] 分析情感反应模式...")
    emotion = analyze_emotional_patterns(data['ta_texts'], data['conversations'])
    for emo, ratio in list(emotion['emotion_distribution'].items())[:3]:
        print(f"  {emo}: {ratio}%")

    # 4. 对话习惯
    print("\n[4/7] 分析对话习惯...")
    habits = analyze_conversation_habits(data['conversations'], data['ta_texts'])
    print(f"  活跃时段: {habits['peak_hours']}")

    # 5. 口语特征
    print("\n[5/7] 提取口语特征...")
    speech = extract_speech_patterns(data['ta_texts'])
    print(f"  常见网络用语: {speech['internet_slang'][:5]}")

    # 6. 表情包
    print("\n[6/7] 分析表情包使用...")
    emoji_usage = analyze_emoji_usage(data['ta_emojis'], data['ta_images'], data['ta_texts'])
    print(f"  非文字占比: {emoji_usage['non_text_ratio']}%")

    # 7. 价值观
    print("\n[7/7] 提取价值观线索...")
    values_logic = extract_values_and_logic(data['conversations'], data['ta_texts'])
    for cat, sents in values_logic['value_sentences'].items():
        print(f"  {cat}: {len(sents)} 条典型语句")

    all_analysis = {
        'language': lang_style,
        'emotion': emotion,
        'habits': habits,
        'speech': speech,
        'emoji': emoji_usage,
        'values': values_logic,
    }

    # 保存详细数据
    # 需要把不可序列化的对象转换
    serializable = {
        'language': lang_style,
        'emotion': {k: dict(v) if isinstance(v, Counter) else v for k, v in emotion.items()},
        'habits': {k: v for k, v in habits.items() if k not in ['sample_openers', 'sample_closers']},
        'speech': speech,
        'emoji': emoji_usage,
        'values': {
            'value_sentences': values_logic['value_sentences'],
            'logic_patterns': values_logic['logic_patterns'],
        }
    }

    with open(OUTPUT_DIR / 'analysis_data.json', 'w', encoding='utf-8') as f:
        json.dump(serializable, f, ensure_ascii=False, indent=2)
    print(f"\n详细数据已保存到: {OUTPUT_DIR / 'analysis_data.json'}")

    # 生成报告
    report = generate_persona_report(all_analysis)
    with open(OUTPUT_DIR / 'persona_report.md', 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"Persona 报告已保存到: {OUTPUT_DIR / 'persona_report.md'}")

    # 保存 TA 纯文本（用于后续 DeepSeek 分析）
    with open(OUTPUT_DIR / 'ta_texts.txt', 'w', encoding='utf-8') as f:
        for i, text in enumerate(data['ta_texts']):
            if text.strip():
                f.write(f"{text}\n")
    print(f"TA 纯文本已保存到: {OUTPUT_DIR / 'ta_texts.txt'}")

    # 保存对话样本
    with open(OUTPUT_DIR / 'conversation_samples.txt', 'w', encoding='utf-8') as f:
        for i, conv in enumerate(data['conversations'][:30]):
            f.write(f"\n=== 对话片段 #{i+1} ===\n")
            for msg in conv:
                f.write(f"[{msg['time']}] {msg['speaker']}: {msg['content']}\n")
    print(f"对话样本已保存到: {OUTPUT_DIR / 'conversation_samples.txt'}")

    print("\n" + "=" * 60)
    print("分析完成！")
    print("=" * 60)

    return all_analysis, data


if __name__ == '__main__':
    results, raw_data = main()
