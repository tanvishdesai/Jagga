import re
import json
from datetime import datetime
from typing import List
from pathlib import Path

# Adjust import based on usage (script vs package)
if __package__:
    from .models import UnifiedMessage
else:
    from models import UnifiedMessage

def parse_whatsapp(file_path: Path) -> List[UnifiedMessage]:
    """
    Parses WhatsApp exported text file.
    Format line: "18/07/2024, 19:09 - User Name: Message"
    """
    messages = []
    # Regex to capture: Date, Time, Sender, Message
    # Example: 18/07/2024, 19:09 - Sneha Bajaj LDRP: Kya similarity hai?
    # Note: Sender name can contain spaces. Message can be multiline.
    pattern = re.compile(r"^(\d{2}/\d{2}/\d{4}), (\d{2}:\d{2}) - (.*?): (.*)$")
    
    current_msg = None
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
                
            match = pattern.match(line)
            if match:
                # Save previous message if it exists
                if current_msg:
                    messages.append(current_msg)
                
                date_str, time_str, sender, content = match.groups()
                
                # Handling "Media omitted"
                if content.strip() == "<Media omitted>":
                    current_msg = None # Skip media messages for now or mark them? 
                    # Let's skip them for text analysis to reduce noise
                    continue

                dt = datetime.strptime(f"{date_str} {time_str}", "%d/%m/%Y %H:%M")
                
                current_msg = UnifiedMessage(
                    timestamp=dt,
                    platform="WhatsApp",
                    sender=sender.strip(),
                    content=content
                )
            else:
                # This is a continuation of the previous message (multi-line)
                if current_msg:
                    current_msg.content += f"\n{line}"
    
    # Append the last message
    if current_msg:
        messages.append(current_msg)
        
    return messages

def parse_instagram(file_path: Path) -> List[UnifiedMessage]:
    """
    Parses Instagram exported JSON file.
    Structure: { "messages": [ { "sender_name": "...", "timestamp_ms": 123, "content": "..." } ] }
    """
    messages = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    for msg in data.get("messages", []):
        sender = msg.get("sender_name")
        ts_ms = msg.get("timestamp_ms")
        content = msg.get("content")
        
        # Skip messages without text content (e.g., pure media sends without caption)
        # Note: 'share' key exists for shared posts, might want to capture description
        if not content:
            if "share" in msg and "share_text" in msg["share"]:
                content = f"[Shared Post] {msg['share']['share_text']}"
            else:
                continue

        # Handle 'Blocked' or 'Unsent' flags if necessary (ignoring for now)
        
        # Convert timestamp
        # Instagram uses milliseconds
        dt = datetime.fromtimestamp(ts_ms / 1000.0)
        
        # Instagram text decoding might be needed for utf-8 (sometimes it's latin-1 encoded in json string)
        # But Python's json usually handles utf-8. 
        # Known legacy FB/Insta issue: Text is often latin-1 encoded bytes showing as escaped unicode.
        # Fix for mojibake:
        try:
            content = content.encode('latin1').decode('utf-8')
            sender = sender.encode('latin1').decode('utf-8')
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass # Keep original if fix fails

        messages.append(UnifiedMessage(
            timestamp=dt,
            platform="Instagram",
            sender=sender,
            content=content
        ))
        
    # Sort by timestamp (usually Instagram export is reverse chronological)
    messages.sort(key=lambda x: x.timestamp)
    
    return messages
