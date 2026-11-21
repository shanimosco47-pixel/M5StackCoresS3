"""Validate actual PCM frames instead of assuming every WAV has a 44-byte header."""
import array
import io
import math
import sys
import wave

MAX_INPUT_BYTES = 1_000_000
MAX_OUTPUT_BYTES = 1_500_000


def pcm_frames(body: bytes, max_seconds: float = 30) -> bytes:
    try:
        with wave.open(io.BytesIO(body), 'rb') as wav:
            if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getcomptype()) != (1, 2, 16000, 'NONE'):
                raise ValueError('expected 16kHz mono PCM16')
            count = wav.getnframes()
            if not 0 < count <= int(16000 * max_seconds):
                raise ValueError('invalid duration')
            data = wav.readframes(count)
            if len(data) != count * 2:
                raise ValueError('truncated frames')
            return data
    except (wave.Error, EOFError) as error:
        raise ValueError('invalid WAV') from error


def too_quiet_or_short(frames: bytes) -> bool:
    if len(frames) < 16000:  # 0.5 seconds, 16kHz, 2 bytes per sample
        return True
    samples = array.array('h', frames)
    if sys.byteorder != 'little':
        samples.byteswap()
    rms = math.sqrt(sum(value * value for value in samples) / len(samples))
    return rms < 80
