import argparse
import time
from app import create_app
from app.jobs import monitor, tick

parser = argparse.ArgumentParser()
parser.add_argument("--once", action="store_true", help="Process queued jobs once, run monitoring, and exit")
args = parser.parse_args()
app = create_app()
with app.app_context():
    while True:
        processed = tick()
        monitor()
        if args.once:
            while processed:
                processed = tick()
            break
        time.sleep(2 if processed else 30)
