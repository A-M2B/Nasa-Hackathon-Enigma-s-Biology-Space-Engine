#!/usr/bin/env python3
"""
Test script to verify the fetch_article method of PMCAPIClient
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent))

from clients.pmc_client import PMCAPIClient
from config import config

async def test_fetch_article():
    """
    Test the fetch_article method with PMC4136787
    """
    print("🧪 Testing PMC API Client fetch_article method...")
    
    # Use email from config or default to test email
    email = config.pmc.email or "test@example.com"
    api_key = config.pmc.api_key
    
    print(f"📧 Using email: {email}")
    if api_key:
        print("🔑 Using API key")
    else:
        print("⚠️ No API key provided (this is fine, but rate limits will apply)")
    
    async with PMCAPIClient(email=email, api_key=api_key) as client:
        try:
            pmc_id = "PMC5018776"  # ID from the bottom of pmc_client.py
            print(f"📥 Fetching article: {pmc_id}")
            
            article = await client.fetch_article(pmc_id)
            
            print(f"✅ Successfully fetched article: {pmc_id}")
            print(f"📊 Article keys: {list(article.keys())}")
            
            # Print metadata if available
            if 'metadata' in article:
                metadata = article['metadata']
                print(f"📋 Title: {metadata.get('title', 'N/A')[:100]}...")
                print(f"📝 Abstract: {metadata.get('abstract', 'N/A')[:200]}...")
                print(f"📅 Publication date: {metadata.get('publication_date', 'N/A')}")
                print(f"📚 Journal: {metadata.get('journal', 'N/A')}")
                print(f"👥 Authors: {len(metadata.get('authors', []))} found")
            
            # Print sections info
            if 'sections' in article:
                print(f"📖 Sections: {list(article['sections'].keys())}")
                print(f"🏷️  Metadata: {list(article['metadata'].keys())}")
            
            return article
            
        except Exception as e:
            print(f"❌ Error fetching article {pmc_id}: {e}")
            import traceback
            traceback.print_exc()
            return None

if __name__ == "__main__":
    article = asyncio.run(test_fetch_article())
    
    if article:
        print("\n🎉 Test completed successfully!")
    else:
        print("\n💥 Test failed!")
        sys.exit(1)