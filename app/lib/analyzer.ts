import { GoogleGenerativeAI } from '@google/generative-ai';
import { UnifiedMessage, AnalysisProfile } from './types';

// Key Manager Logic
class KeyManager {
  private accountKeys: string[][];
  private currentAccIdx: number = 0;
  private currentKeyIndices: number[];
  private accountCooldowns: Record<number, number> = {};
  private cooldownDuration: number = 90 * 1000; // 90 seconds in ms

  constructor(accountKeys: string[][]) {
    this.accountKeys = accountKeys.filter(keys => keys && keys.length > 0);
    this.currentKeyIndices = new Array(this.accountKeys.length).fill(0);

    if (this.accountKeys.length === 0) {
      console.warn("No API keys provided to KeyManager");
    }
  }

  async getActiveKey(): Promise<string> {
    if (this.accountKeys.length === 0) {
      throw new Error("No API keys provided.");
    }

    // 1. Try to find an account not in cooldown
    for (let i = 0; i < this.accountKeys.length; i++) {
      const accIdx = this.currentAccIdx;

      if (!this.accountCooldowns[accIdx] || Date.now() > this.accountCooldowns[accIdx]) {
        const keyIdx = this.currentKeyIndices[accIdx];
        const keys = this.accountKeys[accIdx];

        // Rotate key index
        this.currentKeyIndices[accIdx] = (this.currentKeyIndices[accIdx] + 1) % keys.length;

        return keys[keyIdx % keys.length];
      }

      // Try next account
      this.currentAccIdx = (this.currentAccIdx + 1) % this.accountKeys.length;
    }

    // 2. If all accounts cooling down, wait for the soonest
    const earliestTime = Math.min(...Object.values(this.accountCooldowns));
    const waitTime = earliestTime - Date.now();

    if (waitTime > 0) {
      console.warn(`All Accounts are in cooldown. Waiting ${waitTime}ms...`);
      await new Promise(resolve => setTimeout(resolve, waitTime + 1000));
    }

    return this.getActiveKey();
  }

  markCurrentAccountExhausted() {
    const accIdx = this.currentAccIdx;
    console.warn(`Account ${accIdx} hit rate/quota limit. Switching account...`);
    this.accountCooldowns[accIdx] = Date.now() + this.cooldownDuration;
    this.currentAccIdx = (this.currentAccIdx + 1) % this.accountKeys.length;
  }
}

// Load keys from environment variables
const loadGeminiKeys = (): string[][] => {
  const accounts: Record<string, { keyId: string, value: string }[]> = {};

  if (typeof process !== 'undefined' && process.env) {
    for (const [key, value] of Object.entries(process.env)) {
      if (key.startsWith('GEMINI_ACCOUNT_') && key.includes('_KEY_') && value) {
        try {
          const parts = key.split('_');
          // GEMINI_ACCOUNT_{ACC_ID}_KEY_{KEY_ID}
          // parts: ['GEMINI', 'ACCOUNT', '1', 'KEY', '1']
          if (parts.length >= 5) {
            const accId = parts[2];
            if (!accounts[accId]) {
              accounts[accId] = [];
            }
            accounts[accId].push({ keyId: key, value });
          }
        } catch {
          continue;
        }
      }
    }
  }

  const sortedAccIds = Object.keys(accounts).sort((a, b) => {
    const numA = parseInt(a);
    const numB = parseInt(b);
    return isNaN(numA) || isNaN(numB) ? a.localeCompare(b) : numA - numB;
  });

  const finalKeys: string[][] = [];
  for (const accId of sortedAccIds) {
    const sortedKeys = accounts[accId]
      .sort((a, b) => a.keyId.localeCompare(b.keyId))
      .map(k => k.value);

    if (sortedKeys.length > 0) {
      finalKeys.push(sortedKeys);
    }
  }

  return finalKeys;
};

// Initialize global key manager (lazy init if needed)
let keyManager: KeyManager | null = null;
const initKeyManager = () => {
    if (!keyManager) {
        const keys = loadGeminiKeys();
        keyManager = new KeyManager(keys);
    }
    return keyManager;
}


// Analysis Logic

