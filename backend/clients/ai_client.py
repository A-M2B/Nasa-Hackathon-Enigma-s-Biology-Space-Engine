import asyncio
from typing import List, Dict
import json
from groq import AsyncGroq
from sentence_transformers import SentenceTransformer
from tenacity import retry, stop_after_attempt, wait_exponential
import numpy as np

class AIEnricher:
    """
    Client pour enrichissement IA des publications
    """
    
    def __init__(self, groq_api_key: str, embedding_model: str = "all-MiniLM-L6-v2"):
        self.groq_client = AsyncGroq(api_key=groq_api_key)
        # Initialize sentence transformer model for embeddings
        self.embedding_model = SentenceTransformer(embedding_model)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def extract_structured_info(self, article_data: Dict) -> Dict:
        """
        Extrait des informations structurées via LLM (Groq)
        """
        
        # Prépare le contenu pour l'IA
        content = self._prepare_content_for_llm(article_data)
        
        prompt = f"""
Analyse cette publication scientifique de bioscience spatiale NASA et extrais les informations suivantes au format JSON:

1. **hypothesis**: L'hypothèse principale testée (string)
2. **organisms**: Liste des organismes étudiés (array of strings)
3. **space_conditions**: Conditions spatiales testées (array of objects avec 'type' et 'value')
4. **key_findings**: 3-5 découvertes majeures (array of strings)
5. **implications**: Implications pour missions lunaires/martiennes (string)
6. **knowledge_gaps**: Questions non résolues (array of strings)
7. **entities**: Entités biologiques mentionnées - gènes, protéines, voies (array of objects avec 'name' et 'type')

Publication:
Titre: {article_data['metadata'].get('title', '')}
Abstract: {article_data['metadata'].get('abstract', '')}
{content}

Réponds UNIQUEMENT avec un objet JSON valide, sans markdown ni explications.
"""
        
        try:
            response = await self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",  # Using Llama 3 70B model for robust scientific text processing
                messages=[
                    {
                        "role": "system",
                        "content": "Vous êtes un expert en analyse de publications scientifiques. Répondez UNIQUEMENT avec un objet JSON valide, sans explications ni formatage markdown."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,  # Plus déterministe
                max_tokens=4000
            )
            
            # Extrait le JSON de la réponse
            response_text = response.choices[0].message.content
            
            # Nettoie la réponse (enlève les markdown code blocks si présents)
            response_text = response_text.strip()
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.startswith('```'):
                response_text = response_text[3:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            
            enriched_data = json.loads(response_text.strip())
            
            return enriched_data
            
        except json.JSONDecodeError as e:
            print(f"⚠️ Erreur de parsing JSON: {e}")
            # Retourne structure par défaut
            return self._get_default_enriched_data()
        
        except Exception as e:
            print(f"⚠️ Erreur d'enrichissement IA: {e}")
            return self._get_default_enriched_data()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Génère des embeddings avec Sentence Transformers
        """
        try:
            # Generate embeddings using SentenceTransformer
            embeddings = self.embedding_model.encode(texts, convert_to_numpy=True)
            
            # Convert numpy arrays to lists of floats
            if isinstance(embeddings, np.ndarray):
                embeddings_list = embeddings.tolist()
            else:
                # If it's already a list, ensure it's properly formatted
                embeddings_list = [[float(val) for val in embedding] for embedding in embeddings]
            
            return embeddings_list
            
        except Exception as e:
            print(f"⚠️ Erreur génération embeddings: {e}")
            # Determine embedding dimension from the model (default to common size if couldn't be determined)
            embedding_dim = len(self.embedding_model.encode(["test"])) if hasattr(self.embedding_model.encode(["test"]), '__len__') else 384
            # Return zero embeddings with appropriate dimensions in case of error
            return [[0.0] * embedding_dim for _ in texts]
    
    def _prepare_content_for_llm(self, article_data: Dict) -> str:
        """
        Prépare le contenu de l'article pour le LLM (limité en tokens)
        """
        content_parts = []
        
        # Sections importantes
        sections = article_data.get('sections', {})
        priority_sections = ['introduction', 'results', 'conclusion', 'discussion']
        
        for section_name in priority_sections:
            if section_name in sections:
                text = sections[section_name]
                # Limite à 500 premiers mots par section
                words = text.split()[:500]
                content_parts.append(f"{section_name.upper()}: {' '.join(words)}")
        
        return '\n\n'.join(content_parts)
    
    def _get_default_enriched_data(self) -> Dict:
        """
        Retourne une structure par défaut en cas d'erreur
        """
        return {
            'hypothesis': 'Not extracted',
            'organisms': [],
            'space_conditions': [],
            'key_findings': [],
            'implications': 'Not extracted',
            'knowledge_gaps': [],
            'entities': []
        }