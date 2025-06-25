# --- Importy základních knihoven ---
# Flask je mikrorámec pro vytváření webových aplikací v Pythonu.
# render_template - slouží k načtení a zobrazení HTML šablon.
# request - objekt, který obsahuje data o aktuálním HTTP požadavku (např. nahrané soubory, data z formulářů).
# jsonify - převede Python slovník na platnou JSON odpověď pro API.
# send_from_directory - bezpečně pošle soubor z daného adresáře (používá se pro stahování výsledků).
from flask import Flask, render_template, request, jsonify, send_from_directory
# werkzeug.utils.secure_filename - funkce pro zabezpečení názvů souborů (odstraní nebezpečné znaky).
from werkzeug.utils import secure_filename
# uuid - generuje unikátní identifikátory, které použijeme pro oddělení session nahrávání.
import uuid
# os - poskytuje funkce pro práci s operačním systémem, např. pro vytváření adresářů a spojování cest.
import os

# --- Importy z naší vlastní logiky ---
import config  # Importujeme centrální konfigurační soubor
from extract_bill_json import (
    zpracovat_davku_jednotlivo as process_individually,
    zpracovat_davku_uctenek as process_in_batch,
    nacti_api_klic,
    vypocitat_naklady
)
from rag import get_rag_chain, ask_question
# Pro odhad ceny potřebujeme i samotný model
from langchain_google_genai import ChatGoogleGenerativeAI

# --- Inicializace Flask aplikace ---
# Vytvoříme instanci Flask aplikace. `__name__` je speciální proměnná v Pythonu,
# která pomáhá Flasku najít zdroje, jako jsou šablony a statické soubory.
app = Flask(__name__, template_folder=config.TEMPLATES_DIR)

# --- Konfigurace aplikace ---
# Načteme konfiguraci z centrálního souboru
app.config['UPLOAD_FOLDER'] = config.UPLOADS_DIR
app.config['RESULT_FOLDER'] = config.RESULT_DIR
app.config['ALLOWED_EXTENSIONS'] = config.ALLOWED_EXTENSIONS

# --- Globální proměnná a inicializace RAG chain ---
# Tímto zajistíme, že se model a databáze načtou jen jednou při startu aplikace.
# Inicializace proběhne při importu tohoto souboru.
# Ukládáme si chainy pro různé modely, abychom je nemuseli znovu vytvářet.
global_rag_chains = {}

def get_or_create_rag_chain(model_name):
    """Získá existující RAG chain pro daný model, nebo vytvoří nový."""
    global global_rag_chains
    if model_name not in global_rag_chains:
        print(f"Vytvářím nový RAG chain pro model: {model_name}...")
        global_rag_chains[model_name] = get_rag_chain(model_name)
        if global_rag_chains[model_name]:
            print(f"RAG chain pro model {model_name} je připraven.")
        else:
            print(f"POZOR: RAG chain pro model {model_name} se nepodařilo inicializovat.")
            return None
    return global_rag_chains[model_name]

# Načteme výchozí model při startu, pokud nějaký existuje v popisech
if config.MODEL_DESCRIPTIONS:
    default_model = next(iter(config.MODEL_DESCRIPTIONS))
    get_or_create_rag_chain(default_model)


# --- Pomocná funkce pro kontrolu přípon ---
def allowed_file(filename):
    """
    Zkontroluje, zda má soubor povolenou příponu.
    Vrací True, pokud je přípona v pořádku, jinak False.
    """
    # Zkontroluje, zda název souboru obsahuje tečku a zda text za poslední tečkou (přípona)
    # je v naší množině povolených přípon.
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# --- Definice rout (cest) pro webovou aplikaci ---

# @app.route('/') definuje, co se stane, když uživatel navštíví hlavní stránku (např. http://127.0.0.1:5000/).
@app.route('/')
def index():
    """
    Tato funkce obsluhuje hlavní stránku.
    Jejím úkolem je pouze zobrazit uživateli HTML šablonu `index.html`.
    """
    return render_template('index.html')

