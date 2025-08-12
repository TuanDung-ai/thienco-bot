
import time
import sys

def log(*args):
    print(*args, file=sys.stdout, flush=True)

def log_error(*args):
    print(*args, file=sys.stderr, flush=True)

class Timer:
    def __init__(self):
        self.start = time.time()
    def stop_ms(self) -> int:
        return int((time.time() - self.start) * 1000)
