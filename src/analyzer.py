import os
import time
import json
import logging
from typing import List, Dict
import google.generativeai as genai
from config import GEMINI_ACCOUNT_KEYS
from models import UnifiedMessage, AnalysisProfile

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KeyManager:
    """
    Manages multiple Google Accounts, each with a list of API Key(s).
    Structure: [ [Acc1_K1, Acc1_K2], [Acc2_K1], ... ]
    """
    def __init__(self, account_keys: List[List[str]]):
        self.account_keys = [keys for keys in account_keys if keys] # Filter empty lists
        self.current_acc_idx = 0
        self.current_key_indices = [0] * len(self.account_keys)
        self.account_cooldowns: Dict[int, float] = {} # acc_idx -> timestamp available
        self.cooldown_duration = 90 # 1.5 Minutes as requested

    def get_active_key(self) -> str:
        """
        Returns a valid API key from an available account.
        """
        if not self.account_keys:
            raise ValueError("No API keys provided in config.")

        start_idx = self.current_acc_idx
        
        # 1. Try to find an account not in cooldown
        for _ in range(len(self.account_keys)):
            acc_idx = self.current_acc_idx
            
            if acc_idx not in self.account_cooldowns or time.time() > self.account_cooldowns[acc_idx]:
                # Found available account, get its current key
                key_idx = self.current_key_indices[acc_idx]
                keys = self.account_keys[acc_idx]
                
                # Rotate key index for this account for next time (Round Robin)
                self.current_key_indices[acc_idx] += 1
                
                return keys[key_idx % len(keys)]
            
            # Try next account
            self.current_acc_idx = (self.current_acc_idx + 1) % len(self.account_keys)

        # 2. If all accounts cooling down, wait for the soonest
        earliest_time = min(self.account_cooldowns.values())
        wait_time = earliest_time - time.time()
        
        if wait_time > 0:
            logger.warning(f"All Accounts are in cooldown / quota limit. Waiting {wait_time:.1f}s...")
            time.sleep(wait_time + 1)
        
        return self.get_active_key()

    def mark_current_account_exhausted(self):
        """
        Call this when 429 is received. Marks the *entire account* as exhausted/cooldown.
        """
        acc_idx = self.current_acc_idx
        logger.warning(f"Account {acc_idx} hit rate/quota limit. Switching account...")
        
        self.account_cooldowns[acc_idx] = time.time() + self.cooldown_duration
        
        # Switch to next account immediately
        self.current_acc_idx = (self.current_acc_idx + 1) % len(self.account_keys)

# Initialize Manager
try:
    key_manager = KeyManager(GEMINI_ACCOUNT_KEYS)
except ValueError:
    logger.error("Failed to initialize KeyManager. Check config.py")
    key_manager = None

def chunk_messages(messages: List[UnifiedMessage], chunk_size: int = 50) -> List[List[UnifiedMessage]]:
    """
    Splits the list of messages into smaller chunks to fit context windows.
    """
    return [messages[i:i + chunk_size] for i in range(0, len(messages), chunk_size)]

def analyze_chunk(chunk_id: int, messages: List[UnifiedMessage]) -> Dict:
    """
    Sends a chunk of messages to Gemini Flash for interest extraction.
    """
    if not GEMINI_ACCOUNT_KEYS:
        logger.error("Gemini API Keys are missing.")
        return {}

def get_analysis_system_instruction() -> str:
    """
    Returns the static system instruction for the analysis.
    """
    return """
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
    """

def construct_analysis_prompt(messages: List[UnifiedMessage]) -> str:
    """
    Constructs the prompt string for the analysis.
    """
    # Format transcript for the prompt
    transcript = ""
    for msg in messages:
        transcript += f"[{msg.timestamp.strftime('%Y-%m-%d %H:%M')}] {msg.sender}: {msg.content}\n"

    system_instruction = get_analysis_system_instruction()
    
    prompt = f"""
    {system_instruction}

    TRANSCRIPT:
    {transcript}
    """
    return prompt
    return prompt

def analyze_chunk(chunk_id: int, messages: List[UnifiedMessage]) -> Dict:
    """
    Sends a chunk of messages to Gemini Flash for interest extraction.
    """
    if not GEMINI_ACCOUNT_KEYS:
        logger.error("Gemini API Keys are missing.")
        return {}

    prompt = construct_analysis_prompt(messages)
    
    max_retries = 10 # Higher retries for rotation
    
    for attempt in range(max_retries):
        try:
            # 1. Get a valid key from active account
            if not key_manager:
                 return {}
            api_key = key_manager.get_active_key()
            genai.configure(api_key=api_key)
            
            # 2. Make Request
            # Small delay to respect 5 RPM (Requests Per Minute) per account roughly if loop is tight
            # If we switch accounts, we are fresh.
            time.sleep(1) 

            model = genai.GenerativeModel('gemini-3-flash-preview')
            response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
            return json.loads(response.text)
            
        except Exception as e:
            error_str = str(e)
            if "429" in error_str:
                # 429 means THIS ACCOUNT is exhausted (limit per project)
                key_manager.mark_current_account_exhausted()
            else:
                logger.error(f"Error analyzing chunk {chunk_id}: {e}")
                return {}
    
    logger.error(f"Failed to analyze chunk {chunk_id} after {max_retries} attempts.")
    return {}

