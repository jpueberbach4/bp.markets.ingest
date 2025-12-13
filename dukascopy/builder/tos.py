#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        tos.py
 Author:      JP Ueberbach
 Created:     2025-12-13
 Description: Module to enforce acceptance of Terms of Service (TOS) for the 
              Dukascopy data extraction tool.

              This module provides a single function, `require_tos_acceptance`, 
              which prompts the user to accept the TOS on first execution and 
              caches the acceptance in a local file. Subsequent runs skip the 
              prompt if acceptance has already been recorded.

 Requirements:
     - Python 3.8+

 License:
     MIT License
===============================================================================
"""
import sys
from pathlib import Path

def require_tos_acceptance():
    """
    Prompt the user to accept the Terms of Service (TOS) before using the tool.

    Behavior:
        - If the acceptance file exists, returns True immediately.
        - Otherwise, displays TOS and loops until a valid response is received.
        - Accepting TOS writes a marker file to cache.
        - Rejecting TOS exits the script with a non-zero status code.

    Returns:
        bool: True if TOS accepted.

    Side Effects:
        - Creates "cache/HAS_ACCEPTED_TERMS_OF_SERVICE" on acceptance.
        - Exits the program on denial.
    """

    # Check if user already accepted TOS
    if Path("cache/HAS_ACCEPTED_TERMS_OF_SERVICE").exists():
        return True

    # Display Terms of Service
    print("\n" + "=" * 70)
    print("🚀 TERMS OF SERVICE")
    print("=" * 70)
    print("""
1. This tool provides access to Dukascopy Bank SA's historical data.
2. Data is for PERSONAL, NON-COMMERCIAL research/analysis ONLY.
3. REDISTRIBUTION IN ANY FORM IS STRICTLY PROHIBITED.
4. You accept full liability for your usage.
5. Dukascopy's own Terms of Service apply.
6. THE TOOL AND DATA ARE PROVIDED 'AS IS' WITHOUT ANY WARRANTIES, 
   EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO WARRANTIES OF 
   MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, OR ACCURACY.
    
By using this tool, you accept these terms.
    """)

    # Loop until a valid input is received
    while True:
        response = input("\nDo you accept the Terms of Service? (yes/no): ").strip().lower()

        if response in ['yes', 'y']:
            # User accepted TOS: record acceptance and continue
            print("\n✓ Terms accepted. Continuing with data extraction...")
            Path("cache").mkdir(parents=True, exist_ok=True)
            with open("cache/HAS_ACCEPTED_TERMS_OF_SERVICE", "w"):
                pass
            return True

        elif response in ['no', 'n']:
            # User declined TOS: exit the script
            print("\n✗ Terms were not accepted. Aborting.")
            sys.exit(1)

        else:
            # Invalid input, prompt again
            print("Invalid input. Please respond with 'yes' or 'no'.")
