# -*- coding: utf-8 -*-
"""
⚙️ Centrální konfigurační soubor pro celý projekt.

Tento soubor obsahuje všechna klíčová nastavení, jako jsou cesty k souborům,
názvy modelů, ceny a další parametry, aby bylo možné je snadno měnit z jednoho místa.
"""

import os

# --- Základní cesty projektu ---
# Definuje kořenový adresář projektu.
# Všechny ostatní cesty jsou odvozeny od této.
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# --- Adresáře ---
# Adresář pro dočasně nahrané soubory z webového rozhraní.
UPLOADS_DIR = os.path.join(PROJECT_ROOT, "uploads")
# Adresář pro výsledné JSON soubory a reporty.
RESULT_DIR = os.path.join(PROJECT_ROOT, "result")
# Adresář pro ukázkové obrázky účtenek.
EXAMPLE_DIR = os.path.join(PROJECT_ROOT, "example")
# Adresář pro uložení vektorové databáze FAISS.
FAISS_INDEX_DIR = os.path.join(PROJECT_ROOT, "faiss_index_google")
# Adresář pro HTML šablony.
TEMPLATES_DIR = os.path.join(PROJECT_ROOT, "templates")

# --- Soubory ---
# Soubor pro uložení Google API klíče.
API_KEY_FILE = os.path.join(PROJECT_ROOT, "api_key.txt")
# Soubor pro report o spotřebě a nákladech.
REPORT_FILE = os.path.join(RESULT_DIR, "report_spotreby.csv")

# --- Konfigurace AI modelů ---

# Popisy modelů pro zobrazení v GUI a CLI.
MODEL_DESCRIPTIONS = {
    "gemini-1.5-flash": "Rychlý a cenově dostupný model, ideální pro většinu běžných úkolů.",
    "gemini-1.0-pro": "Výkonný model vhodný pro složitější úlohy a extrakci dat.",
    "gemini-1.5-pro-latest": "Nejnovější a nejvýkonnější model pro nejnáročnější úkoly."
}

# Ceník modelů Gemini (v USD za 1 milion tokenů).
# Zdroj: https://ai.google.dev/pricing
CENY_MODELU = {
    "gemini-1.5-flash": {
        "vstup": 0.35,
        "vystup": 0.70
    },
    "gemini-1.0-pro": {
        "vstup": 0.50,
        "vystup": 1.50
    },
    "gemini-1.5-pro-latest": {
        "vstup": 3.50,
        "vystup": 10.50
    }
}

# --- Konfigurace pro zpracování souborů ---

# Podporované formáty obrázků (bez tečky).
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}
# Podporované formáty dokumentů (bez tečky).
ALLOWED_PDF_EXTENSIONS = {'pdf'}
# Všechny povolené formáty.
ALLOWED_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS.union(ALLOWED_PDF_EXTENSIONS)

# Velikost dávky pro zpracování účtenek v CLI.
BATCH_SIZE = 10

# --- Konfigurace pro RAG ---

# Název embedding modelu pro RAG.
EMBEDDING_MODEL_NAME = "models/text-embedding-004"

# --- Konfigurace pro extrakci dat ---
# Model, který se má použít pro extrakci strukturovaných dat z účtenek.
EXTRACTION_MODEL = "gemini-1.5-flash"
