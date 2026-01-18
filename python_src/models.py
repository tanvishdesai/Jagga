from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

@dataclass
class UnifiedMessage:
    """
    Represents a single message from any platform (WhatsApp/Instagram)
    normalized to a common format.
    """
    timestamp: datetime
    platform: str # 'WhatsApp' or 'Instagram'
    sender: str
    content: str

    def to_dict(self):
        return {
            "timestamp": self.timestamp.isoformat(),
            "platform": self.platform,
            "sender": self.sender,
            "content": self.content
        }

@dataclass
class AnalysisProfile:
    """
    Aggregated profile containing both gift interests and relationship analysis.
    """
    # Interest Fields
    explicit_interests: List[str]
    implicit_interests: List[str]
    gift_mentions: List[str]
    dislikes: List[str]
    topics_discussed: List[str]
    
    # Relationship Fields
    relationship_dynamics: List[str]
    inside_jokes: List[str]
    closeness_indicators: List[str]
    sentiment_trend: List[str]
