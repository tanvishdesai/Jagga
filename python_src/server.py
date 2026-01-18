"""
FastAPI server for WhatsApp/Instagram chat preprocessing.
Accepts file uploads, runs preprocessing, and returns a downloadable zip file.
"""
import sys
import shutil
import tempfile
import zipfile
import logging
from pathlib import Path
from datetime import datetime
from io import BytesIO

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

# Add current directory to Python path for imports
sys.path.append(str(Path(__file__).resolve().parent))

from parsers import parse_whatsapp, parse_instagram
from optimization import convert_to_optimized_format, save_optimized_json
from analyzer import get_analysis_system_instruction
import json


def compress_messages(messages, output_path: Path):
    """
    Compresses messages into a highly token-efficient format.
    Uses YY-MM timestamps and sender indices for minimal token usage.
    """
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
    
    return output_path

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("ChatPreprocessorAPI")

app = FastAPI(
    title="Chat Preprocessor API",
    description="Upload WhatsApp/Instagram chats and get preprocessed data as a zip file",
    version="1.0.0"
)

# CORS middleware for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "message": "Chat Preprocessor API is running"}


@app.post("/api/process")
async def process_chats(
    whatsapp_file: UploadFile = File(..., description="WhatsApp chat export (.txt)"),
    instagram_file: UploadFile = File(None, description="Instagram chat export (.json) - Optional"),
    enable_compression: bool = Form(False, description="Enable aggressive compression for large chats")
):
    """
    Process uploaded chat files and return a zip with preprocessed data.
    
    - **whatsapp_file**: Required. WhatsApp exported chat (.txt file)
    - **instagram_file**: Optional. Instagram exported messages (.json file)
    
    Returns a zip file containing:
    - processed_data/: Optimized JSON files
    - prompts/: System instruction for AI analysis
    """
    
    # Validate WhatsApp file
    if not whatsapp_file.filename.endswith('.txt'):
        raise HTTPException(
            status_code=400,
            detail="WhatsApp file must be a .txt file"
        )
    
    # Validate Instagram file if provided
    if instagram_file and not instagram_file.filename.endswith('.json'):
        raise HTTPException(
            status_code=400,
            detail="Instagram file must be a .json file"
        )
    
    # Create temporary directory for processing
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        try:
            # Save uploaded WhatsApp file
            whatsapp_path = temp_path / whatsapp_file.filename
            with open(whatsapp_path, 'wb') as f:
                content = await whatsapp_file.read()
                f.write(content)
            logger.info(f"Saved WhatsApp file: {whatsapp_path}")
            
            # Save uploaded Instagram file if provided
            instagram_path = None
            if instagram_file:
                instagram_path = temp_path / instagram_file.filename
                with open(instagram_path, 'wb') as f:
                    content = await instagram_file.read()
                    f.write(content)
                logger.info(f"Saved Instagram file: {instagram_path}")
            
            # --- Dynamic Output Setup ---
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            
            # Identify Chat Name for Slug
            chat_slug = "unknown_chat"
            person_name = "Unknown"
            
            if whatsapp_path.exists():
                chat_slug = whatsapp_path.stem.replace(" ", "_").replace(".", "")
                if "WhatsApp Chat with " in whatsapp_path.stem:
                    person_name = whatsapp_path.stem.replace("WhatsApp Chat with ", "").strip()
            
            # Create output directory structure
            run_dir = temp_path / f"{timestamp}__{chat_slug}"
            run_dir.mkdir(parents=True, exist_ok=True)
            
            original_chats_dir = run_dir / "original_chats"
            processed_data_dir = run_dir / "processed_data"
            prompts_dir = run_dir / "prompts"
            
            original_chats_dir.mkdir(exist_ok=True)
            processed_data_dir.mkdir(exist_ok=True)
            prompts_dir.mkdir(exist_ok=True)
            
            logger.info(f"Created output directory: {run_dir}")
            
            # Copy original files
            shutil.copy2(whatsapp_path, original_chats_dir / whatsapp_path.name)
            
            if instagram_path and instagram_path.exists():
                safe_person_name = person_name.replace(" ", "_").replace(".", "")
                new_filename = f"Instagram_Chat_with_{safe_person_name}.json"
                shutil.copy2(instagram_path, original_chats_dir / new_filename)
            
            # --- Ingestion ---
            logger.info("Starting Data Ingestion...")
            all_messages = []
            
            # Parse WhatsApp
            if whatsapp_path.exists():
                logger.info(f"Parsing WhatsApp: {whatsapp_path}")
                wa_msgs = parse_whatsapp(whatsapp_path)
                all_messages.extend(wa_msgs)
                logger.info(f"Parsed {len(wa_msgs)} WhatsApp messages")
            
            # Parse Instagram
            if instagram_path and instagram_path.exists():
                logger.info(f"Parsing Instagram: {instagram_path}")
                ig_msgs = parse_instagram(instagram_path)
                all_messages.extend(ig_msgs)
                logger.info(f"Parsed {len(ig_msgs)} Instagram messages")
            
            if not all_messages:
                raise HTTPException(
                    status_code=400,
                    detail="No messages found in the uploaded files. Please check the file format."
                )
            
            # Sort messages by timestamp
            all_messages.sort(key=lambda x: x.timestamp)
            logger.info(f"Total messages loaded: {len(all_messages)}")
            
            # Convert to optimized format
            logger.info("Converting to optimized format...")
            optimized_data = convert_to_optimized_format(all_messages)
            
            # Save optimized JSON
            processed_data_path = processed_data_dir / f"processed_{chat_slug}.json"
            saved_paths = save_optimized_json(optimized_data, processed_data_path)
            for path in saved_paths:
                logger.info(f"Saved optimized chunk: {path}")
            
            # Save system instruction prompt
            system_instruction = get_analysis_system_instruction()
            prompt_file = prompts_dir / "system_instruction.txt"
            with open(prompt_file, "w", encoding="utf-8") as f:
                f.write(system_instruction)
            logger.info(f"Saved system instruction to: {prompt_file}")
            
            # --- Compression (if enabled) ---
            if enable_compression:
                logger.info("Compression enabled - creating compressed version...")
                compressed_data_dir = run_dir / "compressed_data"
                compressed_data_dir.mkdir(exist_ok=True)
                
                compressed_file_path = compressed_data_dir / f"compressed_{chat_slug}.txt"
                compress_messages(all_messages, compressed_file_path)
                logger.info(f"Saved compressed chat to: {compressed_file_path}")
            
            # --- Create Zip File ---
            logger.info("Creating zip file...")
            zip_buffer = BytesIO()
            
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                # Add all files from run_dir
                for file_path in run_dir.rglob('*'):
                    if file_path.is_file():
                        arcname = file_path.relative_to(run_dir)
                        zip_file.write(file_path, arcname)
                        logger.info(f"Added to zip: {arcname}")
            
            zip_buffer.seek(0)
            
            # Generate download filename
            download_filename = f"{timestamp}__{chat_slug}.zip"
            
            logger.info(f"Zip file created successfully: {download_filename}")
            
            return StreamingResponse(
                zip_buffer,
                media_type="application/zip",
                headers={
                    "Content-Disposition": f"attachment; filename={download_filename}"
                }
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error processing files: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Error processing files: {str(e)}"
            )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
