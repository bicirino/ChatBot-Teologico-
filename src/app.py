# --- Declaração de variáveis e importações --- 

import os 
import sqlite3
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import APIError 

# ____________________________________________________________________________________________________________________________________________
# --- CONFIGURAÇÃO DE SEGURANÇA E BANCO DE DADOS ---

# Carrega as variáveis de ambiente
load_dotenv() 

# Tenta obter a chave API do Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("ERRO CRÍTICO: Chave GEMINI_API_KEY não encontrada no arquivo .env")
    GEMINI_API_KEY = "" # Mantido vazio para evitar erros de inicialização se faltar no env

# Inicializa o Cliente Gemini
try:
    client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    print(f"Erro ao inicializar Gemini: {e}")
    client = None

# Caminho do banco de dados (ajustado para subir um nível se necessário)
DB_PATH = os.path.join('..', 'data', 'NVI.sqlite.db')

#_____________________________________________________________________________________________________________________________________________
# --- FUNÇÕES DE CONEXÃO E BUSCA (RETRIEVAL) ---

def get_connection():
    """Cria e retorna a conexão com o banco de dados."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print(f"ERRO DE CONEXÃO DB: {e}")
        return None

# -------------------------------------------------------------------------------------------------------------------------
#FUNÇÃO DE BUSCA DE VERSÍCULO: 

def fetch_relevant_verses(query):
    """
    Realiza a busca dinâmica usando FTS (Full Text Search).
    """
    conn = get_connection()
    if not conn:
        return None

    # Versículos fixos: Gênesis 1:3, Salmos 23:1, João 14:6
    fixed_verses = [
        ("Gênesis", 1, 3), 
        ("Salmos", 23, 1), 
        ("João", 14, 6)
    ]
    
    results = []
    
    try:
        cursor = conn.cursor()
        
        # 1. Fase de Busca (FTS): Obtém rowids
        cursor.execute(
            "SELECT rowid FROM full_text_search WHERE full_text_search MATCH ? LIMIT 5",
            (query,)
        )
        
        rows = cursor.fetchall()
        verse_ids = [row[0] for row in rows]

        if not verse_ids:
            return ""

        # 2. Fase de Recuperação: Busca textos usando os IDs encontrados
        placeholders = ','.join('?' * len(verse_ids))
        detail_query = f"""
            SELECT T1.text, T2.name AS book_name, T1.chapter, T1.verse
            FROM verse T1
            JOIN book T2 ON T1.book_id = T2.id
            WHERE T1.id IN ({placeholders})
        """
        
        for book, chapter, verse in fixed_verses:
            cursor.execute(query_sql, (book, chapter, verse))
            result = cursor.fetchone()
            if result:
                results.append(
                    f"[{result['book_name']} {result['chapter']}:{result['verse']}]: {result['text']}"
                )
        return "\n".join(results)
        
    except sqlite3.Error as e:
        print(f"Erro na query SQL: {e}")
        return None
    finally:
        conn.close()

#_____________________________________________________________________________________________________________________________________________
# --- GERAÇÃO DA RESPOSTA (GENERATION) ---

def generate_answer_with_gemini(user_query, relevant_context):
    """Usa o modelo Gemini para gerar resposta baseada no contexto."""
    if not client or not GEMINI_API_KEY:
        return None, "CLIENT_NOT_INITIALIZED"

    # 1. Definir a Persona e Regras do Sistema (System Instruction)
    system_instruction = (
        "Você é Salomão, o ChatBot da Sabedoria. Sua persona é sábia, calma e teológica. "
        "Responda como um conselheiro. Priorize o CONTEXTO bíblico fornecido. "
        "Mantenha a resposta concisa e sempre cite a referência no final. "
        "Se o contexto for vazio, use seu conhecimento geral bíblico."
    )

    # Melhoria no Prompt para garantir que a IA entenda o contexto dinâmico
    prompt = (
        f"CONTEXTO BÍBLICO DISPONÍVEL:\n{relevant_context if relevant_context else 'Nenhum versículo específico encontrado.'}\n\n"
        f"PERGUNTA DO USUÁRIO: {user_query}"
    )

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash-preview-09-2025', # Modelo atualizado para versão estável do preview
            contents=prompt,
            config=types.GenerateContentConfig(system_instruction=system_instruction)
        )
        
        if not response.candidates:
            return None, "NO_RESPONSE_CANDIDATES"

        if response.candidates[0].finish_reason == types.FinishReason.SAFETY:
            return None, "SAFETY_BLOCKED"
            
        return response.text, None

    except Exception as e:
        print(f"ERRO GEMINI: {e}")
        return None, "API_ERROR"

#_____________________________________________________________________________________________________________________________________________
# --- APLICAÇÃO FLASK (ROUTING) ---

app = Flask(__name__)
CORS(app) # Permitir todas as origens para facilitar o desenvolvimento local

# Rota de Teste Simples
@app.route('/')
def home():
    return "Servidor Salomão Ativo."

# Rota Principal da API do Chat (RF.01)
@app.route('/api/chat', methods=['POST'])
def process_chat_query():
    """
    Recebe a pergunta do usuário, busca o contexto e usa a IA para gerar a resposta.
    """
    try:
        # Verifica se o corpo da requisição é JSON
        if not request.is_json:
            return jsonify({"answer": "Erro: O servidor esperava um JSON.", "source": "Client Error"}), 400
            
        data = request.get_json()
        user_query = data.get('query', '')
        if not user_query:
            return jsonify({"answer": "Por favor, digite uma pergunta."}), 400
            
    except Exception:
        return jsonify({"error": "JSON inválido."}), 400

    # 1. Retrieval
    relevant_context = fetch_relevant_verses(user_query)
    
    if relevant_context is None:
        return jsonify({
            "answer": "Erro ao acessar a sabedoria dos manuscritos (Erro de Banco de Dados).",
            "source": "Erro DB"
        }), 500

    # 2. Generation
    generated_text, error_code = generate_answer_with_gemini(user_query, relevant_context) 

    if error_code:
        return jsonify({
            "answer": "Houve uma falha na conexão espiritual (Erro de IA).",
            "source": f"Erro: {error_code}"
        }), 500
    
    # 3. Sucesso
    source_citation = "Referências dinâmicas: " + relevant_context.replace('\n', ' | ') if relevant_context else "Conhecimento geral."

    return jsonify({
        "answer": generated_text,
        "source": source_citation,
        "is_rag_active": True
    })

if __name__ == '__main__':
    app.run(debug=True)