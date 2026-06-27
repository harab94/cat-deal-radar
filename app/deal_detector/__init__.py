"""Deal detection pipeline."""

from app.deal_detector.comment_analyzer import CommentAnalysis, analyze_comments
from app.deal_detector.keyword_rules import DetectedDeal, RuleBasedDealDetector
from app.deal_detector.llm_classifier import LLMDealClassification, parse_llm_classification

__all__ = [
    "CommentAnalysis",
    "DetectedDeal",
    "LLMDealClassification",
    "RuleBasedDealDetector",
    "analyze_comments",
    "parse_llm_classification",
]
