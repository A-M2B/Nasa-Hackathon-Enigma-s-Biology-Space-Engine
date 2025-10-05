#!/usr/bin/env python3
"""
Script pour corriger les configurations des services
"""

import os
import sys
from pathlib import Path
import re

def update_docker_compose():
    """Met à jour le docker-compose.yml avec la bonne version de Weaviate et les bonnes configurations PostgreSQL"""
    docker_compose_path = Path(__file__).parent.parent / "docker-compose.yml"
    
    with open(docker_compose_path, 'r') as f:
        content = f.read()
    
    # Mettre à jour la version de Weaviate à une version supportée (>=1.27.0)
    content = re.sub(
        r'cr\.weaviate\.io/semitechnologies/weaviate:1\.23\.7',
        'cr.weaviate.io/semitechnologies/weaviate:1.27.0',
        content
    )
    
    # Mettre à jour la configuration PostgreSQL dans docker-compose.yml pour correspondre au .env
    content = re.sub(
        r'POSTGRES_USER: postgres',
        'POSTGRES_USER: bioscience',
        content
    )
    content = re.sub(
        r'POSTGRES_PASSWORD: postgres',
        'POSTGRES_PASSWORD: akoredeakorede',
        content
    )
    
    with open(docker_compose_path, 'w') as f:
        f.write(content)
    
    print("✅ docker-compose.yml mis à jour avec la bonne version de Weaviate et les bonnes configurations PostgreSQL")

def display_fixes():
    """Affiche les corrections à effectuer manuellement si nécessaire"""
    print("\n📋 CORRECTIONS À APPLIQUER :")
    print("\n1. PostgreSQL :")
    print("   - Les identifiants dans docker-compose.yml ont été mis à jour pour correspondre à ceux du .env")
    print("   - Ancien: POSTGRES_USER=postgres, POSTGRES_PASSWORD=postgres")
    print("   - Nouveau: POSTGRES_USER=bioscience, POSTGRES_PASSWORD=akoredeakorede")
    
    print("\n2. Elasticsearch :")
    print("   - Assurez-vous qu'Elasticsearch est démarré via Docker Compose")
    print("   - Commande: docker-compose up elasticsearch")
    
    print("\n3. Weaviate :")
    print("   - La version a été mise à jour de 1.23.7 à 1.27.0 (supportée)")
    
    print("\n4. Redémarrage des services :")
    print("   - Après avoir mis à jour le docker-compose.yml, redémarrez les services:")
    print("   - docker-compose down && docker-compose up -d")

def main():
    print("🔧 Correction des configurations des services...")
    
    try:
        update_docker_compose()
        display_fixes()
        
        print("\n✅ Corrections appliquées avec succès !")
        print("\n💡 Lancez 'docker-compose up -d' pour redémarrer les services avec les nouvelles configurations.")
        
    except Exception as e:
        print(f"❌ Erreur lors de la correction des configurations : {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)