def aggregate_profiles(chunk_results: List[Dict]) -> AnalysisProfile:
    """
    Merges multiple extraction results into a single profile.
    This simple aggregation just concatenates lists; a smarter version could dedup or summarize again.
    """
    aggregated = {
        "explicit_interests": set(),
        "implicit_interests": set(),
        "gift_mentions": set(),
        "dislikes": set(),
        "topics_discussed": set(), # Using key_dates as topics or similar
        "relationship_dynamics": set(),
        "inside_jokes": set(),
        "closeness_indicators": set(),
        "sentiment_trend": set()
    }

    def safe_update(target_set, items):
        for item in items:
            if isinstance(item, (dict, list)):
                # Convert complex objects to string so they can be hashed
                target_set.add(json.dumps(item, ensure_ascii=False))
            else:
                target_set.add(str(item))

    for res in chunk_results:
        safe_update(aggregated["explicit_interests"], res.get("explicit_interests", []))
        safe_update(aggregated["implicit_interests"], res.get("implicit_interests", []))
        safe_update(aggregated["gift_mentions"], res.get("gift_mentions", []))
        safe_update(aggregated["dislikes"], res.get("dislikes", []))
        safe_update(aggregated["topics_discussed"], res.get("key_dates", []))
        safe_update(aggregated["relationship_dynamics"], res.get("relationship_dynamics", []))
        safe_update(aggregated["inside_jokes"], res.get("inside_jokes", []))
        safe_update(aggregated["closeness_indicators"], res.get("closeness_indicators", []))
        safe_update(aggregated["sentiment_trend"], res.get("sentiment_trend", [])) 

    return AnalysisProfile(
        explicit_interests=list(aggregated["explicit_interests"]),
        implicit_interests=list(aggregated["implicit_interests"]),
        gift_mentions=list(aggregated["gift_mentions"]),
        dislikes=list(aggregated["dislikes"]),
        topics_discussed=list(aggregated["topics_discussed"]),
        relationship_dynamics=list(aggregated["relationship_dynamics"]),
        inside_jokes=list(aggregated["inside_jokes"]),
        closeness_indicators=list(aggregated["closeness_indicators"]),
        sentiment_trend=list(aggregated["sentiment_trend"])
    )

def generate_gift_recommendations(profile: AnalysisProfile) -> str:
    """
    Uses the aggregated profile to generate final gift recommendations using Gemini Pro.
    """
    if not GEMINI_ACCOUNT_KEYS:
        return "Error: No API Key."

    profile_summary = json.dumps(profile.__dict__, indent=2, ensure_ascii=False)

    prompt = f"""
    Based on the following 'Memory Map' of a user's interests derived from their chat history (Hinglish/English), recommend the Top 5 Gifts for them.

    MEMORY MAP:
    {profile_summary}

    OUTPUT FORMAT:
    Provide a list of 5 high-quality, thoughtful gift ideas.
    For each idea:
    - **Gift**: Name of the item/experience.
    - **Reasoning**: Why this fits their profile (cite specific interests).
    - **emotional_value**: How it connects to their chats.
    """

    try:
        if key_manager:
            api_key = key_manager.get_active_key()
            genai.configure(api_key=api_key)

            model = genai.GenerativeModel('gemini-1.5-pro')
            response = model.generate_content(prompt)
            return response.text
        else:
            return "Error: KeyManager not initialized."
    except Exception as e:
        logger.error(f"Error generating recommendations: {e}")
        return "Could not generate recommendations due to an error."

def generate_relationship_report(profile: AnalysisProfile) -> str:
    """
    Generates a deep dive relationship analysis report using Gemini.
    """
    if not GEMINI_ACCOUNT_KEYS:
        return "Error: No API Key."

    # Serialize profile
    # We select relevant fields to not overwhelm context if list is huge
    profile_data = {
        "dynamics": profile.relationship_dynamics,
        "inside_jokes": profile.inside_jokes,
        "closeness": profile.closeness_indicators,
        "sentiment_history": profile.sentiment_trend,
        "topics": profile.topics_discussed
    }
    profile_summary = json.dumps(profile_data, indent=2, ensure_ascii=False)

    prompt = f"""
    You are an expert Relationship Psychologist.
    Based on the following aggregated 'Relationship Profile' derived from a chat history, write a deep analysis of the bond between these two people.

    RELATIONSHIP DATA:
    {profile_summary}

    OUTPUT FORMAT:
    Write a beautiful, engaging MarkDown report (Title: # Relationship Insights).
    
    Structure:
    1. **The Vibe**: Describe their dynamic in a paragraph. Are they besties, partners, formal colleagues? What's the energy?
    2. **Connection Meter**: Rate their closeness (1-10) and explain why based on the 'closeness_indicators'.
    3. **Inside World**: List their inside jokes, nicknames, or unique behaviors. explain what these imply about their shared history.
    4. **Emotional Landscape**: Analyze the sentiment trends. Is it mostly supportive, fun, dramatic?
    5. **Verdict**: A final summary sentence defining their relationship.

    Make it sound human, insightful, and warm.
    """

    try:
        # Use first available key for this single call
        # In a real app we'd use the proper key manager, but here we can reuse the global one or init a temp one
        # For simplicity, we'll re-init key manager logic or just grab the first one if we can't accept manager
        # Since we don't have the manager instance here easily without passing it, let's just try to grab a key manually 
        # OR better, update the signature to take the key_manager if needed.
        # But wait, KeyManager is global in this file (initialized at top).
        
        if key_manager:
            api_key = key_manager.get_active_key()
            genai.configure(api_key=api_key)
            
            model = genai.GenerativeModel('gemini-1.5-pro')
            response = model.generate_content(prompt)
            return response.text
        else:
             return "Error: KeyManager not initialized."
             
    except Exception as e:
        logger.error(f"Error generating relationship report: {e}")
        return "Could not generate relationship report due to an error."

