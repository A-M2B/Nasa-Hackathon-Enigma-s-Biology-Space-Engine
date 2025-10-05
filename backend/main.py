from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import asyncpg
from elasticsearch import AsyncElasticsearch
import weaviate
from neo4j import AsyncGraphDatabase
import json
from datetime import datetime
import csv
import io

from config import config
from clients.ai_client import AIEnricher
from processors.knowledge_graph import KnowledgeGraphBuilder

app = FastAPI(
    title="NASA Bioscience Intelligence API",
    description="API for NASA bioscience publications",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global clients
postgres_pool = None
es_client = None
weaviate_client = None
kg_builder = None
ai_enricher = None

@app.on_event("startup")
async def startup():
    """Initialise les connexions aux bases de données"""
    global postgres_pool, es_client, weaviate_client, kg_builder, ai_enricher
    
    # PostgreSQL
    postgres_pool = await asyncpg.create_pool(
        host=config.postgres.host,
        port=config.postgres.port,
        user=config.postgres.user,
        password=config.postgres.password,
        database=config.postgres.database
    )
    
    # Elasticsearch
    es_client = AsyncElasticsearch(hosts=[config.elasticsearch.url])
    
    # Weaviate
    weaviate_client = weaviate.connect_to_local(
        host=config.weaviate.host,
        port=config.weaviate.port,
        grpc_port=config.weaviate.grpc_port,
        skip_init_checks=True,
    )
    
    # Neo4j
    kg_builder = KnowledgeGraphBuilder(
        uri=config.neo4j.uri,
        user=config.neo4j.user,
        password=config.neo4j.password
    )
    
    # AI Client
    ai_enricher = AIEnricher(
        groq_api_key=config.ai.groq_api_key
    )
    
    print("✅ All services initialized")

@app.on_event("shutdown")
async def shutdown():
    """Ferme toutes les connexions"""
    if postgres_pool:
        await postgres_pool.close()
    if es_client:
        await es_client.close()
    if kg_builder:
        await kg_builder.close()

# ==================== PUBLICATIONS ====================

@app.get("/api/publications")
async def get_publications(
    organism: Optional[str] = Query(None),
    year_from: Optional[str] = Query(None),  # Changed to str to handle empty strings
    year_to: Optional[str] = Query(None),    # Changed to str to handle empty strings
    journal: Optional[str] = Query(None),
    limit: int = Query(50, le=500)
) -> List[Dict]:
    """Récupère les publications avec filtres"""
    
    query = "SELECT * FROM publications WHERE 1=1"
    params = []
    param_count = 1
    
    # Convert string parameters to int only if they are not None or empty
    year_from_int = int(year_from) if year_from and year_from.isdigit() else None
    year_to_int = int(year_to) if year_to and year_to.isdigit() else None
    
    if organism:
        query += f" AND organisms_studied @> ${param_count}"
        params.append(json.dumps([organism]))
        param_count += 1
    
    if year_from_int is not None:
        query += f" AND EXTRACT(YEAR FROM publication_date::date) >= ${param_count}"
        params.append(year_from_int)
        param_count += 1
    
    if year_to_int is not None:
        query += f" AND EXTRACT(YEAR FROM publication_date::date) <= ${param_count}"
        params.append(year_to_int)
        param_count += 1
    
    if journal:
        query += f" AND journal ILIKE ${param_count}"
        params.append(f"%{journal}%")
        param_count += 1
    
    query += f" ORDER BY publication_date DESC LIMIT ${param_count}"
    params.append(limit)
    
    async with postgres_pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
    
    return [dict(row) for row in rows]

@app.get("/api/publications/{pmc_id}")
async def get_publication(pmc_id: str) -> Dict:
    """Récupère une publication spécifique"""
    
    async with postgres_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM publications WHERE pmc_id = $1",
            pmc_id
        )
    
    if not row:
        raise HTTPException(status_code=404, detail="Publication not found")
    
    return dict(row)

# ==================== SEARCH ====================

class SemanticSearchRequest(BaseModel):
    query: str
    top_k: int = 10
    filters: Optional[Dict] = None

