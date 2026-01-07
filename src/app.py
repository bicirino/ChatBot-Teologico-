import os 
import sqlite3
import re
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
import google.generativeai as genai

# --- INICIALIZAÇÃO E CONFIGURAÇÕES ---

load_dotenv() 

app = Flask(__name__)
# CORS configurado para permitir qualquer origem durante o desenvolvimento
CORS(app, resources={r"/api/*": {"origins": "*"}}) 

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Localização automática do banco de dados
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'NVI.sqlite.db')

# Inicializa o Cliente Gemini
try:
    if not GEMINI_API_KEY:
        print("❌ ERRO: GEMINI_API_KEY não encontrada no ficheiro .env")
    else:
        # Configuração do cliente com a biblioteca correta
        genai.configure(api_key=GEMINI_API_KEY)
        print("✨ Cliente Gemini inicializado com sucesso.")
except Exception as e:
    print(f"❌ Erro ao conectar com Google AI: {e}")

# --- LÓGICA DE BANCO DE DADOS (RAG) ---

def get_connection():
    try:
        # Verifica se o ficheiro existe antes de tentar abrir
        if not os.path.exists(DB_PATH):
            print(f"⚠️ AVISO: Ficheiro de base de dados não encontrado em: {DB_PATH}")
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print(f"❌ Erro ao abrir arquivo .db: {e}")
        return None

def init_db():
    print(f"🔍 Verificando base de dados em: {DB_PATH}...")
    conn = get_connection()
    if not conn: 
        print("❌ Falha crítica: Não foi possível estabelecer conexão com o SQLite.")
        return
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='full_text_search'")
        if not cursor.fetchone():
            print("⚙️ Criando índice de busca nos manuscritos (FTS5)...")
            cursor.execute("""
                CREATE VIRTUAL TABLE full_text_search USING fts5(
                    text, 
                    content='verse', 
                    content_rowid='id'
                );
            """)
            cursor.execute("INSERT INTO full_text_search(rowid, text) SELECT id, text FROM verse;")
            conn.commit()
            print("✅ Índice FTS5 criado e populado com sucesso.")
        else:
            print("✅ Índice de busca já existente e pronto a usar.")
    except sqlite3.Error as e:
        print(f"❌ Erro ao inicializar tabelas: {e}. Verifique se a tabela 'verse' existe.")
    finally:
        conn.close()
    print("📜 Salomão está pronto para consultar os manuscritos.")

def fetch_relevant_verses(query):
    conn = get_connection()
    if not conn: return None
    try:
        cursor = conn.cursor()
        clean_query = re.sub(r'[^\w\s]', '', query)
        
        if not clean_query.strip():
            return ""

        cursor.execute(
            "SELECT rowid FROM full_text_search WHERE full_text_search MATCH ? LIMIT 5", 
            (f'"{clean_query}"',)
        )
        
        ids = [row[0] for row in cursor.fetchall()]
        if not ids: return ""

        placeholders = ','.join('?' * len(ids))
        query_sql = f"""
            SELECT T1.text, T2.name AS book, T1.chapter, T1.verse
            FROM verse T1 JOIN book T2 ON T1.book_id = T2.id
            WHERE T1.id IN ({placeholders})
        """
        cursor.execute(query_sql, ids)
        results = cursor.fetchall()
        return "\n".join([f"[{r['book']} {r['chapter']}:{r['verse']}]: {r['text']}" for r in results])
    except sqlite3.Error as e:
        print(f"❌ Erro na busca FTS5: {e}")
        return None
    finally:
        conn.close()

# --- LÓGICA DE INTELIGÊNCIA ARTIFICIAL ---

def ask_solomon(user_query, context):
    prompt = (
        f"Você é Salomão, um conselheiro sábio. Responda à pergunta do usuário "
        f"usando os seguintes versículos como base:\n\n{context}\n\n"
        f"Pergunta: {user_query}\n\nResponda de forma calma e cite a referência."
    )

    # Lista de prioridade de modelos: 
    models_to_try = ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash']

    last_error = None

    for model_name in models_to_try:
        try:
            print(f"⚡ Tentando usar modelo: {model_name}...")
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7,
                    max_output_tokens=1024,
                )
            )
            print(f"✅ Sucesso com {model_name}")
            return response.text, None

        except Exception as e:
            error_msg = str(e)
            last_error = error_msg
            print(f"⚠️ Modelo {model_name} não disponível: {error_msg}")
            continue

    # Se saiu do loop sem retornar, falhou em todos
    if "429" in str(last_error):
        return None, "LIMITE_EXCEDIDO"
    
    return None, f"ERRO_API: Não foi possível conectar a nenhum modelo. Último erro: {last_error}"
# --- ROTAS DA API ---

@app.route('/api/chat', methods=['POST'])
def chat():
    print(f"📩 Pedido recebido: {request.get_json()}")
    try:
        data = request.get_json()
        pergunta = data.get('query', '')
        
        if not pergunta:
            return jsonify({"answer": "O que desejas saber, meu filho?"}), 400

        contexto = fetch_relevant_verses(pergunta)
        if contexto is None:
            contexto = ""

        resposta, erro = ask_solomon(pergunta, contexto)
        
        if erro == "LIMITE_EXCEDIDO":
            return jsonify({"answer": "Estou meditando... Por favor, aguarde um minuto.", "source": "Cota Google"}), 429
        elif erro:
            print(f"❌ ERRO DETECTADO: {erro}")
            return jsonify({"answer": f"Erro na IA: {erro}", "source": "Debug"}), 500

        return jsonify({
            "answer": resposta,
            "source": "Fontes: " + contexto.replace('\n', ' | ') if contexto else "Conhecimento geral."
        })
    except Exception as e:
        print(f"❌ Erro interno: {e}")
        return jsonify({"answer": "Erro interno no servidor.", "error": str(e)}), 500

if __name__ == '__main__':
    print("🚀 A iniciar o servidor de sabedoria...")
    init_db()
    # O host '0.0.0.0' ajuda a evitar bloqueios em alguns sistemas
    app.run(debug=True, port=5000, host='0.0.0.0') 