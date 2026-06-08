import sys
import os

# Redirect to SRC/STC.py
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "SRC"))
from STC import main

if __name__ == "__main__":
    main()
