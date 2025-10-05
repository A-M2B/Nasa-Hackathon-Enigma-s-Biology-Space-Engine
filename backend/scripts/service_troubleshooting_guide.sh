#!/bin/bash
"""
Guide de résolution des problèmes de services
"""

echo "==============================================="
echo "     GUIDE DE RÉSOLUTION DES PROBLÈMES"
echo "==============================================="

echo
echo "1. PROBLÈME D'AUTHENTIFICATION POSTGRESQL"
echo "------------------------------------------"
echo "Le problème est résolu dans le docker-compose.yml :"
echo "  - POSTGRES_USER: bioscience"
echo "  - POSTGRES_PASSWORD: akoredeakorede"
echo

echo "2. PROBLÈME DE VERSION WEAVIATE"
echo "-----------------------------"
echo "Le problème est résolu dans le docker-compose.yml :"
echo "  - Version mise à jour à 1.27.0 (au lieu de 1.23.7)"
echo

echo "3. PROBLÈME D'ACCÈS DOCKER"
echo "------------------------"
echo "Pour résoudre le problème d'accès à Docker :"
echo "  a) Ajouter l'utilisateur au groupe docker :"
echo "     sudo usermod -aG docker nano"
echo "  b) Se déconnecter et reconnecter (ou exécuter :)"
echo "     newgrp docker"
echo

echo "4. REDÉMARRER LES SERVICES DOCKER"
echo "--------------------------------"
echo "Après avoir résolu le problème d'accès Docker :"
echo "  cd /home/nano/BioKnowledge"
echo "  docker-compose down"
echo "  docker-compose up -d"
echo

echo "5. VÉRIFIER L'ÉTAT DES SERVICES"
echo "------------------------------"
echo "Une fois les services démarrés :"
echo "  python3.12 scripts/check_services.py"
echo

echo "6. DÉPANNAGE ADDITIONNEL"
echo "----------------------"
echo "Si Elasticsearch ne démarre pas correctement :"
echo "- Vérifier l'occupation mémoire : Elasticsearch nécessite beaucoup de mémoire"
echo "- Augmenter la mémoire virtuelle : sudo sysctl -w vm.max_map_count=262144"
echo
echo "Pour Weaviate, si vous rencontrez des problèmes :"
echo "- Vérifier que le port 8080 n'est pas utilisé par autre chose"
echo "- Vous pouvez tester l'accès à Weaviate via : curl http://localhost:8080/v1/.well-known/ready"
echo

echo "==============================================="
echo "APERÇU DES CONFIGURATIONS CORRECTES"
echo "==============================================="
echo
echo "Fichier .env :"
echo "------------"
echo "POSTGRES_USER=bioscience"
echo "POSTGRES_PASSWORD=akoredeakorede"
echo "POSTGRES_DB=pmc_bioscience"
echo "ELASTICSEARCH_HOST=localhost"
echo "ELASTICSEARCH_PORT=9200"
echo "WEAVIATE_HOST=localhost"
echo "WEAVIATE_PORT=8080"
echo
echo "docker-compose.yml (extrait) :"
echo "-----------------------------"
echo "postgres:"
echo "  environment:"
echo "    POSTGRES_USER: bioscience"
echo "    POSTGRES_PASSWORD: akoredeakorede"
echo "    POSTGRES_DB: pmc_bioscience"
echo "  healthcheck:"
echo "    test: [\"CMD-SHELL\", \"pg_isready -U bioscience\"]"
echo ""
echo "weaviate:"
echo "  image: cr.weaviate.io/semitechnologies/weaviate:1.27.0"
echo ""

echo
echo "N'oubliez pas de redémarrer votre session après avoir ajouté votre utilisateur au groupe docker !"