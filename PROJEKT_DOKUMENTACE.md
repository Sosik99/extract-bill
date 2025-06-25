# 📖 Projekt: AI Extraktor Dat a RAG Systém

Tento dokument poskytuje podrobný technický popis projektu, jeho architektury, jednotlivých komponent a jejich logiky.

---

## 🚀 1. Celkový přehled

Cílem projektu je vytvořit multifunkční nástroj, který využívá umělou inteligenci (konkrétně modely **Google Gemini**) pro dva hlavní účely:

1.  **🧾 Extrakce dat z obrázků účtenek**: Nástroj dokáže analyzovat obrázky účtenek a převést z nich veškeré informace do strukturovaného formátu `JSON`.
2.  **❓ Dotazování nad extrahovanými daty (RAG)**: Po extrakci dat je možné se na ně ptát v přirozeném jazyce (česky). Systém využívá techniku **RAG (Retrieval-Augmented Generation)**, aby našel relevantní informace v uložených JSON souborech a na jejich základě zformuloval přesnou odpověď.

Aplikace je navržena tak, aby byla flexibilní a uživatelsky přívětivá. Nabízí tři hlavní režimy použití:
-   **🖥️ Grafické uživatelské rozhraní (GUI)**: Pohodlné webové rozhraní pro nahrávání účtenek a pokládání dotazů.
-   **⌨️ Rozhraní příkazového řádku (CLI)**: Pro dávkové zpracování účtenek přímo z terminálu.
-   **🤖 Samostatný RAG systém v CLI**: Interaktivní konzole pro přímé dotazování na databázi znalostí.

> **💡 Klíčová vlastnost**: Aplikace aktivně monitoruje počet spotřebovaných **tokenů** při komunikaci s AI a na základě interního ceníku modelů Gemini vypočítává **odhadované náklady v USD**, což dává uživateli plnou kontrolu nad výdaji.

---

## 📂 2. Struktura projektu

Projekt je organizován do následujících souborů a adresářů:

```
.
├── 🔑 api_key.txt             # Konfigurační soubor pro uložení Google API klíče.
├── 🌐 app.py                  # Backend webové aplikace (Flask). Obsahuje API endpointy.
├── 📄 extract_bill_json.py    # Jádrová logika pro extrakci dat z obrázků účtenek.
├── ▶️ main.py                 # Hlavní spouštěcí skript, který zobrazuje menu pro výběr režimu.
├── 🧠 rag.py                  # Implementace RAG systému pro dotazování.
├── 📦 requirements.txt        # Seznam Python knihoven potřebných pro běh projektu.
├── 📘 README.md               # Základní uživatelská příručka pro rychlé zprovoznění.
├── 📖 PROJEKT_DOKUMENTACE.md  # Tato podrobná technická dokumentace.
|
├── 🖼️ example/                # Adresář s ukázkovými obrázky účtenek.
├── 🗂️ faiss_index_google/     # Uložená vektorová databáze pro RAG systém.
├── 📈 result/                 # Adresář pro ukládání výsledných JSON souborů a reportu o spotřebě.
│   ├── report_spotreby.csv # CSV soubor s historií zpracování a náklady.
│   └── ...                 # JSON soubory extrahované z účtenek.
|
├── 🌐 templates/
│   └── index.html          # HTML šablona pro webové rozhraní (GUI).
|
└── 📤 uploads/                # Dočasný adresář pro nahrávané soubory z webového rozhraní.
```

---

## ⚙️ 3. Detailní popis souborů

### `▶️ main.py`

-   **Účel**: Hlavní vstupní bod aplikace. Jeho jedinou rolí je prezentovat uživateli jednoduché textové menu v terminálu a na základě jeho volby spustit příslušnou část aplikace.
-   **Logika**:
    1.  Po spuštění (`python main.py`) zobrazí menu s volbami:
        -   `1:` Spustit GUI (webovou aplikaci).
        -   `2:` Spustit CLI pro extrakci dat.
        -   `3:` Spustit RAG systém v CLI.
        -   `0:` Ukončit program.
    2.  Načte vstup od uživatele.
    3.  Podle volby importuje a zavolá příslušnou funkci z `app.py`, `extract_bill_json.py` nebo `rag.py`.
    4.  Při startu je zakomentováno mazání adresáře `uploads`, aby se předešlo nechtěné ztrátě dat při restartu serveru.

