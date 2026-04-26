import os
import sys
import django

# Setup django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from services.gemini_service import GeminiService
from services.anthropic_service import AnthropicService
from services.huggingface_gen_service import HuggingFaceGenService

try:
    from services.openai_service import OpenAIService
except ImportError:
    OpenAIService = None

def test_gemini():
    try:
        service = GeminiService()
        if not service.api_key:
            return False, "No API Key"
        res = service._call("Say exactly 'test ok' and nothing else.", temperature=0.1, json_mode=False)
        return bool(res and 'test ok' in res.lower()), str(res)
    except Exception as e:
        return False, str(e)

def test_anthropic():
    try:
        service = AnthropicService()
        if not service.api_key:
            return False, "No API Key"
        res = service._call("Respond with a JSON object containing the key 'status' and value 'ok'.", temperature=0.1)
        return bool(res and res.get('status') == 'ok'), str(res)
    except Exception as e:
        return False, str(e)

def test_huggingface():
    try:
        service = HuggingFaceGenService()
        if not service.api_key:
            return False, "No API Key"
        res = service._call("Respond with a JSON object containing the key 'status' and value 'ok'.")
        return bool(res and 'status' in res), str(res)
    except Exception as e:
        return False, str(e)

def test_openai():
    if not OpenAIService:
        return False, "OpenAIService module not found"
    try:
        service = OpenAIService()
        if not service.api_key:
            return False, "No API Key"
        res = service._call("Respond with a JSON object containing the key 'status' and value 'ok'.", temperature=0.1)
        return bool(res and res.get('status') == 'ok'), str(res)
    except Exception as e:
        return False, str(e)

print("--- API Key Tests ---")
gem_ok, gem_res = test_gemini()
print(f"Gemini: {'OK' if gem_ok else 'FAILED'} (Response/Error: {gem_res})")

ant_ok, ant_res = test_anthropic()
print(f"Anthropic: {'OK' if ant_ok else 'FAILED'} (Response/Error: {ant_res})")

hf_ok, hf_res = test_huggingface()
print(f"HuggingFace: {'OK' if hf_ok else 'FAILED'} (Response/Error: {hf_res})")

oai_ok, oai_res = test_openai()
print(f"OpenAI: {'OK' if oai_ok else 'FAILED'} (Response/Error: {oai_res})")
