import re
import time
from dataclasses import dataclass

from .audio import MAX_OUTPUT_BYTES, pcm_frames


class UpstreamError(Exception):
    def __init__(self, stage: str, detail: str = ''):
        super().__init__('upstream failure')  # Never retain raw provider errors in public exception text.
        self.stage = stage if stage in ('stt', 'llm', 'search', 'tts') else 'llm'


@dataclass
class Answer:
    text: str
    sources: list[dict[str, str]]


def spoken_text(text: str) -> str:
    text = re.sub(r'\[([^\]]+)\]\(https?://[^)]+\)', r'\1', text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'[*#_`>|~]', '', text)
    return text.strip()


async def run_turn(backend, audio: bytes, private: bool):
    timings = {}
    before = time.monotonic()
    transcript = (await backend.transcribe(audio)).strip()
    timings['stt_ms'] = round((time.monotonic() - before) * 1000)
    if not transcript:
        return None
    if len(transcript) > 4000:
        raise UpstreamError('stt')
    before = time.monotonic()
    answer = await backend.reply(transcript, private)
    answer.text = spoken_text(answer.text)
    if not answer.text or len(answer.text) > 1000:
        raise UpstreamError('llm')
    timings['llm_ms'] = round((time.monotonic() - before) * 1000)
    before = time.monotonic()
    speech = await backend.synthesize(answer.text)
    if len(speech) > MAX_OUTPUT_BYTES:
        raise UpstreamError('tts')
    try:
        pcm_frames(speech, max_seconds=47)
    except ValueError as error:
        raise UpstreamError('tts') from error
    timings['tts_ms'] = round((time.monotonic() - before) * 1000)
    return transcript, answer, speech, timings