# @app.route('/process', methods=['POST']) definuje API koncový bod pro zpracování souborů.
# `methods=['POST']` znamená, že tato routa přijímá pouze HTTP POST požadavky,
# které se používají pro odesílání dat na server (např. z formuláře).
@app.route('/process', methods=['POST'])
def process_files():
    """
    Tato funkce je srdcem webové aplikace. Zpracovává nahrané soubory.
    """
    # 1. Zkontrolujeme, zda požadavek vůbec obsahuje nějaké soubory.
    if 'files[]' not in request.files:
        # Pokud ne, vrátíme chybovou JSON odpověď a HTTP status 400 (Bad Request).
        return jsonify({"error": "Nebyly vybrány žádné soubory."}), 400

    # 2. Načteme soubory a zvolenou metodu z formuláře.
    files = request.files.getlist('files[]') # `getlist` načte všechny soubory se stejným jménem.
    method = request.form.get('method')      # `get` načte hodnotu z pole formuláře.
    
    # 3. Zkontrolujeme API klíč.
    if not nacti_api_klic(config.API_KEY_FILE):
        return jsonify({"error": "API klíč nebyl nalezen. Vytvořte soubor api_key.txt."}), 500

    # 4. Vytvoříme unikátní adresář pro tuto konkrétní sadu nahrávaných souborů.
    # Tím zabráníme tomu, aby se soubory od různých uživatelů nebo z různých
    # nahrávání pletly dohromady.
    session_id = str(uuid.uuid4())
    session_upload_folder = os.path.join(app.config['UPLOAD_FOLDER'], session_id)
    os.makedirs(session_upload_folder)

    # 5. Uložíme soubory na server.
    saved_files = []
    for file in files:
        # Zkontrolujeme, zda soubor existuje a má povolenou příponu.
        if file and allowed_file(file.filename):
            # Zabezpečíme název souboru.
            filename = secure_filename(file.filename)
            # Vytvoříme úplnou cestu pro uložení.
            filepath = os.path.join(session_upload_folder, filename)
            # Uložíme soubor.
            file.save(filepath)
            saved_files.append(filepath)

    # Pokud nebyly nahrány žádné platné soubory, vrátíme chybu.
    if not saved_files:
        return jsonify({"error": "Nebyly nahrány žádné platné soubory."}), 400    # 6. Zavoláme příslušnou funkci pro zpracování na základě zvolené metody.
    try:
        results = [] # Inicializujeme prázdný seznam pro výsledky.
        if method == 'jednotlivo_metrics':
            # Voláme funkci pro jednotlivé zpracování se zapnutými metrikami.
            # Parametr `return_results=True` zajistí, že funkce vrátí strukturovaná data.
            results = process_individually(session_upload_folder, return_results=True, with_metrics=True)
        elif method == 'jednotlivo_basic':
            # Voláme funkci pro jednotlivé zpracování s vypnutými metrikami.
            results = process_individually(session_upload_folder, return_results=True, with_metrics=False)
        elif method == 'davkovo':
            # Voláme funkci pro dávkové zpracování.
            results = process_in_batch(session_upload_folder, return_results=True)
        else:
            # Pokud byla zvolena neznámá metoda, vrátíme chybu.
            return jsonify({"error": "Neznámá metoda zpracování."}), 400
        
        # 7. Vrátíme výsledky ve formátu JSON.
        # Prohlížeč (JavaScript) si tuto odpověď převezme a zobrazí výsledky uživateli.
        return jsonify({"results": results})

    except Exception as e:
        # Pokud během zpracování nastane jakákoliv chyba, zachytíme ji
        # a vrátíme srozumitelnou chybovou hlášku.
        return jsonify({"error": f"Nastala chyba při zpracování: {e}"}), 500

# @app.route('/result/<path:filename>') definuje routu pro stahování výsledných souborů.
# `<path:filename>` je dynamická část URL, která nám umožní specifikovat název souboru.
@app.route('/result/<path:filename>')
def serve_result(filename):
    """
    Tato funkce umožňuje uživateli stáhnout si vygenerovaný JSON soubor.
    """
    # `send_from_directory` bezpečně poskytne soubor z adresáře `RESULT_FOLDER`.
    return send_from_directory(app.config['RESULT_FOLDER'], filename)

