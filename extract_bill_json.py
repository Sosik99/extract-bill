import os
import json
import csv
from datetime import datetime
import fitz  # Import PyMuPDF
from google import genai
from google.genai import types
import config  # Importujeme centrální konfigurační soubor


def vypocitat_naklady(model_name, input_tokens=0, output_tokens=0, total_tokens=0):
    """
    Vypočítá náklady na základě počtu tokenů a modelu.
    Prioritně používá `input_tokens` a `output_tokens`.
    Pokud nejsou k dispozici, použije `total_tokens` pro odhad.
    
    Args:
        model_name (str): Název modelu.
        input_tokens (int): Počet vstupních tokenů.
        output_tokens (int): Počet výstupních tokenů.
        total_tokens (int): Celkový počet tokenů (použito jako fallback).
        
    Returns:
        float: Náklady v USD.
    """
    # Jako výchozí použijeme ceny pro model s nejlepším poměrem cena/výkon
    default_model = next(iter(config.CENY_MODELU))
    default_prices = config.CENY_MODELU.get(default_model)
    ceny = config.CENY_MODELU.get(model_name, default_prices)
    
    cena_vstup = ceny.get("vstup", default_prices["vstup"])
    cena_vystup = ceny.get("vystup", default_prices["vystup"])

    # Preferovaný způsob: přesný výpočet s rozlišením vstupu a výstupu
    if input_tokens > 0 or output_tokens > 0:
        naklady_input = (input_tokens / 1_000_000) * cena_vstup
        naklady_output = (output_tokens / 1_000_000) * cena_vystup
        naklady_usd = naklady_input + naklady_output
    # Fallback: odhad z celkového počtu tokenů
    elif total_tokens > 0:
        # Pro odhad použijeme průměrnou cenu, je to spravedlivější než jen cena vstupu.
        prumerna_cena = (cena_vstup + cena_vystup) / 2
        naklady_usd = (total_tokens / 1_000_000) * prumerna_cena
    else:
        naklady_usd = 0.0
        
    return naklady_usd

