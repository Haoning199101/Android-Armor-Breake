#!/usr/bin/env python3
"""
Android Armor Breaker - Python wrapper for the Bash script
Provides compatibility with ClawHub distribution while maintaining the full functionality
"""

import os
import sys
import subprocess
import signal
from pathlib import Path

def main():
    """Main entry point for the Python wrapper"""
    script_dir = Path(__file__).parent
    bash_script = script_dir / "android-armor-breaker.sh"
    
    # Check if Bash script exists
    if not bash_script.exists():
        print(f"Error: Bash script not found: {bash_script}", file=sys.stderr)
        print(f"Please ensure the skill was installed correctly.", file=sys.stderr)
        sys.exit(1)
    
    # Make sure Bash script is executable
    if not os.access(bash_script, os.X_OK):
        try:
            bash_script.chmod(0o755)
            print(f"Note: Made {bash_script.name} executable", file=sys.stderr)
        except Exception as e:
            print(f"Warning: Could not make {bash_script.name} executable: {e}", file=sys.stderr)
            # Continue anyway, might work with sh
    
    # Build command - pass all arguments
    cmd = [str(bash_script)] + sys.argv[1:]
    
    # Handle signals properly
    def signal_handler(sig, frame):
        print("\nInterrupted, terminating...", file=sys.stderr)
        sys.exit(1)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Execute the Bash script
    try:
        # Use sys.exit to propagate exit code
        sys.exit(subprocess.call(cmd))
    except FileNotFoundError:
        print(f"Error: Could not execute {bash_script.name}", file=sys.stderr)
        print(f"Please ensure you have bash installed.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error executing {bash_script.name}: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()