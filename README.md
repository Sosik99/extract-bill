# 🤖 AI Nástroj na Extrakci Dat z Účtenek 🧾

Tento projekt je multifunkční nástroj napsaný v **Pythonu**, který kombinuje sílu umělé inteligence pro zpracování dokumentů. Umožňuje:

1.  **📸 Extrakci dat z obrázků účtenek** – Převede fotku účtenky na strukturovaná data ve formátu **JSON** pomocí AI modelu **Google Gemini**.
2.  **🗃️ Ukládání a správu** – Automaticky ukládá extrahovaná data pro pozdější použití.
3.  **💬 Dotazování nad daty (RAG)** – Umožňuje pokládat dotazy v přirozeném jazyce nad všemi zpracovanými účtenkami pomocí **RAG systému**, který také využívá Google Gemini.

Aplikace nabízí dvě rozhraní pro maximální flexibilitu:
*   **🌐 Grafické rozhraní (GUI)** ve webovém prohlížeči.
*   **⌨️ Rozhraní pro příkazový řádek (CLI)** pro hromadné zpracování.

---

## ⚙️ Požadavky

Než začnete, ujistěte se, že máte nainstalováno:

*   **🐍 Python** (verze 3.9 nebo novější).
    *   Můžete ho stáhnout z [python.org](https://www.python.org/downloads/).
    *   **Důležité:** Během instalace zaškrtněte políčko **"Add Python to PATH"**.

---

## 🚀 Postup Zprovoznění (Kroky pro Terminál)

Následující kroky vás provedou kompletním nastavením a spuštěním projektu.

### Krok 1: 🔑 Vytvoření souboru s API klíčem

Tento projekt vyžaduje API klíč od **Google AI Studio** pro přístup k modelu Gemini.

1.  V hlavním adresáři projektu vytvořte soubor s názvem `api_key.txt`.
2.  Vložte do něj svůj Google API klíč. V souboru nesmí být nic jiného.

### Krok 2: 📦 Instalace Potřebných Knihoven

Otevřete si terminál (např. **PowerShell** nebo **Příkazový řádek**) v adresáři projektu a zkopírujte do něj následující příkaz. Tento příkaz si přečte soubor `requirements.txt` a automaticky nainstaluje všechny potřebné knihovny.

```shell
pip install -r requirements.txt
```

### Krok 3: ▶️ Spuštění Aplikace

Po úspěšné instalaci knihoven můžete aplikaci spustit. Zkopírujte do terminálu tento příkaz:

```shell
python main.py
```

Po spuštění se v terminálu objeví hlavní menu, kde si můžete vybrat, kterou část aplikace chcete použít:

*   **1: 🌐 Grafické rozhraní v prohlížeči (GUI)**
    *   Spustí webový server a otevře aplikaci ve vašem výchozím prohlížeči.
*   **2: ⌨️ Rozhraní v příkazovém řádku (CLI)**
    *   Spustí nástroj pro dávkové zpracování všech účtenek v adresáři `example/`.
*   **3: 💬 Spustit RAG systém**
    *   Spustí interaktivní konzoli, kde se můžete ptát na obsah vašich účtenek.
*   **0: 🚪 Ukončit**
    *   Bezpečně ukončí program.

---
