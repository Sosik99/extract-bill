import os
import json
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import JSONLoader
from langchain.callbacks.base import BaseCallbackHandler
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains.retrieval import create_retrieval_chain
from langchain_core.prompts import ChatPromptTemplate
from google.api_core import exceptions as google_exceptions

# --- Importy z naší vlastní logiky ---
import config  # Importujeme centrální konfigurační soubor
from extract_bill_json import vypocitat_naklady, nacti_api_klic

# --- Načtení a nastavení API klíče ---
# Načteme klíč pomocí naší centralizované funkce a nastavíme ho jako proměnnou prostředí,
# protože knihovny LangChain a Google ji automaticky hledají.
api_key = nacti_api_klic(config.API_KEY_FILE)
if api_key:
    os.environ['GOOGLE_API_KEY'] = api_key
else:
    print("POZOR: API klíč pro Google se nepodařilo načíst. RAG systém nemusí fungovat.")


class UsageCallback(BaseCallbackHandler):
    """Callback handler pro zachycení statistik o použití tokenů z LLM."""
    def __init__(self):
        super().__init__()
        self.usage = {}

    def on_llm_end(self, response, **kwargs) -> None:
        """Spustí se na konci volání LLM a uloží si metadata o použití."""
        if response.llm_output and 'token_usage' in response.llm_output:
            # Uložíme celý slovník 'token_usage'
            self.usage = response.llm_output['token_usage']

def load_documents_from_json(data_path=config.RESULT_DIR):
    """Načte všechny JSON soubory z adresáře definovaného v configu."""
    if not os.path.exists(data_path):
        print(f"Adresář pro výsledky '{data_path}' neexistuje. Nelze načíst žádné dokumenty.")
        return []
        
    json_files = [f for f in os.listdir(data_path) if f.endswith('.json')]
    
    all_docs = []
    for file in json_files:
        file_path = os.path.join(data_path, file)
        loader = JSONLoader(
            file_path=file_path,
            jq_schema='.',
            text_content=False)
        docs = loader.load()
        all_docs.extend(docs)
        
    return all_docs

def create_vector_store(documents):
    """Vytvoří a uloží vektorovou databázi pomocí Google embeddings."""
    print("Vytvářím novou vektorovou databázi s Google embeddings...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    texts = text_splitter.split_documents(documents)
    
    # Použijeme embedding model od Googlu definovaný v configu
    embeddings = GoogleGenerativeAIEmbeddings(model=config.EMBEDDING_MODEL_NAME)
    vector_store = FAISS.from_documents(texts, embeddings)
    
    # Uložíme databázi do adresáře definovaného v configu
    print(f"Ukládám databázi do '{config.FAISS_INDEX_DIR}' pro příští použití...")
    vector_store.save_local(config.FAISS_INDEX_DIR)
    return vector_store

def create_rag_chain(vector_store, model_name):
    """Vytvoří RAG chain pro odpovídání na dotazy pomocí Google Gemini."""
    
    llm = ChatGoogleGenerativeAI(model=model_name, temperature=0)

    # Vytvoříme prompt template, který říká modelu, jak použít kontext.
    prompt = ChatPromptTemplate.from_template("""
    Odpověz na otázku uživatele pouze na základě poskytnutého kontextu.
    Pokud v kontextu není odpověď, řekni, že to nevíš.
    Buď stručný a drž se faktů z kontextu.

    Kontext:
    {context}

    Otázka: {input}

    Odpověď:
    """)

    # Vytvoříme "stuff" chain, který vezme dokumenty a vloží je do promptu.
    document_chain = create_stuff_documents_chain(llm, prompt)

    # Vytvoříme retriever z naší vektorové databáze.
    retriever = vector_store.as_retriever()

    # Vytvoříme finální "retrieval" chain, který nejprve získá dokumenty a pak je předá dál.
    retrieval_chain = create_retrieval_chain(retriever, document_chain)

    return retrieval_chain


def get_rag_chain(model_name):
    """Inicializuje a vrátí plně funkční RAG chain pro daný model."""
    index_path = config.FAISS_INDEX_DIR
    
    # Načtení embeddingů je potřeba v obou případech
    embeddings = GoogleGenerativeAIEmbeddings(model=config.EMBEDDING_MODEL_NAME)

    if os.path.exists(index_path):
        print(f"Načítám existující vektorovou databázi z '{index_path}'...")
        vector_store = FAISS.load_local(index_path, embeddings, allow_dangerous_deserialization=True)
    else:
        print("Vektorová databáze nenalezena, vytvářím novou...")
        documents = load_documents_from_json()
        if not documents:
            print(f"Nebyly nalezeny žádné dokumenty v adresáři '{config.RESULT_DIR}'. RAG nelze spustit.")
            return None
        vector_store = create_vector_store(documents)

    return create_rag_chain(vector_store, model_name=model_name)

def ask_question(chain, query, model_name):
    """Položí dotaz existujícímu RAG chainu a vrátí odpověď včetně statistik."""
    if not chain:
        return {"error": "RAG chain není inicializován."}
    
    usage_callback = UsageCallback()
    
    try:
        # Nový chain očekává vstup jako slovník s klíčem 'input'
        response = chain.invoke({"input": query}, config={'callbacks': [usage_callback]})

    except google_exceptions.ResourceExhausted as e:
        error_message = (
            "Byl překročen limit pro API (ResourceExhausted). Zkontrolujte svůj fakturační plán v Google AI Studiu. "
            "Toto se často stává u bezplatné verze, která má přísné limity na počet dotazů za minutu/den."
        )
        print(f"❌ Chyba: {error_message}")
        # Do souboru se zaloguje jen zkrácená verze, do konzole se vypíše celá.
        return {"error": error_message, "result": "Chyba: Překročen limit API."}

    except Exception as e:
        print(f"❌ Došlo k chybě při komunikaci s RAG chainem: {e}")
        return {"error": f"Chyba při volání RAG API: {e}", "result": "Chyba komunikace s AI."}

    usage_data = usage_callback.usage
    
    input_tokens = usage_data.get('prompt_token_count', 0)
    output_tokens = usage_data.get('candidates_token_count', 0)
    total_tokens = usage_data.get('total_token_count', 0)
    is_estimated = False
    
    # Fallback: Pokud model nevrátí přesné statistiky, odhadneme je.
    if total_tokens == 0 and response.get("answer"):
        print("⚠️ Statistiky o použití tokenů nebyly vráceny modelem. Provádím odhad...")
        is_estimated = True
        try:
            # Získáme kontext z odpovědi
            context_docs = response.get('context', [])
            context_text = "\n\n".join([doc.page_content for doc in context_docs])
            
            # Zrekonstruujeme prompt, který byl poslán do LLM
            prompt_template_str = """Odpověz na otázku uživatele pouze na základě poskytnutého kontextu.
Pokud v kontextu není odpověď, řekni, že to nevíš.
Buď stručný a drž se faktů z kontextu.

Kontext:
{context}

Otázka: {input}

Odpověď:
"""
            full_prompt = prompt_template_str.format(context=context_text, input=query)
            answer = response.get('answer', "")

            # Speciální případ pro modely, které nepodporují countTokens API
            if model_name == "gemini-1.0-pro":
                input_tokens = len(full_prompt) // 4
                output_tokens = len(answer) // 4
            else:
                # Pro ostatní modely se pokusíme získat přesný počet tokenů
                llm = ChatGoogleGenerativeAI(model=model_name, temperature=0)
                input_tokens = llm.get_num_tokens(full_prompt)
                output_tokens = llm.get_num_tokens(answer)
            
            total_tokens = input_tokens + output_tokens
            print(f"📈 Odhad: Vstupních tokenů: {input_tokens}, Výstupních tokenů: {output_tokens}, Celkem: {total_tokens}")

        except Exception as e:
            print(f"❌ Došlo k chybě při odhadu tokenů: {e}")
            # V případě chyby nastavíme vše na 0, aby se předešlo dalším chybám
            input_tokens, output_tokens, total_tokens = 0, 0, 0

    cost = vypocitat_naklady(model_name, input_tokens=input_tokens, output_tokens=output_tokens)
    
    # Struktura odpovědi se změnila. Odpověď je nyní v klíči 'answer'.
    final_response = {
        "result": response.get('answer', "Odpověď nebyla nalezena."),
        "source_documents": response.get('context', []), # kontext je nyní zde
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "cost_usd": f"{cost:.8f}",
            "estimated": is_estimated # Přidáme flag, že jde o odhad
        }
    }
    
    return final_response

