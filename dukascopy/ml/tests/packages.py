import os
import sys
import time
import site
from datetime import datetime, timedelta

def get_deep_scan_packages(days=14):
    """
    Scans every available Python path for recently modified metadata.
    """
    # Calculate the time horizon
    horizon = time.time() - (days * 24 * 60 * 60)
    found_any = False

    # Collect all potential paths where packages live
    # sys.path includes the current venv, user site-packages, and system libs
    search_paths = sys.path

    print(f"📡 [Space]: Deep Scan initiated. Horizon: {days} days.")
    print(f"🌌 [Space]: Searching across {len(search_paths)} trajectory paths...")
    print("-" * 65)

    seen_folders = set()
    results = []

    for path in search_paths:
        if not os.path.isdir(path):
            continue
            
        # Avoid scanning the current project directory to reduce noise
        if os.getcwd() in path and "site-packages" not in path:
            continue

        try:
            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                
                # Metadata folders (.dist-info or .egg-info) are the ground truth for installs
                if item.endswith(".dist-info") or item.endswith(".egg-info"):
                    if item_path in seen_folders:
                        continue
                    
                    mtime = os.path.getmtime(item_path)
                    if mtime > horizon:
                        pkg_name = item.replace(".dist-info", "").replace(".egg-info", "")
                        install_date = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
                        results.append((pkg_name, install_date, path))
                        seen_folders.add(item_path)
        except PermissionError:
            continue

    # Sort by date (newest first)
    results.sort(key=lambda x: x[1], reverse=True)

    if not results:
        print("Empty Void: Still nothing. Are you sure the installs weren't cached?")
    else:
        for pkg, date, loc in results:
            # Highlight if it's in a Virtual Env
            env_tag = "[VENV]" if "venv" in loc.lower() or ".env" in loc.lower() else "[SYS] "
            print(f"{env_tag} {pkg:<30} | {date}")
            found_any = True

    print("-" * 65)
    if found_any:
        print("⚠️ [Warning]: Environment drift detected. Baseline integrity may be compromised.")

if __name__ == "__main__":
    # Scanning back 14 days to be safe
    get_deep_scan_packages(days=14)