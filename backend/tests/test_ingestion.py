import pytest
import asyncio
from clients.pmc_client import PMCAPIClient
from utils.helpers import extract_pmc_id, validate_pmc_url

@pytest.mark.asyncio
async def test_pmc_client_fetch():
    """Test de récupération d'un article PMC"""
    async with PMCAPIClient(email="test@example.com") as client:
        article = await client.fetch_article("PMC11930778")
        
        assert article is not None
        assert 'pmc_id' in article
        assert article['pmc_id'] == 'PMC11930778'
        assert 'metadata' in article
        assert 'sections' in article

def test_extract_pmc_id():
    """Test d'extraction de PMC ID"""
    url1 = "https://pmc.ncbi.nlm.nih.gov/articles/PMC11930778/"
    assert extract_pmc_id(url1) == "PMC11930778"
    
    url2 = "https://pmc.ncbi.nlm.nih.gov/articles/PMC123/"
    assert extract_pmc_id(url2) == "PMC123"
    
    invalid_url = "https://example.com/article"
    assert extract_pmc_id(invalid_url) is None

def test_validate_pmc_url():
    """Test de validation d'URL PMC"""
    valid_url = "https://pmc.ncbi.nlm.nih.gov/articles/PMC11930778/"
    assert validate_pmc_url(valid_url) is True
    
    invalid_url = "https://example.com/PMC123"
    assert validate_pmc_url(invalid_url) is False

if __name__ == "__main__":
    pytest.main([__file__, "-v"])