def run_rag_cli():
    """Spustí RAG v příkazovém řádku s využitím Google Gemini."""
    print("--- RAG Systém (CLI) ---")

    # --- Výběr modelu ---
    print("\nVyberte AI model:")
    # Načteme modely a jejich popisy z centrální konfigurace
    available_models = list(config.MODEL_DESCRIPTIONS.keys())
    for i, model_name in enumerate(available_models):
        print(f"{i+1}: {model_name} - {config.MODEL_DESCRIPTIONS[model_name]}")

    model_choice = -1
    while model_choice < 0 or model_choice >= len(available_models):
        try:
            choice_str = input(f"Zadejte číslo modelu (1-{len(available_models)}): ")
            model_choice = int(choice_str) - 1
            if model_choice < 0 or model_choice >= len(available_models):
                print("Neplatná volba, zkuste to znovu.")
        except ValueError:
            print("Neplatná volba, zadejte prosím číslo.")

    selected_model = available_models[model_choice]
    print(f"\nVybrali jste model: {selected_model}")
    
    print("\nInicializuji RAG systém...")
    qa_chain = get_rag_chain(model_name=selected_model)
    
    if not qa_chain:
        return # Ukončíme, pokud se nepodařilo chain vytvořit

    print("RAG systém je připraven. Zadejte 'konec' pro ukončení.")
    
    while True:
        query = input("\nZadejte svůj dotaz: ")
        if query.lower() == 'konec':
            break
            
        response = ask_question(qa_chain, query, model_name=selected_model)
        
        print("\nOdpověď:")
        if "result" in response:
            print(response['result'])
        else:
            print(response.get('error', "Neznámá chyba."))
            
        # Vytiskneme statistiky, pokud jsou k dispozici
        if 'usage' in response and response['usage'].get('total_tokens', 0) > 0:
            usage = response['usage']
            estimated_badge = "(Odhad)" if usage.get('estimated') else ""
            print("\n--- Statistiky Použití ---")
            print(f"Vstupní tokeny: {usage['input_tokens']}")
            print(f"Výstupní tokeny: {usage['output_tokens']}")
            print(f"Celkem tokenů: {usage['total_tokens']} {estimated_badge}")
            print(f"Odhadovaná cena: ${usage['cost_usd']} USD")
            print("--------------------------")
        elif 'usage' in response:
            print("\n--- Statistiky Použití ---")
            print("Informace o počtu tokenů nebyly vráceny.")
            print("--------------------------")

    print("\nSezení ukončeno.")

if __name__ == '__main__':
    run_rag_cli()