const getAnalysisSystemInstruction = () => `
    You are an expert behavioral analyst and gift consultant.
    Analyze the following chat transcript between two people.

    **CONTEXT**:
    - The chat contains a mix of English and **Hinglish** (Hindi written in English alphabet).
    - You MUST understand the Hinglish dialect (e.g. "Kya chahiye", "Mujhe ye pasand hai").

    **GOAL**: Extract key information to build a "Memory Map" of the user's interests for gift recommendations.

    **EXTRACT**:
    1. **Explicit Interests**: Things they explicitly say they like/love/want.
    2. **Implicit Interests**: Recurring themes or topics they talk about broadly (e.g. they talk a lot about coffee places => Coffee lover).
    3. **Gift Ideas/Mentions**: Specific items mentioned or hinted at (e.g. "I need a new watch").
    4. **Dislikes**: Things they hate or complained about.
    5. **Key Dates/Events**: Birthdays, anniversaries mentioned.

    **RELATIONSHIP ANALYSIS**:
    6. **Dynamics**: How do they interact? (e.g., "Playful teasing", "Deep emotional support", "Formal/Professional", "Flirty").
    7. **Inside Jokes**: Recurring phrases, nicknames, or references only they understand.
    8. **Closeness Indicators**: Specific moments or quotes showing strong bond/intimacy (e.g., "I can only tell you this").
    9. **Sentiment**: General vibe of this chunk (Positive/Neutral/Tense/Mixed).

    RETURN JSON ONLY:
    {
        "explicit_interests": [],
        "implicit_interests": [],
        "gift_mentions": [],
        "dislikes": [],
        "key_dates": [],
        "relationship_dynamics": [],
        "inside_jokes": [],
        "closeness_indicators": [],
        "sentiment_trend": []
    }
`;

const constructAnalysisPrompt = (messages: UnifiedMessage[]): string => {
  let transcript = "";
  for (const msg of messages) {
    // Format date roughly as YYYY-MM-DD HH:MM
    const dateStr = msg.timestamp.toISOString().replace('T', ' ').substring(0, 16);
    transcript += `[${dateStr}] ${msg.sender}: ${msg.content}\n`;
  }

  return `
    TRANSCRIPT:
    ${transcript}
  `;
};

export const analyzeChunk = async (chunkId: number, messages: UnifiedMessage[]): Promise<Record<string, unknown>> => {
  const manager = initKeyManager();
  const maxRetries = 10;

  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      const apiKey = await manager.getActiveKey();
      const genAI = new GoogleGenerativeAI(apiKey);
      const model = genAI.getGenerativeModel({
        model: "gemini-1.5-flash", // Updated to stable model name if possible, or keep as preview
        systemInstruction: getAnalysisSystemInstruction(),
        generationConfig: { responseMimeType: "application/json" }
      });

      const prompt = constructAnalysisPrompt(messages);

      const result = await model.generateContent(prompt);
      const response = await result.response;
      return JSON.parse(response.text());

    } catch (e: unknown) {
      const err = e as { message?: string, status?: number };
      if (err.message?.includes("429") || err.status === 429) {
        manager.markCurrentAccountExhausted();
      } else {
        console.error(`Error analyzing chunk ${chunkId}:`, e);
        return {};
      }
    }
  }

  console.error(`Failed to analyze chunk ${chunkId} after ${maxRetries} attempts.`);
  return {};
};

