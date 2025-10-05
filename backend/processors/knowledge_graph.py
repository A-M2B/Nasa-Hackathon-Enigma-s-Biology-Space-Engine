from neo4j import AsyncGraphDatabase
from typing import Dict, List
import asyncio

class KnowledgeGraphBuilder:
    """
    Constructeur de graphe de connaissances avec Neo4j
    """
    
    def __init__(self, uri: str, user: str, password: str):
        self.driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    
    async def close(self):
        """Ferme la connexion"""
        await self.driver.close()
    
    async def create_publication_node(self, article_data: Dict, enriched_data: Dict):
        """
        Crée un nœud publication avec ses relations
        """
        async with self.driver.session() as session:
            pmc_id = article_data['pmc_id']
            metadata = article_data.get('metadata', {})
            
            # 1. Crée le nœud publication principal
            await session.run("""
                MERGE (p:Publication {pmc_id: $pmc_id})
                SET p.title = $title,
                    p.abstract = $abstract,
                    p.journal = $journal,
                    p.publication_date = $publication_date,
                    p.doi = $doi,
                    p.pmid = $pmid,
                    p.hypothesis = $hypothesis
                """, 
                pmc_id=pmc_id,
                title=metadata.get('title', ''),
                abstract=metadata.get('abstract', ''),
                journal=metadata.get('journal', ''),
                publication_date=metadata.get('publication_date', ''),
                doi=metadata.get('doi', ''),
                pmid=metadata.get('pmid', ''),
                hypothesis=enriched_data.get('hypothesis', '')
            )
            
            # 2. Crée les relations avec les organismes
            organisms = enriched_data.get('organisms', [])
            for organism in organisms:
                if organism:
                    await session.run("""
                        MERGE (o:Organism {name: $name})
                        WITH o
                        MATCH (p:Publication {pmc_id: $pmc_id})
                        MERGE (p)-[:STUDIES]->(o)
                        """,
                        name=organism,
                        pmc_id=pmc_id
                    )
            
            # 3. Crée les relations avec les conditions spatiales
            conditions = enriched_data.get('space_conditions', [])
            for condition in conditions:
                if isinstance(condition, dict):
                    await session.run("""
                        MERGE (c:Condition {type: $type, value: $value})
                        WITH c
                        MATCH (p:Publication {pmc_id: $pmc_id})
                        MERGE (p)-[:TESTED_UNDER]->(c)
                        """,
                        type=condition.get('type', ''),
                        value=condition.get('value', ''),
                        pmc_id=pmc_id
                    )
            
            # 4. Crée les relations avec les entités (gènes, protéines, etc.)
            entities = enriched_data.get('entities', [])
            for entity in entities:
                if isinstance(entity, dict):
                    await session.run("""
                        MERGE (e:Entity {name: $name, type: $type})
                        WITH e
                        MATCH (p:Publication {pmc_id: $pmc_id})
                        MERGE (p)-[:MENTIONS]->(e)
                        """,
                        name=entity.get('name', ''),
                        type=entity.get('type', ''),
                        pmc_id=pmc_id
                    )
            
            # 5. Crée les nœuds de découvertes (findings)
            findings = enriched_data.get('key_findings', [])
            for i, finding in enumerate(findings):
                if finding:
                    await session.run("""
                        MATCH (p:Publication {pmc_id: $pmc_id})
                        MERGE (f:Finding {text: $text, publication_pmc_id: $pmc_id, index: $index})
                        MERGE (p)-[:HAS_FINDING]->(f)
                        """,
                        pmc_id=pmc_id,
                        text=finding,
                        index=i
                    )
            
            # 6. Crée les nœuds de lacunes de connaissances
            gaps = enriched_data.get('knowledge_gaps', [])
            for gap in gaps:
                if gap:
                    await session.run("""
                        MERGE (g:KnowledgeGap {description: $description})
                        WITH g
                        MATCH (p:Publication {pmc_id: $pmc_id})
                        MERGE (p)-[:IDENTIFIES_GAP]->(g)
                        """,
                        description=gap,
                        pmc_id=pmc_id
                    )
            
            # 7. Lie les auteurs
            authors = metadata.get('authors', [])
            for author in authors:
                if isinstance(author, dict):
                    author_name = f"{author.get('first_name', '')} {author.get('last_name', '')}".strip()
                    if author_name:
                        await session.run("""
                            MERGE (a:Author {name: $name})
                            WITH a
                            MATCH (p:Publication {pmc_id: $pmc_id})
                            MERGE (a)-[:AUTHORED]->(p)
                            """,
                            name=author_name,
                            pmc_id=pmc_id
                        )
            
            print(f"✅ Graphe créé pour {pmc_id}")
    
    async def find_knowledge_gaps(self) -> List[Dict]:
        """
        Identifie les lacunes de connaissances
        """
        async with self.driver.session() as session:
            # Gap 1: Organismes sous-étudiés
            result1 = await session.run("""
                MATCH (o:Organism)
                OPTIONAL MATCH (o)<-[:STUDIES]-(p:Publication)
                WITH o, COUNT(p) as study_count
                WHERE study_count < 3
                RETURN o.name as organism, study_count, 'understudied_organism' as gap_type
                ORDER BY study_count ASC
                LIMIT 20
            """)
            
            gaps = []
            async for record in result1:
                gap = dict(record)
                # Add default values for fields expected by the frontend
                gap['priority'] = 'high' if gap.get('study_count', 0) < 2 else 'medium'
                gap['rationale'] = f"{gap.get('organism', 'Unknown organism')} has been studied in fewer than 3 publications"
                gap['condition1'] = None
                gap['condition2'] = None
                gap['months'] = None
                gaps.append(gap)
            
            return gaps
    
    async def get_publication_connections(self, pmc_id: str) -> Dict:
        """
        Récupère toutes les connexions d'une publication
        """
        async with self.driver.session() as session:
            result = await session.run("""
                MATCH (p:Publication {pmc_id: $pmc_id})
                OPTIONAL MATCH (p)-[:STUDIES]->(o:Organism)
                OPTIONAL MATCH (p)-[:TESTED_UNDER]->(c:Condition)
                OPTIONAL MATCH (p)-[:MENTIONS]->(e:Entity)
                RETURN p,
                       COLLECT(DISTINCT o.name) as organisms,
                       COLLECT(DISTINCT c.type + ': ' + c.value) as conditions,
                       COLLECT(DISTINCT e.name) as entities
            """, pmc_id=pmc_id)
            
            record = await result.single()
            if record:
                return {
                    'publication': dict(record['p']),
                    'organisms': record['organisms'],
                    'conditions': record['conditions'],
                    'entities': record['entities']
                }
            return {}