import asyncio
import json
import sys
from pathlib import Path

from config import config
from processors.batch_processor import PMCBatchProcessor

async def main():
    """
    Script principal pour ingérer les 608 articles
    """
    
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║     NASA BIOSCIENCE PUBLICATION INGESTION SYSTEM          ║
    ║                   PMC to Knowledge Graph                  ║
    ╚═══════════════════════════════════════════════════════════╝
    """)
    
    # 1. Charge la liste des URLs PMC
    print("📋 Chargement de la liste des articles...")
    
    # Option A : Depuis un fichier JSON
    urls_file = Path('data/pmc_urls.json')
    if urls_file.exists():
        with open(urls_file, 'r') as f:
            data = json.load(f)
            # Suppose format: [{"pmc_id": "PMC123", "url": "https://..."}, ...]
            if isinstance(data, list):
                if isinstance(data[0], dict):
                    pmc_urls = [item['url'] for item in data if 'url' in item]
                else:
                    pmc_urls = data
            else:
                pmc_urls = list(data.values())
    
    # Option B : Depuis un fichier texte (une URL par ligne)
    elif Path('data/pmc_urls.txt').exists():
        with open('data/pmc_urls.txt', 'r') as f:
            pmc_urls = [line.strip() for line in f if line.strip()]
    
    # Option C : Liste hardcodée pour test
    else:
        print("⚠️ Fichier URLs non trouvé, utilisation d'URLs de test...")
        pmc_urls = [
            "https://pmc.ncbi.nlm.nih.gov/articles/PMC11930778/",
            "https://pmc.ncbi.nlm.nih.gov/articles/PMC10234567/",
            # Ajoutez vos 608 URLs ici
        ]
    
    print(f"✅ {len(pmc_urls)} articles trouvés\n")
    
    # 2. Initialise le processeur
    processor = PMCBatchProcessor(config)
    
    try:
        # 3. Initialise tous les services
        await processor.initialize()
        
        # 4. Lance le traitement
        print(f"🚀 Début du traitement de {len(pmc_urls)} articles PMC...")
        try:
            await processor.process_all_articles(
                pmc_urls=pmc_urls,
                batch_size=10
            )

        except KeyboardInterrupt:
            print("\n⚠️ Interruption manuelle (Ctrl+C)")
            sys.exit(1)

        except asyncio.CancelledError:
            print("\n⚠️ Tâche async annulée (CancelledError)")
            await processor.cleanup()
            sys.exit(0)

        except Exception as e:
            print(f"\n❌ Erreur fatale: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    
    except Exception as e:
        print(f"\n❌ Erreur fatale: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    finally:
        # 5. Récupère les statistiques de traitement
        stats = getattr(processor, 'stats', None)
        if stats:
            total = stats.get('total', 0)
            success = stats.get('success', 0)
            errors = stats.get('errors', 0)
            skipped = stats.get('skipped', 0)
            
            print(f"\n📊 STATISTIQUES DE TRAITEMENT:")
            print(f"   - Total des articles à traiter: {total}")
            print(f"   - Articles traités avec succès: {success}")
            print(f"   - Articles en erreur: {errors}")
            print(f"   - Articles sautés (ex: sans sections): {skipped}")
            print(f"   - Total vérifié: {success + errors + skipped}")
        
        # 6. Nettoie les ressources
        await processor.cleanup()
    
    print("\n✨ Programme terminé avec succès!")

if __name__ == "__main__":
    # Lance le script
    asyncio.run(main())