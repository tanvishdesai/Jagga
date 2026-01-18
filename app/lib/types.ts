export interface UnifiedMessage {
  timestamp: Date;
  platform: 'WhatsApp' | 'Instagram';
  sender: string;
  content: string;
}

export interface AnalysisProfile {
  explicit_interests: string[];
  implicit_interests: string[];
  gift_mentions: string[];
  dislikes: string[];
  topics_discussed: string[];
  relationship_dynamics: string[];
  inside_jokes: string[];
  closeness_indicators: string[];
  sentiment_trend: string[];
}
