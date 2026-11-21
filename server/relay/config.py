"""Server-owned settings. Requests cannot override providers, models or privacy."""
import os
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    device_secret: str = ''
    groq_key: str = ''
    openrouter_key: str = ''
    azure_key: str = ''
    azure_region: str = ''
    tavily_key: str = ''
    model: str = ''
    reasoning_effort: str = ''
    llm_provider: str = 'openrouter'
    llm_max_tokens: int = 300
    allowed_models: tuple[str, ...] = ()
    private_approved: bool = False
    private_search_approved: bool = False
    durable_quotas_required: bool = False
    require_zdr: bool = True
    voice: str = 'he-IL-HilaNeural'
    tts_provider: str = 'azure'
    google_project: str = ''
    requests_per_minute: int = 6
    requests_per_day: int = 100
    turn_timeout: float = 45

    @property
    def ready(self):
        tts_ready = (
            self.tts_provider == 'google'
            and bool(re.fullmatch(r'[a-z][a-z0-9-]{4,28}[a-z0-9]', self.google_project))
        ) or (
            self.tts_provider == 'azure' and bool(self.azure_key)
            and bool(re.fullmatch(r'[a-z][a-z0-9]{1,30}', self.azure_region))
            and bool(re.fullmatch(r'he-IL-[A-Za-z0-9]+', self.voice))
        )
        return (len(self.device_secret) >= 32
                and bool(self.groq_key) and tts_ready
                and (self.llm_provider == 'groq'
                     or (self.llm_provider == 'openrouter' and bool(self.openrouter_key)))
                and 64 <= self.llm_max_tokens <= 2048
                and self.model in self.allowed_models
                and (not self.durable_quotas_required
                     or bool(re.fullmatch(r'[a-z][a-z0-9-]{4,28}[a-z0-9]', self.google_project)))
                and self.reasoning_effort in ('', 'none', 'minimal', 'low', 'medium', 'high')
                and 0 < self.requests_per_minute <= 1000
                and 0 < self.requests_per_day <= 10000
                and 0 < self.turn_timeout <= 90)

    @classmethod
    def from_env(cls):
        return cls(
            device_secret=os.getenv('DEVICE_SECRET', ''),
            groq_key=os.getenv('GROQ_API_KEY', ''),
            openrouter_key=os.getenv('OPENROUTER_API_KEY', ''),
            azure_key=os.getenv('AZURE_SPEECH_KEY', ''),
            azure_region=os.getenv('AZURE_REGION', ''),
            tavily_key=os.getenv('TAVILY_API_KEY', ''),
            model=os.getenv('LLM_MODEL', ''),
            reasoning_effort=os.getenv('LLM_REASONING_EFFORT', ''),
            llm_provider=os.getenv('LLM_PROVIDER', 'openrouter'),
            llm_max_tokens=int(os.getenv('LLM_MAX_TOKENS', '300')),
            allowed_models=tuple(v.strip() for v in os.getenv('ALLOWED_MODELS', '').split(',') if v.strip()),
            private_approved=os.getenv('PRIVATE_PROVIDERS_APPROVED', '').lower() == 'true',
            private_search_approved=os.getenv('PRIVATE_SEARCH_APPROVED', '').lower() == 'true',
            durable_quotas_required=os.getenv('DURABLE_QUOTAS_REQUIRED', '').lower() == 'true',
            require_zdr=os.getenv('REQUIRE_ZDR', 'true').lower() == 'true',
            voice=os.getenv('TTS_VOICE', 'he-IL-HilaNeural'),
            tts_provider=os.getenv('TTS_PROVIDER', 'azure'),
            google_project=os.getenv('GOOGLE_CLOUD_PROJECT', ''),
            requests_per_minute=int(os.getenv('REQUESTS_PER_MINUTE', '6')),
            requests_per_day=int(os.getenv('REQUESTS_PER_DAY', '100')),
            turn_timeout=float(os.getenv('TURN_TIMEOUT_SECONDS', '45')),
        )
