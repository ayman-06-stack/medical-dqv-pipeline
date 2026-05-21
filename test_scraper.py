import sys
from pathlib import Path
sys.path.insert(0, 'src')

try:
    from scraper import MedicalScraper, ScraperConfig
    print('✅ Import scraper OK')
    
    config = ScraperConfig(
        url='https://archive.ics.uci.edu/ml/machine-learning-databases/heart-disease/processed.cleveland.data',
        mode='static'
    )
    print('✅ Config créée')
    
    scraper = MedicalScraper(config)
    print('✅ Scraper créé')
    
    df = scraper.run()
    print(f'✅ Scraping OK : {len(df)} lignes, {len(df.columns)} colonnes')
    print(df.head())
    
except Exception as e:
    print(f'❌ Erreur : {type(e).__name__}: {e}')
    import traceback
    traceback.print_exc()
