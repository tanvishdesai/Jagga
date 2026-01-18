import sys
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime
import shutil

# Add src to python path to allow imports if running from root
sys.path.append(str(Path(__file__).resolve().parent))

from config import (
    WHATSAPP_PATH, 
    INSTAGRAM_PATH, 
    GEMINI_ACCOUNT_KEYS,
    OUTPUT_DIR
)
from parsers import parse_whatsapp, parse_instagram
from analyzer import (
    chunk_messages, 
    analyze_chunk, 
    aggregate_profiles, 
    generate_gift_recommendations,
    generate_relationship_report,
    construct_analysis_prompt,
    get_analysis_system_instruction
)
from models import UnifiedMessage
from optimization import (
    convert_to_optimized_format, 
    save_optimized_json, 
    load_optimized_json, 
    decode_to_unified_messages
)

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("GiftRecSystem")

def main():
    parser = argparse.ArgumentParser(description="Intelligent Gift Recommendation System")
    parser.add_argument("--dry-run", action="store_true", help="Run without calling Gemini API for testing ingestion.")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of messages to analyze.")
    parser.add_argument("--skip-analysis", action="store_true", help="Skip the Gemini analysis phase and only produce the optimized chat JSON.")
    parser.add_argument("--whatsapp", type=Path, default=None, help="Path to WhatsApp chat export file (.txt)")
    parser.add_argument("--instagram", type=Path, default=None, help="Path to Instagram chat export file (.json)")
    parser.add_argument("--useAI", action="store_true", help="Enable Gemini API calls. When False (default), generates prompts locally.")
    args = parser.parse_args()

    # --- Path Resolution (Args override Config) ---
    target_whatsapp = args.whatsapp if args.whatsapp else WHATSAPP_PATH
    target_instagram = args.instagram if args.instagram else INSTAGRAM_PATH


    # --- Dynamic Output Setup ---
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    
    # Identify Chat Name for Slug
    chat_slug = "unknown_chat"
    person_name = "Unknown"
    
    if target_whatsapp and target_whatsapp.exists():
        # e.g. "WhatsApp Chat with Shivam Dwivedi.txt" -> "WhatsApp_Chat_with_Shivam_Dwivedi"
        chat_slug = target_whatsapp.stem.replace(" ", "_").replace(".", "")
        # Extract person name if possible (heuristic: after "WhatsApp Chat with ")
        if "WhatsApp Chat with " in target_whatsapp.stem:
            person_name = target_whatsapp.stem.replace("WhatsApp Chat with ", "").strip()
            
    elif target_instagram and target_instagram.exists():
        chat_slug = target_instagram.stem.replace(" ", "_")

    # Create Run Directory
    RUN_DIR = OUTPUT_DIR / f"{timestamp}__{chat_slug}"
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    
    # Create Sub-directories
    ORIGINAL_CHATS_DIR = RUN_DIR / "original_chats"
    PROCESSED_DATA_DIR = RUN_DIR / "processed_data"
    REPORTS_DIR = RUN_DIR / "reports"
    PROMPTS_DIR = RUN_DIR / "prompts"
    
    ORIGINAL_CHATS_DIR.mkdir(exist_ok=True)
    PROCESSED_DATA_DIR.mkdir(exist_ok=True)
    
    if args.useAI:
        REPORTS_DIR.mkdir(exist_ok=True)
    else:
        PROMPTS_DIR.mkdir(exist_ok=True)
    
    logger.info(f"Created output directory for this run: {RUN_DIR}")

    # Copy and Rename Original Files
    if target_whatsapp and target_whatsapp.exists():
        # Copy with original name or normalized? User said "original chats, where whatsapp chat text file will be copied"
        # and "instagram json will be modified with the name of the person"
        dest_wa = ORIGINAL_CHATS_DIR / target_whatsapp.name
        shutil.copy2(target_whatsapp, dest_wa)
        logger.info(f"Copied WhatsApp chat to: {dest_wa}")
        
    if target_instagram and target_instagram.exists():
        # Rename Instagram file: "Instagram_Chat_with_<PersonName>.json"
        safe_person_name = person_name.replace(" ", "_").replace(".", "")
        new_filename = f"Instagram_Chat_with_{safe_person_name}.json"
        dest_ig = ORIGINAL_CHATS_DIR / new_filename
        shutil.copy2(target_instagram, dest_ig)
        logger.info(f"Copied & Renamed Instagram chat to: {dest_ig}")

    # Define Dynamic File Paths
    PROCESSED_DATA_PATH = PROCESSED_DATA_DIR / f"processed_{chat_slug}.json"
    MEMORY_MAP_PATH = PROCESSED_DATA_DIR / f"memory_map_{chat_slug}.json"
    CHECKPOINT_FILE = PROCESSED_DATA_DIR / "chunk_results_checkpoint.json"
    RECOMMENDATIONS_PATH = REPORTS_DIR / f"recommendations_{chat_slug}.md"
    RELATIONSHIP_REPORT_PATH = REPORTS_DIR / f"relationship_report_{chat_slug}.md"

    # 1. Ingestion
    logger.info("Starting Data Ingestion...")
    all_messages = []
    
    # NOTE: Since we are creating a fresh directory every run, we naturally "Force" reprocessing 
    # of raw files every time (unless we implemented logic to find the *previous* run folder, 
    # which is complex and likely not what is desired for 'clean' output).
    # So we simply parse the inputs.
    
    if target_whatsapp and target_whatsapp.exists():
        logger.info(f"Parsing WhatsApp: {target_whatsapp}")
        wa_msgs = parse_whatsapp(target_whatsapp)
        all_messages.extend(wa_msgs)
    else:
        if target_whatsapp: logger.warning(f"WhatsApp file not found at {target_whatsapp}")

    if target_instagram and target_instagram.exists():
        logger.info(f"Parsing Instagram: {target_instagram}")
        ig_msgs = parse_instagram(target_instagram)
        all_messages.extend(ig_msgs)
    else:
        if target_instagram: logger.warning(f"Instagram file not found at {target_instagram}")

    if not all_messages:
        logger.error("No messages found from any source. Exiting.")
        return

    # 2. Sorting & Deduplication (Basic)
    all_messages.sort(key=lambda x: x.timestamp)
    logger.info(f"Total messages loaded: {len(all_messages)}")

    # Save Processed Data (OPTIMIZED FORMAT)
    logger.info("Converting to optimized Toon format...")
    optimized_data = convert_to_optimized_format(all_messages)
    
    # Save (handles splitting automatically)
    saved_paths = save_optimized_json(optimized_data, PROCESSED_DATA_PATH)
    for path in saved_paths:
        logger.info(f"Saved optimized chunk: {path}")

    # Exit if we only wanted to convert data
    if args.skip_analysis:
        logger.info("Skipping analysis phase as requested.")
        return

    if args.dry_run:
        logger.info("Dry run completed. Exiting before analysis.")
        return

    # 3. Intelligence / Analysis
    if args.useAI and not GEMINI_ACCOUNT_KEYS:
        logger.error("Gemini Account Keys not found in config.py.")
        print("\n[!] Please provide valid Gemini API Keys provided in config.py")
        return

    logger.info("Starting Intelligence Phase...")
    
    # Apply limit if specified
    msgs_to_analyze = all_messages
    if args.limit:
        msgs_to_analyze = all_messages[-args.limit:] # Analyze recent messages if limited
        logger.info(f"Limiting analysis to last {args.limit} messages.")

    # Increased chunk size to reduce number of API calls
    chunks = chunk_messages(msgs_to_analyze, chunk_size=300) 
    logger.info(f"Created {len(chunks)} chunks for analysis.")

    # OFFLINE MODE: Generate Prompts Only
    if not args.useAI:
        logger.info("--- OFFLINE MODE ---")
        
        system_instruction = get_analysis_system_instruction()
        
        # Save SINGLE system prompt file
        p_file = PROMPTS_DIR / "system_instruction.txt"
        with open(p_file, "w", encoding="utf-8") as f:
            f.write(system_instruction)
        
        logger.info(f"Successfully saved system instruction to: {p_file}")
        logger.info("Use this prompt to process the JSON chunks in Google AI Studio.")
        return

    chunk_results = []
    total_chunks = len(chunks)
    
    # Check if there is an existing checkpoint (Only relevant if we restart *this* specific run context, 
    # but practically minimal since we make new dirs. Could be useful if we manually point to it.)
    if CHECKPOINT_FILE.exists():
        logger.info(f"Found checkpoint file at {CHECKPOINT_FILE}. Loading...")
        try:
            with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
                chunk_results = json.load(f)
            logger.info(f"Loaded {len(chunk_results)} processed chunks. Resuming analysis...")
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")

    # Start from where we left off
    start_index = len(chunk_results)

    for i in range(start_index, total_chunks):
        chunk = chunks[i]
        logger.info(f"Analyzing chunk {i+1}/{total_chunks}...")
        result = analyze_chunk(i, chunk)
        if result:
            chunk_results.append(result)
            
            # Save checkpoint every chunk
            with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
                json.dump(chunk_results, f, ensure_ascii=False)
        
    # 4. Aggregation
    logger.info("Aggregating Memory Map...")
    memory_map = aggregate_profiles(chunk_results)
    
    # Save Memory Map
    with open(MEMORY_MAP_PATH, 'w', encoding='utf-8') as f:
        # Convert dataclass to dict via json dump default or custom
        f.write(json.dumps(memory_map.__dict__, indent=2, ensure_ascii=False))
    logger.info(f"Memory Map saved to {MEMORY_MAP_PATH}")

    # 5. Recommendation
    logger.info("Generating Final Recommendations...")
    recommendations = generate_gift_recommendations(memory_map)
    
    print("\n" + "="*50)
    print(" GIFT RECOMMENDATIONS ")
    print("="*50 + "\n")
    print(recommendations)
    print("\n" + "="*50)

    # Save Recommendations
    with open(RECOMMENDATIONS_PATH, 'w', encoding='utf-8') as f:
        f.write(recommendations)
    logger.info(f"Recommendations saved to {RECOMMENDATIONS_PATH}")

    # 6. Relationship Analysis
    logger.info("Generating Relationship Report...")
    relationship_report = generate_relationship_report(memory_map)
    
    with open(RELATIONSHIP_REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write(relationship_report)
    logger.info(f"Relationship report saved to {RELATIONSHIP_REPORT_PATH}")
    
    print("\n" + "="*50)
    print(" RELATIONSHIP REPORT SAVED ")
    print("="*50 + "\n")

if __name__ == "__main__":
    main()
