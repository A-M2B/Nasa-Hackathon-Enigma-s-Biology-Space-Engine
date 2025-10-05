import weaviate
from typing import Dict

def create_weaviate_schema(client: weaviate.WeaviateClient):
    """
    Crée le schéma Weaviate pour les publications
    """
    
    try:
        # Supprime les classes existantes (optionnel - attention en production!)
        try:
            client.collections.delete("Publication")
            print("Classe Publication existante supprimée")
        except:
            pass
        
        try:
            client.collections.delete("PublicationSection")
            print("Classe PublicationSection existante supprimée")
        except:
            pass

        # Crée la collection Publication
        client.collections.create(
            name="Publication",
            description="NASA Bioscience publication from PMC",
            # Nous n'utilisons pas de vectorizer ici car nous fournissons nos propres vecteurs
            vectorizer_config=weaviate.classes.config.Configure.Vectorizer.none()
        )
        print("✅ Collection Publication créée")

        # Crée la collection PublicationSection
        client.collections.create(
            name="PublicationSection",
            description="Individual section of a publication",
            vectorizer_config=weaviate.classes.config.Configure.Vectorizer.none()
        )
        print("✅ Collection PublicationSection créée")
        
    except Exception as e:
        print(f"❌ Erreur lors de la création du schéma Weaviate: {e}")
        raise

def get_weaviate_client(config) -> weaviate.WeaviateClient:
    """
    Crée et retourne un client Weaviate v4
    """
    try:
        # Utilisation de la méthode de connexion Weaviate v4
        client = weaviate.connect_to_local(
            host=config.weaviate.host,
            port=config.weaviate.port,
            skip_init_checks=True  # Passe les vérifications gRPC problématiques
        )
        
        # Test de connexion
        meta = client.get_meta()
        if meta:
            print("✅ Weaviate connecté")
            return client
        else:
            raise Exception("Weaviate n'est pas prêt")
            
    except Exception as e:
        print(f"❌ Erreur de connexion à Weaviate: {e}")
        raise