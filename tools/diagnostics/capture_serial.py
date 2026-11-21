import argparse
import pathlib
import re
import sys
import time

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

root = pathlib.Path(__file__).parent
sys.path.insert(0, str(root / 'pydeps'))
import serial

p = argparse.ArgumentParser()
p.add_argument('--port', default='COM5')
p.add_argument('--seconds', type=float, default=30)
p.add_argument('--output', required=True)
a = p.parse_args()
out = pathlib.Path(a.output)
if out.exists():
    raise SystemExit('Output exists; refusing to overwrite')

def redact(s):
    s = re.sub(r'\x1b\[[0-9;]*m', '', s)
    s = re.sub(r'(WiFi Password:|OpenAI Key:)[^\r\n]*', r'\1 [REDACTED]', s, flags=re.I)
    s = re.sub(r'sk-[A-Za-z0-9_-]{12,}', '[REDACTED_API_KEY]', s)
    return s

with serial.Serial() as ser, out.open('x', encoding='utf-8') as f:
    ser.port = a.port
    ser.baudrate = 115200
    ser.timeout = 0.2
    ser.dtr = False
    ser.rts = False
    ser.open()
    end = time.monotonic() + a.seconds
    pending = ''
    while time.monotonic() < end:
        data = ser.read(4096)
        if not data:
            continue
        pending += data.decode('utf-8', errors='replace')
        lines = pending.split('\n')
        pending = lines.pop()
        for line in lines:
            clean = redact(line) + '\n'
            f.write(clean)
            f.flush()
            print(clean, end='', flush=True)
    if pending:
        f.write(redact(pending))