### `🌐 app.py`

-   **Účel**: Backend pro webové rozhraní (GUI), postavený na mikrorámci **Flask**. Zajišťuje veškerou komunikaci mezi frontendem (prohlížečem) a jádrovou logikou aplikace.
-   **Klíčové komponenty**:
    -   **Inicializace Flasku**: Vytvoření instance aplikace a nastavení konfigurace (cesty k adresářům `uploads` a `result`).
    -   **Správa RAG chainů**: Proměnná `global_rag_chains` a funkce `get_or_create_rag_chain()` slouží jako *cache*. Drží si již vytvořené RAG "chainy" pro různé AI modely, aby se nemusely nákladně inicializovat při každém dotazu.
    -   **API Endpointy (Routes)**:
        -   `@app.route('/')`: Zobrazí hlavní stránku `index.html`.
        -   `@app.route('/process', methods=['POST'])`: Zpracovává nahrávání souborů s účtenkami.
            -   Přijme soubory a zvolenou metodu zpracování z webového formuláře.
            -   Uloží soubory do unikátního dočasného adresáře.
            -   Zavolá příslušnou funkci z `extract_bill_json.py` (`process_individually` nebo `process_in_batch`).
            -   Vrátí výsledky (včetně nákladů) ve formátu JSON zpět do prohlížeče.
        -   `@app.route('/get_models', methods=['GET'])`: Poskytuje frontendu seznam dostupných AI modelů, jejich popisů a cen. Tyto informace načítá z `rag.py` a `extract_bill_json.py`.
        -   `@app.route('/estimate_cost', methods=['POST'])`: V reálném čase odhaduje náklady na dotaz, který uživatel píše do RAG pole. Spočítá počet tokenů ve vstupním textu a pomocí funkce `vypocitat_naklady` určí cenu.
        -   `@app.route('/ask', methods=['POST'])`: Přijme dotaz a název modelu z RAG formuláře.
            -   Získá (nebo vytvoří) příslušný RAG chain.
            -   Zavolá funkci `ask_question` z `rag.py`.
            -   Vrátí odpověď a detailní statistiky o spotřebě (tokeny, cena) jako JSON.
        -   `@app.route('/result/<path:filename>')`: Umožňuje uživateli stáhnout si vygenerovaný JSON soubor.

### `🧠 rag.py`

