"""
Aggressive Chat Compression Script
-----------------------------------
This script takes a WhatsApp chat export and compresses it into a highly 
token-efficient format for LLM analysis.

Compression techniques used:
1. Timestamp precision reduced: Only YY-MM (year-month) is stored.
2. Platform index removed: Since all messages are from one platform (WhatsApp), 
   this constant data is dropped.
3. Structural overhead reduced: Uses a newline-delimited format instead of
   nested JSON arrays, which saves characters on commas and brackets.

Output Format:
- Line 1: JSON object with metadata (senders list, original message count).
- Lines 2+: Tab-separated values: YY-MM\tSenderIndex\tContent
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# Add src to python path for imports
sys.path.append(str(Path(__file__).resolve().parent / "src"))

from parsers import parse_whatsapp


def compress_chat(input_path: Path, output_path: Path):
    """
    Parses a WhatsApp chat file and outputs a highly compressed version.
    """
    print(f"Parsing: {input_path}")
    messages = parse_whatsapp(input_path)
    
    if not messages:
        print("Error: No messages found.")
        return

    print(f"Parsed {len(messages)} messages.")

    # Build sender index
    senders = []
    sender_map = {}
    for msg in messages:
        if msg.sender not in sender_map:
            sender_map[msg.sender] = len(senders)
            senders.append(msg.sender)

    # Create metadata line
    metadata = {
        "senders": senders,
        "count": len(messages),
        "format": "YY-MM<tab>SenderIdx<tab>Content"
    }

    # Build output lines
    output_lines = [json.dumps(metadata, separators=(',', ':'), ensure_ascii=False)]

    for msg in messages:
        # Timestamp: YY-MM (e.g., "23-09" for September 2023)
        ts_compact = msg.timestamp.strftime("%y-%m")
        
        # Sender index
        s_idx = sender_map[msg.sender]
        
        # Content: escape newlines for the format
        content = msg.content.replace('\n', '\\n').replace('\t', ' ')
        
        # Tab-separated line
        line = f"{ts_compact}\t{s_idx}\t{content}"
        output_lines.append(line)

    # Write output
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_lines))

    # Calculate compression stats
    original_size_approx = sum(len(m.content) + 30 for m in messages)  # Approx original overhead
    new_size = sum(len(line) for line in output_lines)
    
    print(f"Output written to: {output_path}")
    print(f"Estimated original token size: ~{original_size_approx:,}")
    print(f"New compressed size: ~{new_size:,} characters")
    print(f"Compression ratio: ~{original_size_approx / new_size:.2f}x")


def main():
    parser = argparse.ArgumentParser(description="Aggressively compress a WhatsApp chat export.")
    parser.add_argument("input", type=Path, help="Path to WhatsApp chat export file (.txt)")
    parser.add_argument("-o", "--output", type=Path, default=None, help="Output path for compressed file. Defaults to input_compressed.txt")
    
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}")
        return

    output_path = args.output if args.output else args.input.with_name(f"{args.input.stem}_compressed.txt")
    
    compress_chat(args.input, output_path)


if __name__ == "__main__":
    main()
