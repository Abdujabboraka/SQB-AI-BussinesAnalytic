"""
HuggingFace Inference API service.
Used for: OSM amenity zero-shot classification (Block C).
"""
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

try:
    from huggingface_hub import InferenceClient
    HF_AVAILABLE = True
except ImportError:
    HF_AVAILABLE = False
    logger.warning("huggingface_hub not installed.")

MCC_LABELS = [
    'restaurant or cafe',
    'grocery store or supermarket',
    'pharmacy or drugstore',
    'clothing or fashion store',
    'hotel or accommodation',
    'auto parts store',
    'hardware or construction store',
    'medical clinic or healthcare',
    'beauty salon or barber shop',
    'general retail shop',
]

MCC_LABEL_MAP = {
    'restaurant or cafe': '5812',
    'grocery store or supermarket': '5411',
    'pharmacy or drugstore': '5912',
    'clothing or fashion store': '5661',
    'hotel or accommodation': '7011',
    'auto parts store': '5571',
    'hardware or construction store': '5251',
    'medical clinic or healthcare': '8099',
    'beauty salon or barber shop': '7299',
    'general retail shop': '5999',
}


class HuggingFaceService:
    def __init__(self):
        self.token = settings.HUGGINGFACE_API_TOKEN
        self.client = None
        if HF_AVAILABLE and self.token:
            self.client = InferenceClient(token=self.token)

    def classify_amenity(self, amenity_name: str, amenity_type: str = '') -> str:
        """
        Classify an OSM amenity into an MCC code using zero-shot classification.
        Falls back to keyword matching if HF API is unavailable.
        """
        text = f"{amenity_name} {amenity_type}".strip()
        if self.client:
            try:
                result = self.client.zero_shot_classification(
                    text=text,
                    candidate_labels=MCC_LABELS,
                    model='facebook/bart-large-mnli',
                )
                if result:
                    top = result[0]
                    top_label = getattr(top, 'label', None)
                    top_score = float(getattr(top, 'score', 0.0) or 0.0)
                    if isinstance(top, dict):
                        top_label = top_label or top.get('label')
                        top_score = float(top.get('score', top_score) or 0.0)
                    # Keep keyword fallback when model confidence is weak.
                    if top_label and top_score >= 0.45:
                        return MCC_LABEL_MAP.get(top_label, '5999')
            except Exception as e:
                logger.error(f"HF classification failed: {e}")
        # Keyword fallback
        text_lower = text.lower()
        if any(w in text_lower for w in ['cafe', 'restaurant', 'osh', 'choyxona', 'fast']):
            return '5812'
        if any(w in text_lower for w in ['apteka', 'pharmacy', 'dorixona']):
            return '5912'
        if any(w in text_lower for w in ['supermarket', 'do\'kon', 'market', 'grocery']):
            return '5411'
        if any(w in text_lower for w in ['kiyim', 'fashion', 'clothes', 'boutique']):
            return '5661'
        if any(w in text_lower for w in ['sartarosh', 'beauty', 'salon', 'barber']):
            return '7299'
        return '5999'
