import os 
import sqlite3
import re
from flask import Flask, jsonify, request, make_response
from flask_cors import CORS
from dotenv import load_dotenv
from google import genai
from google.genai import types

# --- INICIALIZAÇÃO E CONFIGURAÇÕES ---

load_dotenv() 

app = Flask(__name__)

# CONFIGURAÇÃO DE CORS ROBUSTA:
# Permitimos todas as origens (*), métodos e headers para garantir que a Vercel/Frontend conecte sem problemas.
# Adicionamos suporte a 'Content-Type' para evitar erros em requisições JSON.
CORS(app, resources={r"/api/*": {
    "origins": "*", 
    "methods": ["POST", "OPTIONS"], 
    "allow_headers": ["Content-Type", "Authorization"]
}})

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Localização automática do banco de dados (Caminho Absoluto)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'NVI.sqlite.db')

# Inicializa o Cliente Gemini
try:
    if not GEMINI_API_KEY:
        print("❌ ERRO: GEMINI_API_KEY não encontrada nas variáveis de ambiente.")
    else:
        client = genai.Client(api_key=GEMINI_API_KEY)
        print("✨ Cliente Gemini inicializado com sucesso.")
except Exception as e:
    print(f"❌ Erro ao inicializar Google AI: {e}")
    client = None

# --- LÓGICA DE BANCO DE DADOS (RAG) ---

def get_connection():
    try:
        # Check_same_thread=False é importante para servidores multithread como Gunicorn
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print(f"❌ Erro de conexão com SQLite: {e}")
        return None

def init_db():
    conn = get_connection()
    if not conn: return
    try:
        cursor = conn.cursor()
        # Verifica se a tabela virtual FTS5 existe
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='full_text_search'")
        if not cursor.fetchone():
            print("⚙️ Criando índice FTS5 para busca bíblica...")
            cursor.execute("CREATE VIRTUAL TABLE full_text_search USING fts5(text, content='verse', content_rowid='id');")
            cursor.execute("INSERT INTO full_text_search(rowid, text) SELECT id, text FROM verse;")
            conn.commit()
            print("✅ Índice FTS5 criado com sucesso.")
    except sqlite3.Error as e:
        print(f"❌ Erro na inicialização do FTS5: {e}")
    finally:
        conn.close()

def fetch_relevant_verses(query):
    conn = get_connection()
    if not conn: return None
    try:
        cursor = conn.cursor()
        # Limpa a query para evitar caracteres especiais que quebram o FTS5
        clean_query = re.sub(r'[^\w\s]', '', query)
        if not clean_query.strip(): return ""

        # Busca IDs relevantes via FTS5
        cursor.execute("SELECT rowid FROM full_text_search WHERE full_text_search MATCH ? LIMIT 5", (f'"{clean_query}"',))
        ids = [row[0] for row in cursor.fetchall()]
        if not ids: return ""

        # Recupera os textos e referências
        placeholders = ','.join('?' * len(ids))
        query_str = f"""
            SELECT T1.text, T2.name AS book, T1.chapter, T1.verse 
            FROM verse T1 
            JOIN book T2 ON T1.book_id = T2.id 
            WHERE T1.id IN ({placeholders})
        """
        cursor.execute(query_str, ids)
        results = cursor.fetchall()
        return "\n".join([f"[{r['book']} {r['chapter']}:{r['verse']}]: {r['text']}" for r in results])
    except sqlite3.Error as e:
        print(f"❌ Erro na busca FTS5: {e}")
        return None
    finally:
        conn.close()

# --- LÓGICA DE IA ---

def ask_solomon(user_query, context):
    if not client: 
        return "O espírito de sabedoria está em silêncio (IA Offline).", "Erro de Configuração"
    
    prompt = f"""
    Você é o Rei Salomão, conhecido por sua imensa sabedoria bíblica.
    Responda à pergunta de forma sábia, pastoral e equilibrada.
    Se houver contexto bíblico abaixo, use-o para fundamentar sua resposta.
    
    Contexto Bíblico Local:
    {context}
    
    Pergunta do Buscador: {user_query}
    """
    
    try:
        response = client.models.generate_content(model='gemini-1.5-flash', contents=prompt)
        return response.text, None
    except Exception as e:
        print(f"❌ Erro Gemini: {e}")
        return None, str(e)

# --- ROTAS DA API ---

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "message": "Servidor do Salomão ativo e pronto para pedidos."
    })

@app.route('/api/chat', methods=['POST', 'OPTIONS'])
def chat():
    # Tratamento explícito de OPTIONS (Preflight do Navegador)
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add('Access-Control-Allow-Headers', "Content-Type, Authorization")
        response.headers.add('Access-Control-Allow-Methods', "POST, OPTIONS")
        return response, 204
        
    try:
        data = request.get_json()
        if not data or 'query' not in data:
            return jsonify({"answer": "Por favor, envie uma pergunta válida.", "source": "Sistema"}), 400
            
        pergunta = data.get('query', '')
        
        # Busca contexto no banco de dados local
        contexto = fetch_relevant_verses(pergunta) or ""
        
        # Gera resposta com a IA
        resposta, erro = ask_solomon(pergunta, contexto)
        
        if erro:
            return jsonify({
                "answer": "Houve uma interrupção na conexão celestial. Tente novamente em breve.", 
                "source": "Erro Técnico"
            }), 500

        # Prepara a resposta JSON
        res_data = {
            "answer": resposta,
            "source": "Escrituras Consultadas: " + contexto.replace('\n', ' | ') if contexto else "Sabedoria Teológica Geral."
        }
        
        response = make_response(jsonify(res_data))
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response

    except Exception as e:
        print(f"❌ Erro na Rota Chat: {e}")
        return jsonify({"answer": "Ocorreu um erro inesperado no templo.", "error": str(e)}), 500

# --- INICIALIZAÇÃO ---
if __name__ == '__main__':
    # Inicializa o banco antes de rodar o app
    init_db()
    
    # O Render usa a porta da variável de ambiente PORT
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)