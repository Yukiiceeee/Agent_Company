import re
import jieba
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from enum import Enum, IntEnum
from configs.roles import *

class RecommendationSystem:
    def __init__(self, all_companies: List[Company]):
        self.producers = [c for c in all_companies if c.role == CompanyRole.PRODUCER]
        self.stop_words = {
            "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好", "自己", "这",
            "我们需要", "需要", "开发", "一套", "基于", "用于", "或者", "使用", "以及", "能够", "最好", "具备", "熟悉", "精通"
        }

    def _tokenize(self, text: str) -> Set[str]:
        if not text: return set()
        text = text.lower()
        words = jieba.lcut(text)
        tokens = set()
        for w in words:
            w = w.strip()
            if len(w) > 0 and w not in self.stop_words:
                if re.match(r'^[a-zA-Z0-9\u4e00-\u9fa5]+$', w):
                    tokens.add(w)
        return tokens

    def _calculate_jaccard(self, set_a: Set[str], set_b: Set[str]) -> float:
        if not set_a or not set_b: return 0.0
        intersection = len(set_a.intersection(set_b))
        union = len(set_a.union(set_b))
        return intersection / union if union > 0 else 0.0

    def recommend(self, project: ActiveProject, top_k: int = 3) -> List[Dict]:
        scored_candidates = []
        project_tokens = self._tokenize(project.project_content)
        project_tags_set = set(t.lower() for t in project.tags)

        for producer in self.producers:
            base_penalty = -50.0 if producer.state == CompanyState.BUSY else 0.0
            score = base_penalty
            reasons = []

            # 1. 描述相似度
            producer_desc_tokens = self._tokenize(producer.description)
            desc_sim = self._calculate_jaccard(project_tokens, producer_desc_tokens)
            score += desc_sim * 100
            if desc_sim > 0:
                overlapped = project_tokens.intersection(producer_desc_tokens)
                reasons.append(f"关键词命中: {list(overlapped)}")

            # 2. 标签匹配
            producer_tags_set = set(t.lower() for t in producer.tags)
            tag_intersect = project_tags_set.intersection(producer_tags_set)
            score += len(tag_intersect) * 15
            if tag_intersect:
                reasons.append(f"Tag匹配: {list(tag_intersect)}")

            if score > -100:
                scored_candidates.append({
                    "company": producer, # 直接存储对象方便后续调用
                    "total_score": round(score, 2),
                    "reasons": " | ".join(reasons)
                })

        scored_candidates.sort(key=lambda x: x["total_score"], reverse=True)
        return scored_candidates[:top_k]