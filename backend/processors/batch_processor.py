import asyncio
from typing import List, Dict
import json
from tqdm.asyncio import tqdm_asyncio
from datetime import datetime

from clients.pmc_client import PMCAPIClient
from clients.ai_client import AIEnricher
from processors.knowledge_graph import KnowledgeGraphBuilder
from database.weaviate_schema import get_weaviate_client
import asyncpg
from elasticsearch import AsyncElasticsearch
import weaviate

class PMCBatchProcessor:
    """
    Traite les 608 articles PMC en batch
    """
    
    def __init__(self, config):
        self.config = config
        
        # Clients
        self.pmc_client = None
        self.ai_enricher = AIEnricher(
            groq_api_key=config.ai.groq_api_key,
            embedding_model=config.ai.embedding_model
        )
        self.kg_builder = KnowledgeGraphBuilder(
            uri=config.neo4j.uri,
            user=config.neo4j.user,
            password=config.neo4j.password
        )
        
        # Configuration bases de données
        self.postgres_pool = None
        self.es_client = None
        self.weaviate_client = None
        
        # Statistiques
        self.stats = {
            'total': 0,
            'success': 0,
            'errors': 0,
            'skipped': 0,
            'start_time': None,
            'end_time': None
        }
    
    async def initialize(self):
        """Initialise tous les services"""
        print("🔧 Initialisation des services...")
        
        # PMC Client
        self.pmc_client = PMCAPIClient(
            email=self.config.pmc.email,
            api_key=self.config.pmc.api_key
        )
        await self.pmc_client.__aenter__()
        print("✅ PMC API client initialisé")
        
        # PostgreSQL
        try:
            self.postgres_pool = await asyncpg.create_pool(
                host=self.config.postgres.host,
                port=self.config.postgres.port,
                user=self.config.postgres.user,
                password=self.config.postgres.password,
                database=self.config.postgres.database,
                min_size=5,
                max_size=20
            )
            print("✅ PostgreSQL pool initialisé")
        except Exception as e:
            print(f"❌ Erreur PostgreSQL: {e}")
            raise
        
        # Elasticsearch
        try:
            # Utiliser les paramètres de compatibilité Elasticsearch 8+
            self.es_client = AsyncElasticsearch(
                hosts=[self.config.elasticsearch.url],
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/vnd.elasticsearch+json; compatible-with=8"
                },
                basic_auth=("elastic", "changeme"),  # Mot de passe par défaut
                verify_certs=False,
                ssl_show_warn=False
            )
            
            # Essayons d'abord une vérification simple via HTTP
            import requests
            response = requests.get(self.config.elasticsearch.url)
            if response.status_code == 200:
                print("✅ Elasticsearch accessible via HTTP")
                
                # Crée l'index s'il n'existe pas
                if not await self.es_client.indices.exists(index='publications'):
                    await self.es_client.indices.create(
                        index='publications',
                        mappings={
                            "properties": {
                                "pmc_id": {"type": "keyword"},
                                "title": {"type": "text"},
                                "abstract": {"type": "text"},
                                "full_text": {"type": "text"},
                                "keywords": {"type": "keyword"},
                                "publication_date": {"type": "date", "format": "yyyy-MM-dd||yyyy-MM||yyyy"}
                            }
                        }
                    )
                print("✅ Elasticsearch client initialisé et index créé")
            else:
                print(f"⚠️ Elasticsearch HTTP status: {response.status_code}, tentative directe...")
                # Si la vérification HTTP échoue, on tente directement avec le client
                if not await self.es_client.indices.exists(index='publications'):
                    await self.es_client.indices.create(
                        index='publications',
                        mappings={
                            "properties": {
                                "pmc_id": {"type": "keyword"},
                                "title": {"type": "text"},
                                "abstract": {"type": "text"},
                                "full_text": {"type": "text"},
                                "keywords": {"type": "keyword"},
                                "publication_date": {"type": "date", "format": "yyyy-MM-dd||yyyy-MM||yyyy"}
                            }
                        }
                    )
                print("✅ Elasticsearch client initialisé")
        except Exception as e:
            print(f"❌ Erreur Elasticsearch: {e}")
            # Si Elasticsearch ne fonctionne pas, on continue sans (optionnel)
            print("⚠️ Elasticsearch indisponible - le traitement continuera sans recherche Elasticsearch")
            self.es_client = None
        
        # Weaviate
        try:
            self.weaviate_client = get_weaviate_client(self.config)
            
            # Crée le schéma
            from database.weaviate_schema import create_weaviate_schema
            create_weaviate_schema(self.weaviate_client)
            print("✅ Weaviate client initialisé")
        except Exception as e:
            print(f"❌ Erreur Weaviate: {e}")
            raise
        
        print("🎉 Tous les services sont prêts !\n")
    
    async def cleanup(self):
        """Nettoie les ressources"""
        print("\n🧹 Nettoyage des ressources...")
        
        if self.pmc_client:
            await self.pmc_client.close()
        
        if self.postgres_pool:
            await self.postgres_pool.close()
        
        if self.es_client:
            await self.es_client.close()
        
        if self.kg_builder:
            await self.kg_builder.close()
        
        print("✅ Nettoyage terminé")
    
    async def process_all_articles(self, pmc_urls: List[str], batch_size: int = 10):
        """
        Pipeline complet pour tous les articles
        """
        self.stats['total'] = len(pmc_urls)
        self.stats['start_time'] = datetime.now()
        
        print(f"🚀 Démarrage du traitement de {len(pmc_urls)} articles...")
        print(f"📦 Taille des batchs: {batch_size}\n")
        
        # Charge les articles déjà traités
        processed_ids = await self._get_processed_ids()
        print(f"📊 {len(processed_ids)} articles déjà traités\n")
        
        # Filtre les URLs déjà traitées
        urls_to_process = []
        for url in pmc_urls:
            pmc_id = self._extract_pmc_id(url)
            if pmc_id not in processed_ids:
                urls_to_process.append(url)
            else:
                self.stats['skipped'] += 1
        
        print(f"📋 {len(urls_to_process)} articles à traiter\n")
        
        # Traite par batches
        for i in range(0, len(urls_to_process), batch_size):
            batch = urls_to_process[i:i+batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(urls_to_process) + batch_size - 1) // batch_size
            
            print(f"\n{'='*60}")
            print(f"📦 Batch {batch_num}/{total_batches}")
            print(f"{'='*60}")
            
            # Traite le batch en parallèle avec barre de progression
            tasks = [self.process_single_article(url) for url in batch]
            # Utilise asyncio.gather avec return_exceptions pour gérer les erreurs
            raw_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Traite les résultats avec tqdm pour la barre de progression
            for j, result in enumerate(raw_results):
                if isinstance(result, Exception):
                    print(f"❌ Erreur: {batch[j]} - {result}")
                    self.stats['errors'] += 1
                elif result and result.get('status') == 'success':
                    self.stats['success'] += 1
                else:
                    if result and result.get('status') == 'skipped':
                        self.stats['skipped'] += 1
            
            # Pause pour respecter les rate limits
            await asyncio.sleep(1)
            
            # Affiche statistiques intermédiaires
            self._print_stats()
        
        self.stats['end_time'] = datetime.now()
        
        print("\n" + "="*60)
        print("🎉 TRAITEMENT TERMINÉ !")
        print("="*60)
        self._print_final_stats()
    
    async def process_single_article(self, pmc_url: str) -> Dict:
        """
        Pipeline complet pour un article
        """
        pmc_id = self._extract_pmc_id(pmc_url)
        
        try:
            # Marque comme "en cours"
            await self._update_processing_status(pmc_id, 'processing')
            
            # 1. EXTRACTION
            article_data = await self.pmc_client.fetch_article(pmc_id)
            
            # VÉRIFICATION : L'article a-t-il des sections significatives ?
            # Si l'article n'a pas de sections ou que toutes les sections sont vides, on l'ignore
            sections_available = 'sections' in article_data and article_data['sections'] and any(text.strip() for text in article_data['sections'].values())
            if not sections_available:
                print(f"⏭️ L'article {pmc_id} n'a pas de sections significatives, ignoré.")
                await self._update_processing_status(pmc_id, 'skipped_no_sections')  # Nouveau statut
                return {
                    'pmc_id': pmc_id,
                    'status': 'skipped',
                    'reason': 'no_sections'
                }
            
            # 2. ENRICHISSEMENT IA
            enriched_data = await self.ai_enricher.extract_structured_info(article_data)
            
            # 3. GÉNÉRATION EMBEDDINGS
            full_text_embedding = await self.ai_enricher.generate_embeddings(
                [article_data['full_text'][:8000]]  # Limite pour éviter dépassement tokens
            )
            
            # Génère les embeddings par section
            section_embeddings = {}
            for section_name, section_text in article_data['sections'].items():
                if section_text:
                    emb = await self.ai_enricher.generate_embeddings([section_text[:8000]])
                    section_embeddings[section_name] = emb[0]
            
            # 4. STOCKAGE POSTGRES
            await self._store_in_postgres(pmc_id, article_data, enriched_data)
            
            # 5. STOCKAGE WEAVIATE
            await self._store_in_weaviate(
                pmc_id,
                article_data,
                enriched_data,
                full_text_embedding[0],
                section_embeddings
            )
            
            # 6. INDEXATION ELASTICSEARCH
            await self._index_in_elasticsearch(pmc_id, article_data)
            
            # 7. GRAPHE NEO4J
            await self.kg_builder.create_publication_node(article_data, enriched_data)
            
            # Marque comme "complété"
            await self._update_processing_status(pmc_id, 'completed')
            
            return {
                'pmc_id': pmc_id,
                'status': 'success',
                'metadata': article_data['metadata']
            }
            
        except Exception as e:
            print(f"❌ Erreur {pmc_id}: {str(e)}")
            await self._log_error(pmc_id, str(e), type(e).__name__)
            await self._update_processing_status(pmc_id, 'failed', str(e))
            raise
    
    def _extract_pmc_id(self, url: str) -> str:
        """Extrait PMC ID de l'URL"""
        import re
        match = re.search(r'PMC(\d+)', url)
        if match:
            return f"PMC{match.group(1)}"
        raise ValueError(f"Invalid PMC URL: {url}")
    
    async def _get_processed_ids(self) -> set:
        """Récupère les IDs déjà traités"""
        async with self.postgres_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT pmc_id FROM processing_status WHERE status = 'completed'"
            )
            return {row['pmc_id'] for row in rows}
    
    async def _update_processing_status(self, pmc_id: str, status: str, error: str = None):
        """Met à jour le statut de traitement"""
        async with self.postgres_pool.acquire() as conn:
            if status == 'processing':
                await conn.execute("""
                    INSERT INTO processing_status (pmc_id, status, started_at, attempts)
                    VALUES ($1, $2, NOW(), 1)
                    ON CONFLICT (pmc_id) 
                    DO UPDATE SET 
                        status = $2,
                        started_at = NOW(),
                        attempts = processing_status.attempts + 1
                """, pmc_id, status)
            
            elif status == 'completed':
                await conn.execute("""
                    UPDATE processing_status
                    SET status = $2, completed_at = NOW()
                    WHERE pmc_id = $1
                """, pmc_id, status)
            
            elif status == 'failed':
                await conn.execute("""
                    UPDATE processing_status
                    SET status = $2, last_error = $3
                    WHERE pmc_id = $1
                """, pmc_id, status, error)
    
    async def _store_in_postgres(self, pmc_id: str, article_data: Dict, enriched_data: Dict):
        """Stocke dans PostgreSQL"""
        query = """
        INSERT INTO publications (
            pmc_id, pmid, doi, title, abstract, journal, publication_date,
            authors, keywords, hypothesis, key_findings, organisms_studied,
            space_conditions, full_text, created_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, NOW())
        ON CONFLICT (pmc_id) DO UPDATE SET
            updated_at = NOW(),
            title = EXCLUDED.title,
            abstract = EXCLUDED.abstract,
            full_text = EXCLUDED.full_text
        """
        
        async with self.postgres_pool.acquire() as conn:
            await conn.execute(
                query,
                pmc_id,
                article_data['metadata'].get('pmid'),
                article_data['metadata'].get('doi'),
                article_data['metadata'].get('title'),
                article_data['metadata'].get('abstract'),
                article_data['metadata'].get('journal'),
                article_data['metadata'].get('publication_date'),
                json.dumps(article_data['metadata'].get('authors', [])),
                json.dumps(article_data['metadata'].get('keywords', [])),
                enriched_data.get('hypothesis'),
                json.dumps(enriched_data.get('key_findings', [])),
                json.dumps(enriched_data.get('organisms', [])),
                json.dumps(enriched_data.get('space_conditions', [])),
                article_data['full_text']
            )
    
    async def _store_in_weaviate(
        self,
        pmc_id: str,
        article_data: Dict,
        enriched_data: Dict,
        full_text_embedding: List[float],
        section_embeddings: Dict
    ):
        """Stocke dans Weaviate (API moderne corrigée)"""

        # 1. Insertion de l'article principal
        publication_collection = self.weaviate_client.collections.get("Publication")
        publication_collection.data.insert({
            "pmcId": pmc_id,
            "title": article_data['metadata'].get('title', ''),
            "abstract": article_data['metadata'].get('abstract', ''),
            "fullText": article_data['full_text'][:50000],  # Limite Weaviate
            "publicationDate": article_data['metadata'].get('publication_date', ''),
            "organisms": enriched_data.get('organisms', []),
            "keywords": article_data['metadata'].get('keywords', []),
            "journal": article_data['metadata'].get('journal', '')
        }, vector=full_text_embedding)

        # 2. Insertion des sections (si disponibles)
        if 'sections' in article_data and article_data['sections'] and section_embeddings:
            section_collection = self.weaviate_client.collections.get("PublicationSection")
            for section_name, section_embedding in section_embeddings.items():
                if section_name in article_data['sections']:
                    section_text = article_data['sections'][section_name]
                    if section_text:
                        section_collection.data.insert({
                            "pmcId": pmc_id,
                            "sectionName": section_name,
                            "sectionText": section_text[:50000],
                            "parentTitle": article_data['metadata'].get('title', '')
                        }, vector=section_embedding)
    
    async def _index_in_elasticsearch(self, pmc_id: str, article_data: Dict):
        """Indexe dans Elasticsearch"""
        if self.es_client is None:
            # Elasticsearch n'est pas disponible, on saute l'indexation
            return
        
        doc = {
            'pmc_id': pmc_id,
            'title': article_data['metadata'].get('title'),
            'abstract': article_data['metadata'].get('abstract'),
            'full_text': article_data['full_text'],
            'authors': [
                f"{a.get('first_name', '')} {a.get('last_name', '')}".strip()
                for a in article_data['metadata'].get('authors', [])
            ],
            'keywords': article_data['metadata'].get('keywords', []),
            'journal': article_data['metadata'].get('journal'),
            'publication_date': article_data['metadata'].get('publication_date'),
            'sections': article_data['sections']
        }
        
        await self.es_client.index(
            index='publications',
            id=pmc_id,
            document=doc
        )
    
    async def _log_error(self, pmc_id: str, error_message: str, error_type: str):
        """Log les erreurs"""
        async with self.postgres_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO processing_errors (pmc_id, error_message, error_type, timestamp)
                VALUES ($1, $2, $3, NOW())
            """, pmc_id, error_message, error_type)
    
    def _print_stats(self):
        """Affiche statistiques intermédiaires"""
        print(f"\n📊 Statistiques: ✅ {self.stats['success']} | "
              f"❌ {self.stats['errors']} | "
              f"⏭️ {self.stats['skipped']}")
    
    def _print_final_stats(self):
        """Affiche statistiques finales"""
        duration = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
        
        print(f"""
📊 STATISTIQUES FINALES:
  Total articles     : {self.stats['total']}
  ✅ Succès          : {self.stats['success']}
  ❌ Erreurs         : {self.stats['errors']}
  ⏭️ Déjà traités    : {self.stats['skipped']}
  ⏱️ Durée totale    : {duration:.1f}s ({duration/60:.1f} min)
  ⚡ Vitesse moyenne : {self.stats['success']/duration*60:.1f} articles/min
        """)