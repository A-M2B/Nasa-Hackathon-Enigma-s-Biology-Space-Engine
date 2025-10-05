import re
from typing import Optional, Dict, Any
import json
from datetime import datetime

def extract_pmc_id(url: str) -> Optional[str]:
    """
    Extrait le PMC ID d'une URL
    
    Examples:
        >>> extract_pmc_id("https://pmc.ncbi.nlm.nih.gov/articles/PMC11930778/")
        'PMC11930778'
    """
    match = re.search(r'PMC(\d+)', url)
    if match:
        return f"PMC{match.group(1)}"
    return None

def sanitize_text(text: str) -> str:
    """
    Nettoie le texte en enlevant caractères spéciaux, espaces multiples, etc.
    """
    if not text:
        return ""
    
    # Enlève les caractères de contrôle
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
    
    # Remplace espaces multiples par un seul
    text = re.sub(r'\s+', ' ', text)
    
    # Trim
    text = text.strip()
    
    return text

def safe_json_serialize(obj: Any) -> str:
    """
    Sérialise un objet en JSON en gérant les types problématiques
    """
    def default_handler(o):
        if isinstance(o, datetime):
            return o.isoformat()
        elif isinstance(o, set):
            return list(o)
        elif hasattr(o, '__dict__'):
            return o.__dict__
        return str(o)
    
    return json.dumps(obj, default=default_handler, ensure_ascii=False)

def truncate_text(text: str, max_length: int = 1000) -> str:
    """
    Tronque le texte à une longueur maximale
    """
    if not text or len(text) <= max_length:
        return text
    
    return text[:max_length] + "..."

def validate_pmc_url(url: str) -> bool:
    """
    Valide qu'une URL est bien une URL PMC valide
    """
    pattern = r'^https?://pmc\.ncbi\.nlm\.nih\.gov/articles/PMC\d+/?$'
    return bool(re.match(pattern, url))

def format_duration(seconds: float) -> str:
    """
    Formate une durée en secondes en format lisible
    
    Examples:
        >>> format_duration(125)
        '2m 5s'
        >>> format_duration(3665)
        '1h 1m 5s'
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    
    if minutes < 60:
        return f"{minutes}m {secs}s"
    
    hours = minutes // 60
    minutes = minutes % 60
    
    return f"{hours}h {minutes}m {secs}s"

def chunk_list(lst: list, chunk_size: int) -> list:
    """
    Divise une liste en chunks de taille spécifiée
    
    Examples:
        >>> chunk_list([1, 2, 3, 4, 5], 2)
        [[1, 2], [3, 4], [5]]
    """
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]