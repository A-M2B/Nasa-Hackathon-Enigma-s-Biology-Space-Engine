#!/usr/bin/env python3
"""
Test script to verify the updated AI client with Groq and Sentence Transformers
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent))

from clients.ai_client import AIEnricher
from config import config

async def test_ai_client():
    """
    Test the updated AIEnricher with Groq and Sentence Transformers
    """
    print("🧪 Testing updated AI Client with Groq and Sentence Transformers...")
    
    # Use API key from config
    groq_api_key = config.ai.groq_api_key
    
    if not groq_api_key:
        print("⚠️ No GROQ_API_KEY found in config. Please set it in your .env file.")
        print("Example: GROQ_API_KEY=your_actual_key_here")
        return False
    
    try:
        # Initialize AIEnricher with Groq and Sentence Transformers
        enricher = AIEnricher(groq_api_key=groq_api_key)
        print("✅ AIEnricher initialized successfully")
        
        # Test embedding generation
        test_texts = ["This is a test sentence for embedding.", "Another test sentence."]
        embeddings = await enricher.generate_embeddings(test_texts)
        print(f"✅ Embeddings generated successfully: {len(embeddings)} embeddings")
        print(f"✅ Embedding dimension: {len(embeddings[0]) if embeddings else 0}")
        
        # Mock article data for testing
        mock_article_data = {
            'metadata': {
                'title': 'Test Article on Space Biology',
                'abstract': 'This is a test abstract about space biology research.'
            },
            'sections': {
                'introduction': 'The introduction section of our test article discusses important research in space biology and microgravity effects on organisms.',
                'results': 'The results show significant findings related to organism adaptation in space environments.',
                'conclusion': 'The conclusion summarizes important implications for future space missions and biological research in microgravity conditions.'
            }
        }
        
        # Test structured info extraction (this might take a bit longer as it calls the LLM)
        print("⏳ Testing structured info extraction (calling Groq API)...")
        structured_info = await enricher.extract_structured_info(mock_article_data)
        print(f"✅ Structured info extracted: {list(structured_info.keys())}")
        
        print("\n🎉 All tests passed! AI client is working with Groq and Sentence Transformers.")
        return True
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_ai_client())
    
    if not success:
        print("\n💥 Test failed!")
        sys.exit(1)
    else:
        print("\n✅ Test completed successfully!")