@app.route('/get_models', methods=['GET'])
def get_models():
    """Vrátí seznam dostupných modelů s jejich popisy a cenami."""
    available_models = {
        model: {"description": desc, "prices": config.CENY_MODELU.get(model, {})}
        for model, desc in config.MODEL_DESCRIPTIONS.items()
    }
    return jsonify(available_models)

@app.route('/estimate_cost', methods=['POST'])
def estimate_cost():
    """
    Odhadne počet tokenů a cenu pro zadaný dotaz v reálném čase.
    Tento odhad je pouze pro samotný text dotazu, bez započítání kontextu z databáze.
    Pro modely, které nepodporují API `countTokens` (jako `gemini-1.0-pro`), použije heuristiku.
    """
    data = request.json
    query = data.get('query')
    model_name = data.get('model', next(iter(config.MODEL_DESCRIPTIONS)))

    if not query:
        return jsonify({"input_tokens": 0, "cost_usd": "0.00000000", "note": ""})

    input_tokens = 0
    note = ""

    try:
        # Speciální případ pro modely, které nepodporují countTokens API
        if model_name == "gemini-1.0-pro":
            # Heuristika: 1 token je zhruba 4 znaky. Je to hrubý odhad.
            input_tokens = len(query) // 4
            note = "Poznámka: Pro model gemini-1.0-pro se používá odhad tokenů (1 token ≈ 4 znaky). Celková cena bude zahrnovat i tokeny za kontext a odpověď."
        else:
            # Pro ostatní modely se pokusíme získat přesný počet tokenů
            llm = ChatGoogleGenerativeAI(model=model_name, temperature=0)
            input_tokens = llm.get_num_tokens(query)
            note = "Poznámka: Toto je odhad pouze pro text vašeho dotazu. Celková cena bude zahrnovat i tokeny za kontext a za odpověď modelu."

        # Výpočet nákladů se VŽDY řídí ceníkem v config.py.
        cost = vypocitat_naklady(model_name, total_tokens=input_tokens)
        
        return jsonify({
            "input_tokens": input_tokens,
            "cost_usd": f"{cost:.8f}",
            "note": note
        })

    except Exception as e:
        # Pokud i standardní metoda selže, vrátíme chybu.
        error_message = str(e)
        print(f"Chyba při odhadu tokenů pro model '{model_name}': {error_message}")
        
        # Zobrazíme uživateli srozumitelnou chybu
        user_friendly_error = f"Chyba odhadu: API nepodporuje počítání tokenů pro model '{model_name}'. Zkuste jiný model pro přesný odhad."
        if "is not found for API version" in error_message or "does not support countTokens" in error_message:
             return jsonify({"error": user_friendly_error}), 400
        
        return jsonify({"error": error_message}), 500

@app.route('/ask', methods=['POST'])
def ask():
    """
    API koncový bod pro pokládání dotazů RAG systému.
    """
    data = request.json
    query = data.get('query')
    model_name = data.get('model', next(iter(config.MODEL_DESCRIPTIONS)))

    rag_chain = get_or_create_rag_chain(model_name)
    if rag_chain is None:
        return jsonify({"error": f"RAG systém pro model {model_name} není a nepodařilo se ho inicializovat."}), 503

    if not query:
        return jsonify({"error": "Nebyl poskytnut žádný dotaz."}), 400

    print(f"Přijat dotaz pro RAG (model: {model_name}): {query}")
    response = ask_question(rag_chain, query, model_name=model_name)
    
    # Zkontrolujeme, zda odpověď neobsahuje chybu
    if "error" in response:
        return jsonify(response), 500

    # Vracíme výsledek včetně statistik
    return jsonify({
        "answer": response.get('result', "Nepodařilo se získat odpověď."),
        "usage": response.get('usage', {})
    })

# --- Hlavní spouštěcí blok ---
if __name__ == '__main__':
    # RAG systém se inicializuje výše při načtení modulu.
    # Zde jen spustíme Flask server.
    app.run(debug=True)