-   **Účel**: Implementuje kompletní logiku pro **Retrieval-Augmented Generation (RAG)**. Tento skript je zodpovědný za vytvoření vektorové databáze, její prohledávání a generování odpovědí na základě nalezených informací.
-   **Klíčové komponenty**:
    -   **`MODEL_DESCRIPTIONS`**: Slovník obsahující textové popisy jednotlivých AI modelů, které se zobrazují uživateli v GUI i CLI.
    -   **`UsageCallback`**: Vlastní třída (callback), která se "zahákne" do procesu volání AI modelu v LangChainu a zachytí metadata o spotřebě tokenů, pokud je model poskytne.
    -   **`load_documents_from_json()`**: Načte všechny `.json` soubory z adresáře `result/` a připraví je pro zpracování.
    -   **`create_vector_store()`**:
        -   Vezme načtené dokumenty a rozdělí je na menší, stravitelnější části (`RecursiveCharacterTextSplitter`).
        -   Pomocí `GoogleGenerativeAIEmbeddings` převede textové části na **vektory** (číselné reprezentace).
        -   Uloží tyto vektory do databáze **FAISS**, která umožňuje extrémně rychlé vyhledávání podobnosti.
        -   Databázi uloží na disk do adresáře `faiss_index_google/`, aby se nemusela při každém spuštění vytvářet znovu.
    -   **`create_rag_chain()`**: Sestaví samotný RAG "řetězec" pomocí LangChainu.
        -   **Retriever**: Komponenta, která prohledává FAISS databázi.
        -   **Prompt Template**: Šablona, která instruuje AI model, jak má pracovat s nalezeným kontextem a uživatelovým dotazem.
        -   **LLM**: Samotný jazykový model (`ChatGoogleGenerativeAI`).
        -   Spojí tyto části do `create_retrieval_chain`, která automatizuje celý proces: přijetí dotazu -> nalezení relevantních dokumentů -> vložení do promptu -> vygenerování odpovědi.
    -   **`get_rag_chain()`**: Orchestruje inicializaci. Zkontroluje, zda již existuje uložená FAISS databáze. Pokud ano, načte ji. Pokud ne, vytvoří ji voláním `create_vector_store()`. Poté vrátí hotový RAG chain.
    -   **`ask_question()`**:
        -   Přijme dotaz, model a existující chain.
        -   Spustí chain s `UsageCallback` pro zachycení statistik.
        -   **Fallback logika**: Pokud model nevrátí statistiky o spotřebě, funkce sama odhadne počet tokenů na základě délky vstupu a výstupu. Tím je zajištěno, že uživatel vždy dostane alespoň odhad nákladů.
        -   Zavolá `vypocitat_naklady` pro finální cenu.
        -   Vrátí strukturovanou odpověď obsahující text odpovědi, nalezené zdrojové dokumenty a detailní statistiky o použití.
    -   **`run_rag_cli()`**: Spustí interaktivní smyčku v terminálu, kde si uživatel nejprve vybere model a poté může pokládat dotazy.

### `📄 extract_bill_json.py`

-   **Účel**: Obsahuje logiku pro zpracování obrázků účtenek a komunikaci s Google Gemini API za účelem extrakce dat.
-   **Klíčové komponenty**:
    -   **`CENY_MODELU`**: Centrální slovník, který definuje ceny za 1 milion vstupních a výstupních tokenů pro různé modely Gemini. Je to jediný zdroj pravdy o cenách v celém projektu.
    -   **`vypocitat_naklady()`**: Klíčová funkce pro výpočet nákladů. Přijímá název modelu a počet tokenů (rozlišené na vstupní a výstupní) a na základě ceníku vrací cenu v USD.
    -   **`ulozit_report_spotreby()`**: Zapisuje záznamy o každém zpracování do souboru `result/report_spotreby.csv`. Ukládá čas, název souboru, spotřebované tokeny, náklady a status operace.
    -   **`nacti_api_klic()`**: Bezpečně načítá API klíč ze souboru `api_key.txt`.
    -   **Zpracovatelské funkce**:
        -   `zpracovat_jeden_obrazek_s_metrami()`: Zpracuje jeden obrázek, pošle ho Gemini API s detailním promptem, který instruuje AI, jak extrahovat data. Získá přesné statistiky o spotřebě a uloží výsledek.
        -   `zpracovat_davku_jednotlivo()`: Projde všechny obrázky v adresáři a volá pro každý z nich `zpracovat_jeden_obrazek_s_metrami`.
        -   `zpracovat_jednu_davku()`: Zpracuje více obrázků najednou v jediném volání API. Je to rychlejší a levnější, ale AI vrací náklady a tokeny jen pro celou dávku dohromady, nikoli pro jednotlivé soubory.
        -   `zpracovat_davku_uctenek()`: Rozdělí obrázky na menší dávky a volá pro ně `zpracovat_jednu_davku`.
    -   **`run_cli()`**: Spustí interaktivní menu v terminálu pro výběr metody extrakce dat (jednotlivě vs. dávkově).

### `🌐 templates/index.html`