export const aggregateProfiles = (chunkResults: Record<string, unknown>[]): AnalysisProfile => {
  const sets = {
      explicit_interests: new Set<string>(),
      implicit_interests: new Set<string>(),
      gift_mentions: new Set<string>(),
      dislikes: new Set<string>(),
      topics_discussed: new Set<string>(),
      relationship_dynamics: new Set<string>(),
      inside_jokes: new Set<string>(),
      closeness_indicators: new Set<string>(),
      sentiment_trend: new Set<string>()
  };

  const safeUpdate = (targetSet: Set<string>, items: unknown) => {
      if (Array.isArray(items)) {
          items.forEach(item => {
              if (typeof item === 'object') {
                  targetSet.add(JSON.stringify(item));
              } else {
                  targetSet.add(String(item));
              }
          });
      }
  };

  for (const res of chunkResults) {
    safeUpdate(sets.explicit_interests, res.explicit_interests);
    safeUpdate(sets.implicit_interests, res.implicit_interests);
    safeUpdate(sets.gift_mentions, res.gift_mentions);
    safeUpdate(sets.dislikes, res.dislikes);
    safeUpdate(sets.topics_discussed, res.key_dates); // Mapping key_dates to topics as in python
    safeUpdate(sets.relationship_dynamics, res.relationship_dynamics);
    safeUpdate(sets.inside_jokes, res.inside_jokes);
    safeUpdate(sets.closeness_indicators, res.closeness_indicators);
    safeUpdate(sets.sentiment_trend, res.sentiment_trend);
  }

  return {
      explicit_interests: Array.from(sets.explicit_interests),
      implicit_interests: Array.from(sets.implicit_interests),
      gift_mentions: Array.from(sets.gift_mentions),
      dislikes: Array.from(sets.dislikes),
      topics_discussed: Array.from(sets.topics_discussed),
      relationship_dynamics: Array.from(sets.relationship_dynamics),
      inside_jokes: Array.from(sets.inside_jokes),
      closeness_indicators: Array.from(sets.closeness_indicators),
      sentiment_trend: Array.from(sets.sentiment_trend),
  };
};

export const generateGiftRecommendations = async (profile: AnalysisProfile): Promise<string> => {
    const manager = initKeyManager();
    const profileSummary = JSON.stringify(profile, null, 2);

    const prompt = `
    Based on the following 'Memory Map' of a user's interests derived from their chat history (Hinglish/English), recommend the Top 5 Gifts for them.

    MEMORY MAP:
    ${profileSummary}

    OUTPUT FORMAT:
    Provide a list of 5 high-quality, thoughtful gift ideas.
    For each idea:
    - **Gift**: Name of the item/experience.
    - **Reasoning**: Why this fits their profile (cite specific interests).
    - **emotional_value**: How it connects to their chats.
    `;

    try {
        const apiKey = await manager.getActiveKey();
        const genAI = new GoogleGenerativeAI(apiKey);
        const model = genAI.getGenerativeModel({ model: "gemini-1.5-pro" });

        const result = await model.generateContent(prompt);
        return result.response.text();
    } catch (e) {
        console.error("Error generating recommendations:", e);
        return "Could not generate recommendations due to an error.";
    }
};

export const generateRelationshipReport = async (profile: AnalysisProfile): Promise<string> => {
    const manager = initKeyManager();

    const profileData = {
        dynamics: profile.relationship_dynamics,
        inside_jokes: profile.inside_jokes,
        closeness: profile.closeness_indicators,
        sentiment_history: profile.sentiment_trend,
        topics: profile.topics_discussed
    };
    const profileSummary = JSON.stringify(profileData, null, 2);

    const prompt = `
    You are an expert Relationship Psychologist.
    Based on the following aggregated 'Relationship Profile' derived from a chat history, write a deep analysis of the bond between these two people.

    RELATIONSHIP DATA:
    ${profileSummary}

    OUTPUT FORMAT:
    Write a beautiful, engaging MarkDown report (Title: # Relationship Insights).

    Structure:
    1. **The Vibe**: Describe their dynamic in a paragraph. Are they besties, partners, formal colleagues? What's the energy?
    2. **Connection Meter**: Rate their closeness (1-10) and explain why based on the 'closeness_indicators'.
    3. **Inside World**: List their inside jokes, nicknames, or unique behaviors. explain what these imply about their shared history.
    4. **Emotional Landscape**: Analyze the sentiment trends. Is it mostly supportive, fun, dramatic?
    5. **Verdict**: A final summary sentence defining their relationship.

    Make it sound human, insightful, and warm.
    `;

    try {
        const apiKey = await manager.getActiveKey();
        const genAI = new GoogleGenerativeAI(apiKey);
        const model = genAI.getGenerativeModel({ model: "gemini-1.5-pro" });

        const result = await model.generateContent(prompt);
        return result.response.text();
    } catch (e) {
        console.error("Error generating relationship report:", e);
        return "Could not generate relationship report due to an error.";
    }
};
