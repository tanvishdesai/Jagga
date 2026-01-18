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
    Supports 24h and 12h formats, 2 or 4 digit years.
    Format line: "18/07/2024, 19:09 - User Name: Message"
             or: "28/08/23, 11:53 am - User Name: Message"
    """
    messages = []
    # Regex to capture: Date, Time, Sender, Message
    # Improved regex to handle:
    # - Date: d/m/y or d/m/Y (2 or 4 digits)
    # - Time: H:M or I:M am/pm (optional space/narrow non-break space)
    # - Sender: Any characters until ": "
    pattern = re.compile(r"^(\d{1,2}/\d{1,2}/\d{2,4}), (\d{1,2}:\d{2}(?:(?:\s|[\u202f])?[a-zA-Z]{2})?) - (.*?): (.*)$")
    
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
                    current_msg = None 
                    continue

                # Normalize time string: 
                # Replace narrow no-break space (\u202f) with standard space
                # ensuring AM/PM is standard
                clean_time_str = time_str.replace('\u202f', ' ').strip()
                
                # Try multiple formats
                dt = None
                formats_to_try = [
                    "%d/%m/%Y %H:%M",       # 24h, 4-digit year
                    "%d/%m/%y %H:%M",       # 24h, 2-digit year
                    "%d/%m/%Y %I:%M %p",    # 12h, 4-digit year
                    "%d/%m/%y %I:%M %p",    # 12h, 2-digit year
                    "%d/%m/%Y %I:%M%p",     # 12h, 4-digit year (no space)
                    "%d/%m/%y %I:%M%p",     # 12h, 2-digit year (no space)
                    "%d/%m/%y %I:%M %p"     # fallbacks logic handling case insensitivity via upper() below
                ]
                
                full_dt_str = f"{date_str} {clean_time_str}"
                
                # Helper to handle AM/PM case insensitivity
                # strptime %p requires AM/PM usually
                upper_dt_str = full_dt_str.upper().replace("AM", "AM").replace("PM", "PM")

                for fmt in formats_to_try:
                    try:
                        dt = datetime.strptime(upper_dt_str, fmt)
                        break
                    except ValueError:
                        continue
                
                if not dt:
                    # If all parsing fails, log warning or skip?
                    # For now, let's skip silently or maybe just print debug if strict
                    # print(f"Failed to parse date: {full_dt_str}")
                    current_msg = None
                    continue

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