-   **Účel**: Frontend webové aplikace. Jedná se o HTML soubor s CSS styly a JavaScriptem, který se zobrazuje v prohlížeči.
-   **Struktura**:
    -   **Hlavička**: Odkazy na **Bootstrap CSS** pro základní vzhled.
    -   **Sekce pro nahrávání účtenek**: Formulář (`<form>`) s polem pro výběr souborů (`<input type="file">`), výběrem metody zpracování (`<select>`) a tlačítkem pro spuštění.
    -   **Sekce pro RAG**:
        -   Rozbalovací seznam (`<select>`) pro výběr AI modelu.
        -   Textové pole (`<input type="text">`) pro zadání dotazu.
        -   Tlačítko pro odeslání.
        -   Kontejnery pro zobrazení odpovědi, statistik a odhadu nákladů.
-   **JavaScript logika**:
    -   **Obsluha nahrávání**: Po odeslání formuláře pro extrakci dat JavaScript pomocí `fetch()` pošle data na backend (`/process`), zobrazí načítací kolečko a po obdržení odpovědi dynamicky vykreslí výsledky do stránky.
    -   **Dynamické načítání modelů**: Při načtení stránky si `fetch()` zavolá endpoint `/get_models` a naplní výběrový seznam (`select`) dostupnými AI modely.
    -   **Odhad nákladů v reálném čase**: Při každém stisku klávesy v poli pro RAG dotaz se zavolá endpoint `/estimate_cost`, který vrátí odhadovaný počet tokenů a cenu, jež se ihned zobrazí pod polem.
    -   **Pokládání RAG dotazu**: Po kliknutí na "Odeslat" se dotaz a vybraný model pošlou na endpoint `/ask`. Po přijetí odpovědi se dynamicky zobrazí text odpovědi a pod ním detailní statistiky o spotřebě.
    -   **Diagnostické logování**: Odpovědi ze serveru se vypisují do konzole prohlížeče (`console.log`), což usnadňuje ladění.

### `📦 requirements.txt`

-   **Účel**: Definuje všechny externí Python knihovny, které projekt potřebuje. Umožňuje snadnou instalaci všech závislostí jediným příkazem: `pip install -r requirements.txt`.
-   **Obsah**:
    -   `Flask`: Pro webový server.
    -   `google-generativeai`: Oficiální Google knihovna pro přímou práci s Gemini.
    -   `langchain`, `langchain-community`, `langchain-google-genai`: Komponenty frameworku LangChain pro stavbu RAG systému.
    -   `faiss-cpu`: Knihovna pro vektorovou databázi.
    -   `jq`: Nástroj pro práci s JSON, vyžadovaný `JSONLoaderem` v LangChainu.

---

## 🛠️ 4. Konfigurace a spuštění

1.  **🔑 API klíč**: Nejdůležitějším krokem je vytvoření souboru `api_key.txt` v kořenovém adresáři projektu a vložení platného Google API klíče.
2.  **📦 Instalace**: Spuštění `pip install -r requirements.txt` v terminálu.
3.  **▶️ Spuštění**: Spuštění `python main.py` a výběr požadovaného režimu z menu.

---

## 💡 5. Klíčové koncepty

### **RAG (Retrieval-Augmented Generation)**

RAG je technika, která kombinuje **vyhledávání informací** s **generováním textu**. Místo toho, aby se AI spoléhala jen na své obecné znalosti, nejprve prohledá specifickou databázi (v našem případě extrahované JSONy) a nalezené relevantní úryvky použije jako kontext pro generování odpovědi. Tím se výrazně zvyšuje přesnost a relevance odpovědí a omezuje se "halucinování" AI.

### **Sledování nákladů a tokenizace**

Jazykové modely nepracují s textem přímo, ale s **"tokeny"**, což jsou části slov. Každé volání API je zpoplatněno na základě počtu vstupních a výstupních tokenů. Tento projekt pečlivě sleduje spotřebu:
-   **✅ Přesné měření**: Kde je to možné (jednotlivé zpracování, RAG), získáváme přesná data o spotřebě přímo z odpovědi API.
-   **🤔 Odhad (Fallback)**: Pokud API data neposkytne, systém odhadne počet tokenů z délky textu, aby uživatel měl vždy představu o nákladech.
-   **💰 Ceník**: Všechny výpočty vycházejí z centrálního ceníku `CENY_MODELU` v `extract_bill_json.py`.
