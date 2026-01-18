import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent

# Input Files
WHATSAPP_PATH = BASE_DIR / "WhatsApp Chat with Shivam Dwivedi.txt"
INSTAGRAM_PATH = BASE_DIR / "message_shivam.json"

# Output Directory
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True) # Ensure it exists

# API Keys Configuration
"""
NAMING CONVENTION FOR .env FILE:

The system supports multiple accounts, each having multiple API keys for rotation.
Use the following naming convention for environment variables in your .env file:

GEMINI_ACCOUNT_{ACCOUNT_ID}_KEY_{KEY_ID}

Where:
- {ACCOUNT_ID}: A unique identifier for the account (e.g., 1, 2, 3, "Personal").
- {KEY_ID}: A unique index for the key within that account (e.g., 1, 2, 3).

Examples:
    GEMINI_ACCOUNT_2_KEY_1=AIzaSy...
    GEMINI_ACCOUNT_2_KEY_2=AIzaSy...
    GEMINI_ACCOUNT_3_KEY_1=AIzaSy...

The `GEMINI_ACCOUNT_KEYS` list will be automatically populated as a list of lists:
[
    [Account_1_Key_1, Account_1_Key_2, ...],
    [Account_2_Key_1, Account_2_Key_2, ...],
    ...
]
"""
from dotenv import load_dotenv

# Load environment variables from .env file
# Assuming .env is in the same directory as config.py (src folder)
ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(ENV_PATH)

def load_gemini_keys():
    """Dynamically loads Gemini API keys from environment variables."""
    accounts = {}
    
    # Iterate over all environment variables
    for key, value in os.environ.items():
        if key.startswith("GEMINI_ACCOUNT_") and "_KEY_" in key:
            try:
                # Parse the key structure: GEMINI_ACCOUNT_{ACC_ID}_KEY_{KEY_ID}
                parts = key.split("_")
                # Expected format: ['GEMINI', 'ACCOUNT', '{ACC_ID}', 'KEY', '{KEY_ID}']
                if len(parts) >= 5:
                    acc_id = parts[2]
                    # We store keys in a set first to avoid duplicates if any, though dict keys are unique
                    if acc_id not in accounts:
                        accounts[acc_id] = []
                    accounts[acc_id].append((key, value))
            except Exception:
                continue
    
    # Sort accounts by ID (to ensure consistent order if IDs are numeric-like)
    # We attempt to sort by integer value if possible, else string
    sorted_acc_ids = sorted(accounts.keys(), key=lambda x: int(x) if x.isdigit() else x)
    
    final_keys = []
    for acc_id in sorted_acc_ids:
        # Sort keys within each account by the variable name (which includes the KEY_ID)
        # This checks the full string 'GEMINI_ACCOUNT_2_KEY_1', so it sorts by KEY_ID naturally
        sorted_account_keys = [val for _, val in sorted(accounts[acc_id], key=lambda x: x[0])]
        if sorted_account_keys:
            final_keys.append(sorted_account_keys)
            
    return final_keys

GEMINI_ACCOUNT_KEYS = load_gemini_keys()

if not GEMINI_ACCOUNT_KEYS:
    print("WARNING: No Gemini API keys found in .env file. Please check configuration.")

