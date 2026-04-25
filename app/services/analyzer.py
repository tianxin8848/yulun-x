from collections import Counter

import jieba
from snownlp import SnowNLP

STOPWORDS = {
    "的",
    "了",
    "和",
    "是",
    "在",
    "与",
    "为",
    "对",
    "就",
    "及",
    "也",
    "将",
    "中",
    "有",
    "或",
}


def sentiment(text: str) -> tuple[float, str]:
    if not text.strip():
        return 0.5, "neutral"
    score = float(SnowNLP(text).sentiments)
    if score >= 0.6:
        label = "positive"
    elif score <= 0.4:
        label = "negative"
    else:
        label = "neutral"
    return score, label


def top_keywords(texts: list[str], topn: int = 12) -> list[str]:
    words: list[str] = []
    for text in texts:
        for token in jieba.cut(text):
            t = token.strip()
            if len(t) < 2 or t in STOPWORDS:
                continue
            words.append(t)
    counts = Counter(words)
    return [word for word, _ in counts.most_common(topn)]
