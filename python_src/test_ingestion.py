import sys
from pathlib import Path
from pprint import pprint

# Add src to python path to allow imports
sys.path.append(str(Path(__file__).resolve().parent))

from config import WHATSAPP_PATH, INSTAGRAM_PATH
from parsers import parse_whatsapp, parse_instagram

def test_ingestion():
    print("Testing WhatsApp Ingestion...")
    if WHATSAPP_PATH.exists():
        wa_msgs = parse_whatsapp(WHATSAPP_PATH)
        print(f"Parsed {len(wa_msgs)} WhatsApp messages.")
        if wa_msgs:
            print("Sample WhatsApp Message:")
            pprint(wa_msgs[0].to_dict())
            print("Latest WhatsApp Message:")
            pprint(wa_msgs[-1].to_dict())
    else:
        print(f"WhatsApp file not found at {WHATSAPP_PATH}")

    print("\n" + "="*50 + "\n")

    print("Testing Instagram Ingestion...")
    if INSTAGRAM_PATH.exists():
        ig_msgs = parse_instagram(INSTAGRAM_PATH)
        print(f"Parsed {len(ig_msgs)} Instagram messages.")
        if ig_msgs:
            print("Sample Instagram Message:")
            pprint(ig_msgs[0].to_dict())
            print("Latest Instagram Message:")
            pprint(ig_msgs[-1].to_dict())
    else:
        print(f"Instagram file not found at {INSTAGRAM_PATH}")

if __name__ == "__main__":
    test_ingestion()
