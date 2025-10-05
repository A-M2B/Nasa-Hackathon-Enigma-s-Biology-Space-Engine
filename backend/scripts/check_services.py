#!/usr/bin/env python3
"""
Script pour vérifier que tous les services sont accessibles
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import config
import asyncpg
from elasticsearch import AsyncElasticsearch
import weaviate
from neo4j import AsyncGraphDatabase

async def check_postgres():
    """Vérifie PostgreSQL"""
    try:
        conn = await asyncpg.connect(
            host=config.postgres.host,
            port=config.postgres.port,
            user=config.postgres.user,
            password=config.postgres.password,
            database=config.postgres.database
        )
        await conn.close()
        print("✅ PostgreSQL: OK")
        return True
    except Exception as e:
        print(f"❌ PostgreSQL: ERREUR - {e}")
        return False

async def check_elasticsearch():
    """Vérifie Elasticsearch"""
    try:
        # Utiliser les paramètres de compatibilité Elasticsearch 8+
        es = AsyncElasticsearch(
            hosts=[config.elasticsearch.url],
            headers={
                "Content-Type": "application/json",
                "Accept": "application/vnd.elasticsearch+json; compatible-with=8"
            },
            # Activer la compatibilité avec les versions antérieures
            basic_auth=("elastic", "changeme"),  # Mot de passe par défaut
            verify_certs=False,
            ssl_show_warn=False
        )
        info = await es.info()
        await es.close()
        print(f"✅ Elasticsearch: OK (version {info['version']['number']})")
        return True
    except Exception as e:
        # Essayons une approche HTTP directe
        try:
            import requests
            response = requests.get(config.elasticsearch.url)
            if response.status_code == 200:
                es_data = response.json()
                version = es_data.get('version', {}).get('number', 'inconnue')
                print(f"✅ Elasticsearch: OK (version {version} - via HTTP)")
                return True
            else:
                print(f"❌ Elasticsearch: Erreur HTTP {response.status_code}")
                return False
        except Exception as e2:
            print(f"❌ Elasticsearch: ERREUR - {e}; HTTP: {e2}")
            return False

def check_weaviate():
    """Vérifie Weaviate avec une approche simplifiée"""
    try:
        # Essayons une vérification HTTP simple en premier
        import requests
        response = requests.get(f"http://{config.weaviate.host}:{config.weaviate.port}/v1/.well-known/ready", timeout=10)
        if response.status_code == 200:
            print("✅ Weaviate: OK (HTTP API disponible)")
            return True
        else:
            print(f"❌ Weaviate: API HTTP indique un problème (status: {response.status_code})")
            return False
    except Exception as e:
        # Essayer avec le client Weaviate mais avec les vérifications initiales désactivées
        try:
            import weaviate.client
            # Utiliser une connexion avec skip_init_checks pour éviter les problèmes de gRPC
            client = weaviate.connect_to_local(
                host=config.weaviate.host,
                port=config.weaviate.port,
                skip_init_checks=True  # Désactiver les vérifications initiales qui posent problème
            )
            # Tester une opération simple
            meta = client.get_meta()
            client.close()
            print("✅ Weaviate: OK (connexion établie)")
            return True
        except Exception as e2:
            print(f"❌ Weaviate: ERREUR - {e}; Alternative: {e2}")
            return False

async def check_neo4j():
    """Vérifie Neo4j"""
    try:
        driver = AsyncGraphDatabase.driver(
            config.neo4j.uri,
            auth=(config.neo4j.user, config.neo4j.password)
        )
        async with driver.session() as session:
            result = await session.run("RETURN 1 as test")
            record = await result.single()
            assert record["test"] == 1
        await driver.close()
        print("✅ Neo4j: OK")
        return True
    except Exception as e:
        print(f"❌ Neo4j: ERREUR - {e}")
        return False

async def main():
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║         VÉRIFICATION DES SERVICES                         ║
    ╚═══════════════════════════════════════════════════════════╝
    """)
    
    results = []
    
    print("🔍 Vérification en cours...\n")
    
    results.append(await check_postgres())
    results.append(await check_elasticsearch())
    results.append(check_weaviate())
    results.append(await check_neo4j())
    
    print("\n" + "="*60)
    
    if all(results):
        print("🎉 Tous les services sont opérationnels !")
        return 0
    else:
        failed = sum(1 for r in results if not r)
        print(f"⚠️ {failed} service(s) en erreur")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)