import os
import shutil
from threading import Thread
import webbrowser
from config import UPLOADS_DIR

def run_flask_app():
    """Importuje a spustí Flask aplikaci."""
    from app import app
    # Spustíme Flask v samostatném vlákně, aby neblokoval hlavní vlákno
    # a zároveň otevřeme prohlížeč.
    url = "http://127.0.0.1:5000"
    
    def start_server():
        app.run(debug=False, use_reloader=False)

    # Spuštění serveru v samostatném vlákně
    server_thread = Thread(target=start_server)
    server_thread.daemon = True
    server_thread.start()
    
    # Otevření prohlížeče
    try:
        webbrowser.open(url)
        print(f"Webové rozhraní by se mělo otevřít v prohlížeči na adrese: {url}")
    except Exception as e:
        print(f"Nepodařilo se automaticky otevřít prohlížeč. Otevřete prosím manuálně: {url}")
        print(f"Chyba: {e}")

    server_thread.join() # Čekáme na ukončení serveru (např. Ctrl+C v terminálu)


def run_cli_app():
    """Importuje a spustí CLI rozhraní."""
    from extract_bill_json import run_cli
    run_cli()

def run_rag_app():
    """Importuje a spustí RAG systém."""
    from rag import run_rag_cli
    run_rag_cli()

def initialize_project():
    """Zajistí existenci potřebných adresářů a provede úklid."""
    # --- Automatický úklid při spuštění ---
    # Pokud adresář 'uploads' existuje z předchozího běhu, smažeme ho
    if os.path.exists(UPLOADS_DIR):
        print(f"🧹 Provádím úklid: Mažu dočasný adresář '{UPLOADS_DIR}'...")
        try:
            shutil.rmtree(UPLOADS_DIR)
            print("✅ Úklid dokončen.")
        except OSError as e:
            print(f"❌ Chyba při mazání adresáře {UPLOADS_DIR}: {e}")
    
    # --- Vytvoření potřebných adresářů ---
    # Vytvoří adresář 'uploads', pokud neexistuje
    os.makedirs(UPLOADS_DIR, exist_ok=True)


if __name__ == "__main__":
    initialize_project()

    while True:
        print("\n---  hlavní menu ---")
        print("1: 🌐 Grafické rozhraní v prohlížeči (GUI)")
        print("2: ⌨️  Rozhraní v příkazovém řádku (CLI)")
        print("3: 💬 Spustit RAG systém")
        print("0: 🚪 Ukončit")
        
        volba = input("Zadejte svou volbu (1, 2, 3 nebo 0): ").strip()
        
        if volba == '1':
            print("🚀 Spouštím grafické rozhraní...")
            run_flask_app()
            break # Po ukončení web serveru se program ukončí
        elif volba == '2':
            print("🚀 Spouštím rozhraní v příkazovém řádku...")
            run_cli_app()
            # Po skončení se vrátí do hlavního menu (break odstraněn)
        elif volba == '3':
            print("🚀 Spouštím RAG systém...")
            run_rag_app()
            # Po skončení se vrátí do hlavního menu (break odstraněn)
        elif volba == '0':
            print("Ukončuji program.")
            break
        else:
            print("Neplatná volba, zkuste to znovu.")
