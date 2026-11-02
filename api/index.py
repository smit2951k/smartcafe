import os
import sys

# Ensure root directory is on the python search path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from app import app

# Expose app for Vercel Serverless Function
if __name__ == "__main__":
    app.run()