@app.post("/api/search/semantic")
async def semantic_search(
    request: SemanticSearchRequest = Body(...)
) -> List[Dict]:
    """Recherche sémantique via Weaviate"""
    
    try:
        # Génère l'embedding de la requête
        query_embedding = await ai_enricher.generate_embeddings([request.query])
        
        # Recherche dans Weaviate - new API syntax
        collection = weaviate_client.collections.get("Publication")
        response = collection.query.near_vector(
            query_embedding[0],
            limit=request.top_k,
            return_properties=["pmcId", "title", "abstract", "publicationDate", "journal"]
        )
        
        publications = []
        for item in response.objects:
            pub = item.properties
            pub["similarity"] = 1 - (getattr(item, 'distance', 1.0) or 1.0)
            pub["pmc_id"] = pub.pop("pmcId", "")
            pub["publication_date"] = pub.pop("publicationDate", "")
            publications.append(pub)
        
        return publications
    except Exception as e:
        print(f"Error in semantic_search: {e}")
        return []

@app.post("/api/search/hybrid")
async def hybrid_search(request: SemanticSearchRequest = Body(...)) -> List[Dict]:
    """Recherche hybride (sémantique + mots-clés)"""
    
    try:
        # Recherche sémantique en utilisant les mêmes paramètres que la requête
        semantic_results = await semantic_search(request)
        
        # Recherche mots-clés via Elasticsearch
        es_results = await es_client.search(
            index="publications",
            body={
                "query": {
                    "multi_match": {
                        "query": request.query,
                        "fields": ["title^3", "abstract^2", "full_text"]
                    }
                },
                "size": request.top_k * 2
            }
        )
        
        # Fusion RRF (Reciprocal Rank Fusion)
        scores = {}
        k = 60
        
        for rank, result in enumerate(semantic_results):
            pmc_id = result["pmc_id"]
            scores[pmc_id] = scores.get(pmc_id, 0) + 1 / (rank + k)
        
        for rank, hit in enumerate(es_results["hits"]["hits"]):
            pmc_id = hit["_source"]["pmc_id"]
            scores[pmc_id] = scores.get(pmc_id, 0) + 1 / (rank + k)
        
        # Trie par score
        sorted_ids = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:request.top_k]
        
        # Récupère les détails
        results = []
        async with postgres_pool.acquire() as conn:
            for pmc_id, score in sorted_ids:
                row = await conn.fetchrow(
                    "SELECT pmc_id, title, abstract, publication_date, journal FROM publications WHERE pmc_id = $1",
                    pmc_id
                )
                if row:
                    result = dict(row)
                    result["similarity"] = score
                    results.append(result)
        
        return results
    except Exception as e:
        print(f"Error in hybrid_search: {e}")
        return []

# ==================== CHAT ====================

class ChatRequest(BaseModel):
    message: str
    context: Optional[List[str]] = None
    user_role: str = "scientist"

@app.post("/api/chat")
async def chat(
    request: ChatRequest = Body(...)
) -> Dict:
    """Chat avec l'IA"""
    
    try:
        # Recherche documents pertinents using the updated semantic search function
        search_request = SemanticSearchRequest(query=request.message, top_k=5)
        
        # Génère l'embedding de la requête
        query_embedding = await ai_enricher.generate_embeddings([search_request.query])
        
        # Recherche dans Weaviate - new API syntax
        collection = weaviate_client.collections.get("Publication")
        response = collection.query.near_vector(
            query_embedding[0],
            limit=search_request.top_k,
            return_properties=["pmcId", "title", "abstract", "publicationDate", "journal"]
        )
        
        relevant_docs = []
        for item in response.objects:
            pub = item.properties
            pub["similarity"] = 1 - (getattr(item, 'distance', 1.0) or 1.0)
            pub["pmc_id"] = pub.pop("pmcId", "")
            pub["publication_date"] = pub.pop("publicationDate", "")
            relevant_docs.append(pub)
        
        # Construit le contexte
        context_text = "\n\n".join([
            f"Publication {doc['pmc_id']}: {doc['title']}\n{doc['abstract']}"
            for doc in relevant_docs
        ])
        
        # Personnalise selon le rôle
        role_prompts = {
            "scientist": "Tu es un assistant scientifique expert. Sois précis et technique.",
            "manager": "Tu es un conseiller stratégique. Focus sur impact et opportunités.",
            "architect": "Tu es un expert en planification de missions. Donne des recommandations actionnables."
        }
        
        system_prompt = role_prompts.get(request.user_role, role_prompts["scientist"])
        
        # Appelle l'IA
        from groq import AsyncGroq
        client = AsyncGroq(api_key=config.ai.groq_api_key)
        
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=2000,
            temperature=0.7,
            system=system_prompt,
            messages=[{
                "role": "user",
                "content": f"""Contexte des publications pertinentes:
            {context_text}

            Question de l'utilisateur: {request.message}

            Réponds de manière claire et cite tes sources (PMC IDs)."""
            }]
        )
        
        return {
            "response": response.choices[0].message.content,
            "sources": [doc["pmc_id"] for doc in relevant_docs]
        }
    except Exception as e:
        print(f"Error in chat: {e}")
        return {
            "response": "Désolé, une erreur s'est produite lors du traitement de votre demande.",
            "sources": []
        }

