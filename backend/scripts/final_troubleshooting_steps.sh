#!/bin/bash
"""
Étapes finales pour résoudre les problèmes de services
"""

echo "==============================================="
echo "     ÉTAPES FINALES DE RÉSOLUTION"
echo "==============================================="

echo
echo "❌ PROBLÈME ACTUEL : Utilisateur non membre du groupe docker"
echo "   Commande 'groups' montre que 'docker' n'est pas dans la liste des groupes"
echo

echo "🔧 SOLUTION :"
echo "   1. Vous avez déjà exécuté : sudo usermod -aG docker nano"
echo "   2. MAIS il faut maintenant vous reconnecter pour que le changement prenne effet"
echo

echo "🔄 MÉTHODES POUR ACTIVER LE GROUPE DOCKER :"
echo "   Option 1 (recommandée) :"
echo "     - Fermez votre session graphique (ou déconnectez-vous)"
echo "     - Reconnectez-vous"
echo "     - Vérifiez avec 'groups' que 'docker' est présent"
echo
echo "   Option 2 :"
echo "     - Redémarrez votre ordinateur"
echo "     - Cela garantit que tous les changements de groupe sont appliqués"
echo
echo "   Option 3 (alternative temporaire) :"
echo "     - Vous pouvez exécuter les commandes Docker avec sudo :"
echo "       sudo docker-compose down && sudo docker-compose up -d"
echo "     - Mais il est préférable de redémarrer la session pour éviter les problèmes de permissions"
echo

echo "📋 ÉTATS ACTUELS DES SERVICES :"
echo "   - Les configurations dans docker-compose.yml sont CORRECTES :"
echo "     ✓ PostgreSQL : bioscience / akoredeakorede / pmc_bioscience"
echo "     ✓ Weaviate : version 1.27.0 (supportée)"
echo "     ✓ Elasticsearch : configuration correcte"
echo

echo "✅ PROCÉDURE COMPLÈTE APRÈS REDÉMARRAGE/RECONNEXION :"
echo "   1. Vérifiez que vous êtes dans le groupe docker :"
echo "      groups | grep docker"
echo
echo "   2. Arrêtez et redémarrez les services :"
echo "      cd /home/nano/BioKnowledge"
echo "      docker-compose down"
echo "      docker-compose up -d"
echo
echo "   3. Vérifiez l'état des services :"
echo "      python3.12 scripts/check_services.py"
echo

echo "⚠️ ATTENTION ADDITIONNELLE :"
echo "   - Si Elasticsearch ne démarre pas, il se peut que votre système n'ait pas"
echo "     assez de mémoire ou que vm.max_map_count soit trop bas :"
echo "     sudo sysctl -w vm.max_map_count=262144"
echo
echo "   - Assurez-vous également que les ports 5432, 9200, 8080, 7687 ne sont pas utilisés :"
echo "     sudo lsof -i :5432,:9200,:8080,:7687"
echo

echo "   - Si Weaviate continue de poser problème, vérifiez ces ports spécifiquement :"
echo "     sudo lsof -i :8080,:50051"
echo

echo
echo "Une fois reconnecté et les services démarrés, tous les services devraient fonctionner correctement."