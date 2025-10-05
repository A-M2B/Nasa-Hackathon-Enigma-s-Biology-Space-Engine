#!/usr/bin/env python3
"""
Script pour initialiser la base de données PostgreSQL
"""

import asyncio
import asyncpg
from pathlib import Path
import sys

# Ajoute le dossier parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import config

async def init_database():
    """Initialise la base de données PostgreSQL"""
    
    print("🔧 Initialisation de la base de données PostgreSQL...")
    
    # Connexion sans spécifier la base (pour créer la DB si nécessaire)
    conn = await asyncpg.connect(
        host=config.postgres.host,
        port=config.postgres.port,
        user=config.postgres.user,
        password=config.postgres.password,
        database='postgres'  # Base par défaut
    )
    
    try:
        # Vérifie si la base existe
        db_exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1",
            config.postgres.database
        )
        
        if not db_exists:
            print(f"📦 Création de la base de données '{config.postgres.database}'...")
            await conn.execute(f'CREATE DATABASE {config.postgres.database}')
            print("✅ Base de données créée")
        else:
            print(f"✅ Base de données '{config.postgres.database}' existe déjà")
        
    finally:
        await conn.close()
    
    # Connexion à la base cible
    conn = await asyncpg.connect(
        host=config.postgres.host,
        port=config.postgres.port,
        user=config.postgres.user,
        password=config.postgres.password,
        database=config.postgres.database
    )
    
    try:
        # Exécute le script SQL
        schema_file = Path(__file__).parent.parent / 'database' / 'postgres_schema.sql'
        
        if not schema_file.exists():
            print(f"❌ Fichier schema non trouvé: {schema_file}")
            return
        
        print("📜 Exécution du script SQL...")
        with open(schema_file, 'r') as f:
            sql = f.read()
            await conn.execute(sql)
        
        print("✅ Tables créées avec succès")
        
        # Vérifie les tables créées
        tables = await conn.fetch("""
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname = 'public'
        """)
        
        print(f"\n📊 Tables créées:")
        for table in tables:
            print(f"  - {table['tablename']}")
        
    finally:
        await conn.close()
    
    print("\n🎉 Initialisation terminée avec succès!")

if __name__ == "__main__":
    asyncio.run(init_database())