# ==================== GRAPH ====================

@app.get("/api/graph/data")
async def get_graph_data(
    nodeTypes: Optional[List[str]] = Query(None),
    maxNodes: int = 100
) -> Dict:
    """Récupère les données du graphe"""
    
    node_filter = ""
    if nodeTypes:
        labels = " OR ".join([f"n:{t}" for t in nodeTypes])
        node_filter = f"WHERE {labels}"
    
    query = f"""
    MATCH (n)
    {node_filter}
    WITH n LIMIT {maxNodes}
    OPTIONAL MATCH (n)-[r]->(m)
    RETURN n, r, m
    """
    
    nodes = []
    links = []
    node_ids = set()
    
    async with kg_builder.driver.session() as session:
        result = await session.run(query)
        
        async for record in result:
            # Nœud source
            n = record.get("n")
            if n and n.element_id not in node_ids:
                nodes.append({
                    "id": n.element_id,
                    "label": n.get("name") or n.get("title") or n.element_id,
                    "type": list(n.labels)[0] if n.labels else "Unknown",
                    "properties": dict(n)
                })
                node_ids.add(n.element_id)
            
            # Nœud cible
            m = record.get("m")
            if m and m.element_id not in node_ids:
                nodes.append({
                    "id": m.element_id,
                    "label": m.get("name") or m.get("title") or m.element_id,
                    "type": list(m.labels)[0] if m.labels else "Unknown",
                    "properties": dict(m)
                })
                node_ids.add(m.element_id)
            
            # Relation
            r = record.get("r")
            if r:
                links.append({
                    "source": n.element_id,
                    "target": m.element_id,
                    "type": r.type,
                    "properties": dict(r)
                })
    
    return {"nodes": nodes, "links": links}

@app.get("/api/graph/publication/{pmc_id}")
async def get_publication_graph(pmc_id: str) -> Dict:
    """Récupère le graphe d'une publication spécifique"""
    
    try:
        connections = await kg_builder.get_publication_connections(pmc_id)
        return connections
    except Exception as e:
        print(f"Error in get_publication_graph for pmc_id {pmc_id}: {e}")
        return {"nodes": [], "links": []}

# ==================== INSIGHTS ====================

@app.get("/api/insights/gaps")
async def get_knowledge_gaps() -> List[Dict]:
    """Identifie les lacunes de connaissances"""
    
    try:
        gaps = await kg_builder.find_knowledge_gaps()
        return gaps
    except Exception as e:
        print(f"Error in get_knowledge_gaps: {e}")
        # Return an empty list or default response if there's an error
        return []

@app.get("/api/insights/consensus/{topic}")
async def get_consensus(topic: str) -> Dict:
    """Analyse consensus/désaccords"""
    
    async with kg_builder.driver.session() as session:
        result = await session.run("""
            MATCH (p:Publication)-[:MENTIONS]->(e:Entity {name: $topic})
            RETURN p.key_findings as findings, p.title as title
        """, topic=topic)
        
        findings_list = []
        async for record in result:
            findings_list.append({
                "title": record["title"],
                "findings": record["findings"]
            })
    
    # Analyse simple (à améliorer avec LLM)
    return {
        "consensus": [],
        "disagreements": [],
        "publications_count": len(findings_list)
    }