def ulozit_report_spotreby(data_reportu):
    """
    Uloží report o spotřebě tokenů a nákladech do CSV souboru definovaného v configu.
    
    Args:
        data_reportu: Seznam s daty ve formátu [čas, soubor, tokeny, náklady_usd, status]
    """
    report_soubor = config.REPORT_FILE
    
    # Zkontrolujeme, zda soubor existuje
    soubor_existuje = os.path.exists(report_soubor)
    
    with open(report_soubor, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # Napíšeme hlavičku jen pokud soubor neexistuje
        if not soubor_existuje:
            writer.writerow(['cas', 'soubor', 'tokeny', 'naklady_usd', 'status', 'poznamka'])
        
        # Napíšeme data
        for radek in data_reportu:
            writer.writerow(radek)

def nacti_api_klic(soubor=config.API_KEY_FILE):
    """Bezpečně načte API klíč z textového souboru definovaného v configu."""
    try:
        with open(soubor, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        print(f"Chyba: Soubor '{soubor}' s API klíčem nebyl nalezen.")
        print("Prosím, vytvořte jej a vložte do něj svůj API klíč.")
        return None

def zpracovat_davku_uctenek(adresar=config.EXAMPLE_DIR, return_results=False):
    """
    Zpracuje obrázky účtenek v dávkách zadané velikosti.
    
    Args:
        adresar: Adresář s obrázky (výchozí z configu)
        return_results: Pokud True, vrací výsledky jako pole slovníků
    """
    if return_results:
        all_results = []

    print(f"Hledám soubory v adresáři '{adresar}'...")
    
    # Najdeme všechny soubory s podporovanými příponami z configu
    soubory_ke_zpracovani = []
    for soubor in os.listdir(adresar):
        if soubor.lower().endswith(tuple(config.ALLOWED_EXTENSIONS)):
            cesta_k_souboru = os.path.join(adresar, soubor)
            soubory_ke_zpracovani.append(cesta_k_souboru)
    
    if not soubory_ke_zpracovani:
        print(f"V adresáři '{adresar}' nebyly nalezeny žádné podporované soubory.")
        return
    
    print(f"Nalezeno {len(soubory_ke_zpracovani)} souborů: {[os.path.basename(s) for s in soubory_ke_zpracovani]}")
    print(f"Zpracování v dávkách po {config.BATCH_SIZE} souborech...")
    
    # Načteme API klíč
    print("Načítám API klíč...")
    api_key = nacti_api_klic()
    if not api_key:
        return
    
    # Inicializujeme klienta
    print("Inicializuji Google AI klienta...")
    client = genai.Client(api_key=api_key)
    model = next(iter(config.MODEL_DESCRIPTIONS)) # Použijeme první model z configu jako výchozí
    
    # Zpracujeme obrázky v dávkách
    celkem_zpracovano = 0
    
    for i in range(0, len(soubory_ke_zpracovani), config.BATCH_SIZE):
        davka = soubory_ke_zpracovani[i:i + config.BATCH_SIZE]
        cislo_davky = (i // config.BATCH_SIZE) + 1
        celkem_davek = (len(soubory_ke_zpracovani) + config.BATCH_SIZE - 1) // config.BATCH_SIZE
        
        print(f"\n--- Zpracovávám dávku {cislo_davky}/{celkem_davek} ({len(davka)} souborů) ---")
        
        # Zpracujeme jednu dávku
        batch_results = zpracovat_jednu_davku(davka, client, model, return_results)
        if return_results:
            all_results.extend(batch_results)
        elif batch_results:
            celkem_zpracovano += len(davka)
    
    if return_results:
        return all_results

    print(f"\nHotovo! Celkem zpracováno {celkem_zpracovano} souborů z {len(soubory_ke_zpracovani)}.")

def zpracovat_jednu_davku(davka_soubory, client, model, return_results=False):
    """
    Zpracuje jednu dávku souborů (obrázků nebo PDF).
    
    Returns:
        Pokud return_results=True, vrací pole slovníků, jinak (úspěch: bool, ...)
    """
    if return_results:
        results_list = []

    # Připravíme prompt pro dávkové zpracování
    davkovy_prompt = """# ROLE A CÍL
Jsi expertní systém pro dávkovou extrakci dat z více dokumentů najednou. Tvým úkolem je analyzovat VŠECHNY přiložené obrázky. Tyto obrázky mohou být buď samostatné soubory, nebo stránky z PDF dokumentů. Pro KAŽDÝ obrázek (stránku) musíš extrahovat veškeré informace a vytvořit pro něj samostatný JSON objekt. Všechny tyto JSON objekty pak zabal do jednoho hlavního JSON pole.

# METODIKA PRÁCE
1. **Iteruj přes obrázky/stránky:** Postupně projdi každý obrázek/stránku, který ti byl poslán.
2. **Analyzuj každý obrázek samostatně:** Pro každý jednotlivý obrázek aplikuj následující logiku:
   - Zmapuj dokument a identifikuj bloky informací
   - Přesně přepisuj všechna data
   - Vytvoř logicky strukturovaný JSON objekt
   - Přidej identifikátor: Do JSON objektu přidej klíč "obrazek_index" s pořadovým číslem obrázku (0, 1, 2...), jak jsi je obdržel.
3. **Zkompletuj výstup:** Vytvoř pole JSON objektů ve formátu: [{"obrazek_index": 0, "data": {...}}, {"obrazek_index": 1, "data": {...}}, ...]


# ZÁVĚREČNÝ POKYN
Aplikuj tuto metodiku na VŠECHNY přiložené obrázky/stránky. Vytvoř JEDEN JSON výstup obsahující pole objektů, jeden pro každý obrázek/stránku."""
    
    # Připravíme obsah pro API
    contents = [types.Content(role="user", parts=[types.Part.from_text(text=davkovy_prompt)])]
    
    # Seznam pro mapování indexu výsledku zpět na původní soubor a stránku
    mapovani_vystupu = []

    # Přidáme všechny soubory do jednoho requestu
    print("Načítám soubory v dávce...")
    for soubor_cesta in davka_soubory:
        try:
            pripona_s_teckou = os.path.splitext(soubor_cesta)[1].lower()

            if pripona_s_teckou.lstrip('.') in config.ALLOWED_IMAGE_EXTENSIONS:
                with open(soubor_cesta, "rb") as f:
                    soubor_data = f.read()
                
                if pripona_s_teckou in ['.jpg', '.jpeg']:
                    mime_type = "image/jpeg"
                else: # .png, .gif, .bmp, .webp
                    mime_type = "image/png"
                
                contents[0].parts.append(types.Part.from_bytes(mime_type=mime_type, data=soubor_data))
                mapovani_vystupu.append({"soubor": os.path.basename(soubor_cesta), "strana": 1})
                print(f"  - Přidán obrázek: {os.path.basename(soubor_cesta)}")

            elif pripona_s_teckou.lstrip('.') in config.ALLOWED_PDF_EXTENSIONS:
                print(f"  - Zpracovávám PDF: {os.path.basename(soubor_cesta)}")
                doc = fitz.open(soubor_cesta)
                for cislo_strany, page in enumerate(doc):
                    pix = page.get_pixmap()
                    img_bytes = pix.tobytes("png")
                    contents[0].parts.append(types.Part.from_bytes(mime_type="image/png", data=img_bytes))
                    mapovani_vystupu.append({"soubor": os.path.basename(soubor_cesta), "strana": cislo_strany + 1})
                    print(f"    - Přidána strana {cislo_strany + 1}/{len(doc)}")
                doc.close()
            
        except Exception as e:
            print(f"Chyba při načítání souboru '{soubor_cesta}': {e}")
            continue
    
    if len(contents[0].parts) == 1: # Jen prompt, žádné soubory
        print("Nebyly nalezeny žádné platné soubory ke zpracování v dávce.")
        return [] if return_results else False

    print(f"\nOdesílám dávkový požadavek s {len(mapovani_vystupu)} obrázky/stránkami a čekám na odpověď...")
    
    try:
        response = client.models.generate_content(model=model, contents=contents)
        
        # Získáme počet tokenů a vypočítáme náklady
        celkove_tokeny = response.usage_metadata.total_token_count
        celkove_naklady = vypocitat_naklady(model, total_tokens=celkove_tokeny)
        
        print(f"Odpověď přijata. Celkem tokenů: {celkove_tokeny}, odhadované náklady: ${celkove_naklady:.4f} USD.")
        
        # Zpracujeme odpověď
        data_reportu = []
        
        try:
            # Odstraníme ```json a ``` z odpovědi
            cleaned_response = response.text.strip().replace("```json", "").replace("```", "").strip()
            vysledne_jsony = json.loads(cleaned_response)
            
            print(f"Podařilo se extrahovat {len(vysledne_jsony)} JSON objektů.")
            
            for item in vysledne_jsony:
                index = item.get("obrazek_index")
                json_data = item.get("data")
                
                if index is None or json_data is None:
                    print(f"Varování: Chybí 'obrazek_index' nebo 'data' v jednom z objektů: {item}")
                    continue

                if index < len(mapovani_vystupu):
                    info_o_souboru = mapovani_vystupu[index]
                    puvodni_soubor = info_o_souboru["soubor"]
                    strana = info_o_souboru.get("strana")

                    # Vytvoříme název výstupního souboru
                    nazev_bez_pripony = os.path.splitext(puvodni_soubor)[0]
                    if strana and len(mapovani_vystupu) > 1: # Přidáme stranu jen pokud je víc obrázků/stran
                        vystupni_soubor = f"{nazev_bez_pripony}_strana_{strana}.json"
                    else:
                        vystupni_soubor = f"{nazev_bez_pripony}.json"
                    
                    cesta_k_vystupu = os.path.join(config.RESULT_DIR, vystupni_soubor)
                    
                    # Uložíme JSON
                    with open(cesta_k_vystupu, 'w', encoding='utf-8') as f:
                        json.dump(json_data, f, ensure_ascii=False, indent=4)
                    
                    print(f"  - Úspěšně uložen výsledek pro '{puvodni_soubor}' (strana {strana}) do '{vystupni_soubor}'")
                    
                    # Rozpočítáme náklady a tokeny na jednotlivé položky
                    tokeny_na_polozku = celkove_tokeny / len(vysledne_jsony) if vysledne_jsony else 0
                    naklady_na_polozku = celkove_naklady / len(vysledne_jsony) if vysledne_jsony else 0

                    if return_results:
                        results_list.append({
                            "soubor": puvodni_soubor, 
                            "strana": strana, 
                            "data": json_data,
                            "tokeny": f"{tokeny_na_polozku:.0f}",
                            "cost": naklady_na_polozku,
                            "status": "úspěch",
                            "json_soubor": vystupni_soubor
                        })
                    
                    # Přidáme záznam do reportu
                    data_reportu.append([
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        puvodni_soubor,
                        f"{tokeny_na_polozku:.0f}",
                        f"{naklady_na_polozku:.6f}",
                        "úspěch",
                        f"Zpracováno z dávky, strana {strana}"
                    ])
                else:
                    print(f"Varování: Model vrátil index {index}, který je mimo rozsah zpracovaných souborů ({len(mapovani_vystupu)}).")

        except json.JSONDecodeError:
            print("Chyba: Nepodařilo se dekódovat JSON z odpovědi modelu.")
            print("Odpověď modelu:", response.text)
            # Uložíme neúspěšný report pro celou dávku
            for soubor_info in mapovani_vystupu:
                data_reportu.append([
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    soubor_info["soubor"],
                    celkove_tokeny,
                    celkove_naklady,
                    "chyra",
                    "JSONDecodeError"
                ])
        except Exception as e:
            print(f"Došlo k neočekávané chybě při zpracování odpovědi: {e}")
            # Uložíme neúspěšný report pro celou dávku
            for soubor_info in mapovani_vystupu:
                 data_reportu.append([
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    soubor_info["soubor"],
                    celkove_tokeny,
                    celkove_naklady,
                    "chyra",
                    str(e)
                ])

        # Uložíme report o spotřebě
        if data_reportu:
            ulozit_report_spotreby(data_reportu)
            
        return results_list if return_results else True

    except types.generation_types.BlockedPromptException as e:
        print(f"Chyba: Požadavek byl zablokován z bezpečnostních důvodů. {e}")
    except Exception as e:
        print(f"Došlo k chybě při komunikaci s Google AI: {e}")

    # Pokud došlo k chybě, uložíme report a vrátíme neúspěch
    data_reportu = []
    for soubor_info in mapovani_vystupu:
        data_reportu.append([
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            soubor_info["soubor"],
            0,
            0,
            "chyra",
            "API Error"
        ])
    ulozit_report_spotreby(data_reportu)
    
    return [] if return_results else False


def zpracovat_davku_jednotlivo(adresar=config.EXAMPLE_DIR, return_results=False, with_metrics=True):
    """
    Zpracuje soubory v adresáři jeden po druhém.
    Tato metoda je pomalejší, ale poskytuje detailní metriky pro každý soubor zvlášť.
    
    Args:
        adresar (str): Adresář se soubory.
        return_results (bool): Zda vrátit výsledky jako seznam slovníků.
        with_metrics (bool): Zda počítat a ukládat metriky (tokeny, náklady).
    """
    soubory_ke_zpracovani = []
    for soubor in os.listdir(adresar):
        if soubor.lower().endswith(tuple(config.ALLOWED_EXTENSIONS)):
            cesta_k_souboru = os.path.join(adresar, soubor)
            soubory_ke_zpracovani.append(cesta_k_souboru)

    if not soubory_ke_zpracovani:
        print(f"V adresáři '{adresar}' nebyly nalezeny žádné podporované soubory.")
        return [] if return_results else None

    print(f"Nalezeno {len(soubory_ke_zpracovani)} souborů. Zpracovávám jednotlivě...")
    
    all_results = []
    for i, cesta_k_souboru in enumerate(soubory_ke_zpracovani):
        print(f"\n--- Zpracovávám soubor {i+1}/{len(soubory_ke_zpracovani)}: {os.path.basename(cesta_k_souboru)} ---")
        
        # `zpracovat_jeden_soubor` vrací tuple: (tokeny, náklady, status, chyba, json_soubor)
        tokeny, naklady, status, chyba, json_soubor = zpracovat_jeden_soubor(
            cesta_k_souboru,
            model_name=next(iter(config.MODEL_DESCRIPTIONS)),
            with_metrics=with_metrics,
            return_result=True # Vždy chceme strukturovaný výsledek
        )
        
        if return_results:
            # Převedeme tuple na slovník, který očekává frontend
            all_results.append({
                "soubor": os.path.basename(cesta_k_souboru),
                "tokeny": str(tokeny),  # Explicitní převod na string pro konzistenci
                "cost": naklady,
                "status": status,
                "chyba": chyba,
                "json_soubor": json_soubor
            })

    print("\nHotovo! Všechny soubory byly zpracovány jednotlivě.")
    if return_results:
        return all_results


def zpracovat_jeden_soubor(cesta_k_souboru, model_name=next(iter(config.MODEL_DESCRIPTIONS)), with_metrics=True, return_result=False):
    """
    Zpracuje jeden soubor (obrázek nebo PDF). V případě PDF zpracuje všechny jeho stránky.
    
    Args:
        cesta_k_souboru (str): Cesta k souboru k zpracování.
        model_name (str): Název modelu (volitelné, výchozí je první model z configu).
        with_metrics (bool): Zda počítat a ukládat metriky (tokeny, náklady).
        return_result (bool): Zda vrátit výsledek jako tuple.
        
    Returns:
        Pro obrázek: (tokeny, náklady, status, chyba, json_soubor)
        Pro PDF: (celkové_tokeny, celkové_náklady, status, chyba, základní_název_pro_výstupy)
    """
    api_key = nacti_api_klic()
    if not api_key:
        return 0, 0, "CHYBA", "API klíč nebyl nalezen.", None

    client = genai.Client(api_key=api_key)
    pripona_s_teckou = os.path.splitext(cesta_k_souboru)[1].lower()
    zakladni_nazev = os.path.splitext(os.path.basename(cesta_k_souboru))[0]

    if not os.path.exists(config.RESULT_DIR):
        os.makedirs(config.RESULT_DIR)

    prompt = """# ROLE A CÍL
Jsi autonomní systém pro inteligentní extrakci dat z dokumentů. Tvým úkolem je analyzovat přiložený obrázek (nebo stránku dokumentu), porozumět jeho struktuře a převést VŠECHNY informace do logicky uspořádaného formátu JSON. Každý dokument je jiný, proto se nespoléhej na pevně danou šablonu, ale na svou schopnost porozumět kontextu.

# METODIKA PRÁCE
1.  **Zmapuj Dokument:** Projdi si celý dokument a identifikuj vizuálně a logicky oddělené bloky informací (např. hlavička s prodejcem, seznam položek, souhrn plateb, detaily o transakci, daňový rozpis atd.).
2.  **Přesně Přepisuj:** Při čtení dat buď maximálně přesný.
3.  **Logicky Zoskupuj:** Vytvoř JSON, kde každá hlavní klíč reprezentuje jeden logický blok, který jsi identifikoval.
4.  **Sám Vytvoř Popisky:** Pro každý blok vytvoř popisný název a pro každou informaci uvnitř bloku vytvoř jasný a logický klíč (např. `sazba_dph`, `celkova_castka`, `nazev_polozky`).
5.  **Nezapomeň na Nic:** Ujisti se, že jsi přepsal VŠECHNY informace z dokumentu.

# ZÁVĚREČNÝ POKYN
Aplikuj tuto metodiku na přiložený dokument. Vytvoř logický, přehledný a kompletní JSON přepis. Začni generovat:"""

    # --- Zpracování PDF (všechny stránky) ---
    if pripona_s_teckou.lstrip('.') in config.ALLOWED_PDF_EXTENSIONS:
        print(f"  - Zpracovávám PDF: {os.path.basename(cesta_k_souboru)}")
        celkove_tokeny = 0
        celkove_naklady = 0.0
        chyba_v_prubehu = False
        
        try:
            doc = fitz.open(cesta_k_souboru)
            print(f"  - Nalezeno {len(doc)} stran.")

            for i, page in enumerate(doc):
                print(f"    - Zpracovávám stranu {i + 1}/{len(doc)}...")
                
                try:
                    pix = page.get_pixmap()
                    img_bytes = pix.tobytes("png")
                    
                    parts = [
                        types.Part.from_bytes(mime_type="image/png", data=img_bytes),
                        types.Part.from_text(prompt)
                    ]
                    contents = [types.Content(role="user", parts=parts)]

                    response = client.models.generate_content(model=model_name, contents=contents)
                    
                    tokeny_stranka = 0
                    naklady_stranka = 0.0

                    if with_metrics and hasattr(response, 'usage_metadata'):
                        tokeny_stranka = response.usage_metadata.total_token_count
                        naklady_stranka = vypocitat_naklady(model_name, total_tokens=tokeny_stranka)
                        celkove_tokeny += tokeny_stranka
                        celkove_naklady += naklady_stranka
                        print(f"      📊 Tokeny (strana): {tokeny_stranka}, Náklady (strana): ${naklady_stranka:.6f} USD")

                    nazev_vystupu = os.path.join(config.RESULT_DIR, f"{zakladni_nazev}_strana_{i+1}.json")
                    cisty_json_text = response.text.replace("```json", "").replace("```", "").strip()
                    
                    with open(nazev_vystupu, "w", encoding="utf-8") as f:
                        json.dump(json.loads(cisty_json_text), f, ensure_ascii=False, indent=4)

                    if with_metrics:
                        cas = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        data_reportu = [[cas, f"{os.path.basename(cesta_k_souboru)} (str. {i+1})", tokeny_stranka, naklady_stranka, 'USPECH_JEDNOTLIVO', f'Zpracována strana {i+1} z PDF']]
                        ulozit_report_spotreby(data_reportu)
                    
                    print(f"      ✅ Uloženo: {os.path.basename(nazev_vystupu)}")

                except Exception as e:
                    print(f"    ❌ Chyba při zpracování strany {i+1}: {e}")
                    chyba_v_prubehu = True
                    if with_metrics:
                        cas = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        data_reportu = [[cas, f"{os.path.basename(cesta_k_souboru)} (str. {i+1})", 0, 0.0, 'CHYBA', str(e)]]
                        ulozit_report_spotreby(data_reportu)
            
            doc.close()

        except Exception as e:
            print(f"❌ Chyba při otevírání nebo čtení PDF souboru: {e}")
            if return_result:
                return 0, 0.0, "CHYBA", str(e), zakladni_nazev
            return 0, 0.0

        status = "ČÁSTEČNÝ ÚSPĚCH" if chyba_v_prubehu else "ÚSPĚCH"
        print(f"\nPDF Zpracováno. Celkové tokeny: {celkove_tokeny}, Celkové náklady: ${celkove_naklady:.6f} USD. Status: {status}")
        if return_result:
            return celkove_tokeny, celkove_naklady, status, None, zakladni_nazev
        return celkove_tokeny, celkove_naklady

    # --- Zpracování obrázku (jeden soubor) ---
    elif pripona_s_teckou.lstrip('.') in config.ALLOWED_IMAGE_EXTENSIONS:
        print(f"  - Zpracovávám obrázek: {os.path.basename(cesta_k_souboru)}")
        try:
            with open(cesta_k_souboru, "rb") as f:
                soubor_data = f.read()
            
            if pripona_s_teckou in ['.jpg', '.jpeg']:
                mime_type = "image/jpeg"
            else:
                mime_type = "image/png"
            
            parts = [
                types.Part.from_bytes(mime_type=mime_type, data=soubor_data),
                types.Part.from_text(prompt)
            ]
            contents = [types.Content(role="user", parts=parts)]

            response = client.models.generate_content(model=model_name, contents=contents)
            
            tokeny = 0
            naklady_usd = 0.0

            if with_metrics and hasattr(response, 'usage_metadata'):
                tokeny = response.usage_metadata.total_token_count
                naklady_usd = vypocitat_naklady(model_name, total_tokens=tokeny)
                print(f"📊 Tokeny: {tokeny}, Náklady: ${naklady_usd:.6f} USD")
            
            nazev_vystupu = os.path.join(config.RESULT_DIR, f"{zakladni_nazev}.json")
            cisty_json_text = response.text.replace("```json", "").replace("```", "").strip()
            with open(nazev_vystupu, "w", encoding="utf-8") as f:
                json.dump(json.loads(cisty_json_text), f, ensure_ascii=False, indent=4)
            
            if with_metrics:
                cas = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                data_reportu = [[cas, os.path.basename(cesta_k_souboru), tokeny, naklady_usd, 'USPECH_JEDNOTLIVO', 'Zpracováno jednotlivě - přesné údaje']]
                ulozit_report_spotreby(data_reportu)
            
            print(f"✅ Uloženo: {os.path.basename(nazev_vystupu)}")
            if return_result:
                return tokeny, naklady_usd, "ÚSPĚCH", None, os.path.basename(nazev_vystupu)
            return tokeny, naklady_usd
            
        except Exception as e:
            print(f"❌ Chyba: {e}")
            if with_metrics:
                cas = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                data_reportu = [[cas, os.path.basename(cesta_k_souboru), 0, 0.0, 'CHYBA', str(e)]]
                ulozit_report_spotreby(data_reportu)
            if return_result:
                return 0, 0.0, "CHYBA", str(e), None
            return 0, 0.0
    
    # --- Nepodporovaný typ souboru ---
    else:
        error_msg = f"Nepodporovaný typ souboru: {pripona_s_teckou}"
        print(f"❌ Chyba: {error_msg}")
        if return_result:
            return 0, 0.0, "CHYBA", error_msg, None
        return 0, 0.0


def run_cli():
    """Spustí interaktivní rozhraní pro ovládání z příkazového řádku."""
    print("--- CLI Rozhraní pro Extrakci Dat z Účtenek ---")
    
    # Zkontrolujeme API klíč hned na začátku
    if not nacti_api_klic():
        return  # Funkce nacti_api_klic již vypíše chybovou hlášku

    while True:
        print("\nVyberte metodu zpracování:")
        print("1: Jednotlivě (s metrikami) - Pomalé, ale přesné sledování nákladů pro každý soubor.")
        print("2: Jednotlivě (základní) - Rychlejší, bez sledování nákladů.")
        print("3: Dávkově - Nejrychlejší, zpracuje všechny soubory najednou (náklady jsou za celou dávku).")
        print("0: Ukončit")

        volba = input("Zadejte svou volbu (1, 2, 3 nebo 0): ").strip()

        if volba == '1':
            print("\nSpouštím zpracování jednotlivě s metrikami...")
            zpracovat_davku_jednotlivo(adresar="example", return_results=False, with_metrics=True)
            break
        elif volba == '2':
            print("\nSpouštím základní zpracování jednotlivě...")
            zpracovat_davku_jednotlivo(adresar="example", return_results=False, with_metrics=False)
            break
        elif volba == '3':
            print("\nSpouštím dávkové zpracování...")
            zpracovat_davku_uctenek(adresar="example", return_results=False)
            break
        elif volba == '0':
            print("Ukončuji CLI rozhraní.")
            break
        else:
            print("Neplatná volba, zkuste to znovu.")
