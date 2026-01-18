from typing import List, Dict, Any, Union
import json
import math
from pathlib import Path
from datetime import datetime

# Adjust import based on usage (script vs package)
if __package__:
    from .models import UnifiedMessage
else:
    from models import UnifiedMessage

def convert_to_optimized_format(messages: List[UnifiedMessage]) -> Dict[str, Any]:
    """
    Converts a list of UnifiedMessage objects into a highly optimized table format.
    """
    platforms = []
    senders = []
    platform_map = {}
    sender_map = {}

    data = []

    for msg in messages:
        p = msg.platform
        if p not in platform_map:
            platform_map[p] = len(platforms)
            platforms.append(p)
        p_idx = platform_map[p]

        s = msg.sender
        if s not in sender_map:
            sender_map[s] = len(senders)
            senders.append(s)
        s_idx = sender_map[s]

        # DateTime to ISO string
        ts = msg.timestamp.isoformat()
        content = msg.content

        row = [ts, p_idx, s_idx, content]
        data.append(row)

    return {
        "meta": {
            "platforms": platforms,
            "senders": senders
        },
        "columns": ["timestamp", "platform_idx", "sender_idx", "content"],
        "data": data
    }

def estimate_tokens(text: str) -> int:
    """
    Rough estimation of tokens.
    Previously we used len(text)/4 (standard for English), but JSON/Code is much denser.
    We now use len(text) (1 char = 1 token) as a safe conservative upper bound 
    to ensure we strictly stay under limits like 500k.
    """
    return len(text)

def save_optimized_json(data: Dict[str, Any], filepath: Path, max_tokens: int = 500000):
    """
    Saves the dictionary as minified JSON file(s).
    If the data exceeds max_tokens, it splits into multiple files:
    filepath_part1.json, filepath_part2.json, etc.
    """
    meta = data['meta']
    columns = data['columns']
    rows = data['data']
    
    # Calculate base overhead tokens (meta + columns)
    # We serialize it to check size
    base_structure = {"meta": meta, "columns": columns, "data": []}
    base_json = json.dumps(base_structure, separators=(',', ':'), ensure_ascii=False)
    base_tokens = estimate_tokens(base_json)
    
    current_tokens = base_tokens
    current_chunk_rows = []
    part_number = 1
    
    # Helper to save a chunk
    def save_chunk(rows_to_save, part_num, total_parts=None):
        chunk_data = {
            "meta": meta,
            "columns": columns,
            "data": rows_to_save
        }
        
        # Determine filename
        if total_parts == 1 and part_num == 1:
            # If only one part, use original filename
            save_path = filepath
        else:
            # If multiple, use _partX suffix
            # e.g. processed_chat_history.json -> processed_chat_history_part1.json
            save_path = filepath.with_name(f"{filepath.stem}_part{part_num}{filepath.suffix}")
            
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(chunk_data, f, separators=(',', ':'), ensure_ascii=False)
        return save_path

    # First pass: Check if we even need to split?
    # Actually, let's just stream through and split as we go.
    
    saved_files = []
    
    for row in rows:
        # row schema: [timestamp, platform_idx, sender_idx, content]
        # Content is usually the bulk of tokens.
        content = row[3]
        row_tokens = estimate_tokens(content if content else "") + 10 # +10 for metadata overhead in row
        
        if current_tokens + row_tokens > max_tokens and current_chunk_rows:
            # Functionally "full", save current chunk
            saved_files.append(current_chunk_rows)
            # Reset
            current_chunk_rows = []
            current_tokens = base_tokens
        
        current_chunk_rows.append(row)
        current_tokens += row_tokens
        
    # Add last chunk
    if current_chunk_rows:
        saved_files.append(current_chunk_rows)
        
    # Now actually write the files
    num_parts = len(saved_files)
    created_paths = []
    for i, rows_in_chunk in enumerate(saved_files):
        path = save_chunk(rows_in_chunk, i + 1, num_parts)
        created_paths.append(path)
        
    return created_paths

def load_optimized_json(filepath: Path) -> Dict[str, Any]:
    """
    Loads raw optimized JSON data.
    Automatically detects if there are multiple parts (filepath_part*.json) and merges them.
    """
    # 1. Check if the exact single file exists
    if filepath.exists():
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
            
    # 2. Check for parts
    directory = filepath.parent
    stem = filepath.stem # e.g. processed_chat_history
    suffix = filepath.suffix # e.g. .json
    
    # Look for stem_part*.json
    # We want to find files that match the pattern, distinct from other files
    # E.g. processed_chat_history_part1.json
    
    parts = sorted(directory.glob(f"{stem}_part*{suffix}"))
    
    if not parts:
        raise FileNotFoundError(f"No file found at {filepath} and no parts found matching {stem}_part*{suffix}")
        
    # Merge parts
    merged_data = None
    all_rows = []
    
    for part in parts:
        with open(part, 'r', encoding='utf-8') as f:
            part_data = json.load(f)
            
        if merged_data is None:
            # Initialize with meta/columns from first part
            merged_data = {
                "meta": part_data.get("meta"),
                "columns": part_data.get("columns"),
                "data": [] # Will fill this
            }
        
        # Append rows
        all_rows.extend(part_data.get("data", []))
        
    if merged_data:
        merged_data["data"] = all_rows
        return merged_data
    
    raise ValueError("Empty parts found.")

def decode_to_unified_messages(data: Dict[str, Any]) -> List[UnifiedMessage]:
    """
    Decodes the optimized dictionary back into a list of UnifiedMessage objects.
    """
    meta = data.get("meta", {})
    platforms = meta.get("platforms", [])
    senders = meta.get("senders", [])
    rows = data.get("data", [])
    
    messages = []
    for row in rows:
        # Schema: [timestamp, platform_idx, sender_idx, content]
        ts_str, p_idx, s_idx, content = row
        
        # Safe lookup in case indices are weird (though they shouldn't be)
        platform = platforms[p_idx] if 0 <= p_idx < len(platforms) else "Unknown"
        sender = senders[s_idx] if 0 <= s_idx < len(senders) else "Unknown"
        
        dt = datetime.fromisoformat(ts_str)
        
        messages.append(UnifiedMessage(
            timestamp=dt,
            platform=platform,
            sender=sender,
            content=content
        ))
        
    return messages