@app.get("/api/insights/trends")
async def get_trending_topics() -> List[Dict]:
    """Identifie les sujets tendance"""
    
    # Agrège par keywords des 2 dernières années
    async with postgres_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT 
                keyword,
                COUNT(*) as count,
                ARRAY_AGG(pmc_id) as publications
            FROM publications, 
                 jsonb_array_elements_text(keywords) as keyword
            WHERE EXTRACT(YEAR FROM publication_date::date) >= EXTRACT(YEAR FROM CURRENT_DATE) - 2
            GROUP BY keyword
            HAVING COUNT(*) >= 3
            ORDER BY count DESC
            LIMIT 20
        """)
    
    return [
        {
            "topic": row["keyword"],
            "growth_rate": 0,  # À calculer
            "publications": len(row["publications"])
        }
        for row in rows
    ]

# ==================== RECOMMENDATIONS ====================

@app.get("/api/recommendations")
async def get_mission_recommendations(
    mission_type: str,
    duration: int,
    crew_size: int
) -> Dict:
    """Génère des recommandations de mission"""
    
    # Trouve études pertinentes
    async with postgres_pool.acquire() as conn:
        studies = await conn.fetch("""
            SELECT * FROM publications
            WHERE 
                (space_conditions @> $1::jsonb
                OR organisms_studied @> $2::jsonb)
            ORDER BY publication_date DESC
            LIMIT 50
        """, 
        json.dumps([{"type": "gravity", "value": "microgravity"}]),
        json.dumps(["Homo sapiens"])
        )
    
    # Agrège les connaissances
    all_findings = []
    for study in studies:
        findings = json.loads(study["key_findings"] or "[]")
        all_findings.extend(findings)
    
    # Génère recommandations avec IA
    from groq import AsyncGroq
    client = AsyncGroq(api_key=config.ai.groq_api_key)
    
    prompt = f"""
Basé sur {len(studies)} études scientifiques, génère des recommandations pour :
- Mission: {mission_type}
- Durée: {duration} jours
- Équipage: {crew_size} personnes

Principales découvertes:
{json.dumps(all_findings[:20], indent=2)}

Génère un rapport JSON avec:
- critical_risks (top 5)
- mandatory_countermeasures
- budget_summary

Réponds UNIQUEMENT en JSON valide.
"""
    
    response = await client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=4000,
        temperature=0.3,
        messages=[{"role": "user", "content": prompt}]
    )
    
    try:
        response_text = response.choices[0].message.content
        recommendations = json.loads(response_text)
    except:
        # Fallback
        recommendations = {
            "critical_risks": [],
            "mandatory_countermeasures": [],
            "budget_summary": {}
        }
    
    return recommendations

# ==================== DASHBOARD ====================

@app.get("/api/dashboard/stats")
async def get_dashboard_stats() -> Dict:
    """Statistiques du dashboard"""
    
    async with postgres_pool.acquire() as conn:
        # Total publications
        total_pubs = await conn.fetchval("SELECT COUNT(*) FROM publications")
        
        # Total organismes
        organisms = await conn.fetch("""
            SELECT DISTINCT organism
            FROM publications, jsonb_array_elements_text(organisms_studied) as organism
        """)
        
        # Recent findings
        recent = await conn.fetch("""
            SELECT key_findings
            FROM publications
            WHERE key_findings IS NOT NULL
            ORDER BY publication_date DESC
            LIMIT 10
        """)
        
        findings = []
        for row in recent:
            findings.extend(json.loads(row["key_findings"] or "[]"))
        
        # Trend par année
        trend = await conn.fetch("""
            SELECT 
                EXTRACT(YEAR FROM publication_date::date) as year,
                COUNT(*) as count
            FROM publications
            WHERE publication_date IS NOT NULL
            GROUP BY year
            ORDER BY year
        """)
    
    return {
        "total_publications": total_pubs,
        "total_organisms": len(organisms),
        "total_conditions": 0,  # À calculer
        "recent_findings": findings[:5],
        "publication_trend": [
            {"date": str(int(row["year"])), "count": row["count"]}
            for row in trend
        ]
    }

# ==================== EXPORT ====================

@app.post("/api/export")
async def export_data(
    pmc_ids: Optional[List[str]] = None,
    format: str = "csv"
) -> StreamingResponse:
    """Exporte les données"""
    
    query = "SELECT * FROM publications"
    params = []
    
    if pmc_ids:
        query += " WHERE pmc_id = ANY($1)"
        params.append(pmc_ids)
    
    async with postgres_pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
    
    if format == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))
        
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=publications.csv"}
        )
    
    elif format == "json":
        data = [dict(row) for row in rows]
        return StreamingResponse(
            iter([json.dumps(data, indent=2)]),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=publications.json"}
        )

# ==================== HEALTH CHECK ====================

@app.get("/health")
async def health_check():
    """Vérifie l'état de l'API"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "postgres": postgres_pool is not None,
            "elasticsearch": es_client is not None,
            "weaviate": weaviate_client is not None,
            "neo4j": kg_builder is not None
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)