# --- Declaração de variáveis e importações --- 

import os 
import sqlite3
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import APIError 
#__________________________________________________________________________________________________________________
# --- CONFIGURAÇÃO DE SEGURANÇA E BANCO DE DADOS ---


# Carrega as variáveis de ambiente do arquivo .env
load_dotenv() 

# Tenta obter a chave API do Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("ERRO CRÍTICO: Chave GEMINI_API_KEY não encontrada no arquivo .env")
    GEMINI_API_KEY = "CHAVE_VAZIA_PARA_TESTE"

# Inicializa o Cliente Gemini
try:
    client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    print(f"ERRO ao inicializar o cliente Gemini: {e}")
    client = None

# O caminho está configurado para voltar uma pasta (..) e buscar o arquivo na pasta 'data'
DB_PATH = os.path.join('..', 'data', 'NVI.sqlite.db')
#__________________________________________________________________________________________________________________
# --- FUNÇÕES DE CONEXÃO COM O BANCO DE DADOS (RETRIEVAL) ---

def get_connection():
    """Cria e retorna a conexão com o banco de dados."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    
    except sqlite3.Error as e:
        print(f"ERRO CRÍTICO: Não foi possível conectar ao banco de dados em {DB_PATH}.")
        print(f"Detalhes do Erro: {e}")
        return None

def fetch_relevant_verses(query):
    """
    IMPLEMENTAÇÃO FTS (Busca por Texto Completo) CORRIGIDA.
    Busca no banco de dados os 5 versículos mais relevantes para a pergunta do usuário.
    Retorna uma string formatada ou uma string vazia ("") se não encontrar.
    Retorna None em caso de erro crítico (conexão/SQL).
    """
    conn = get_connection()
    if conn is None:
        return None

    results = []
    
    try:
        cursor = conn.cursor()
        
        # 1. Busca IDs dos versículos mais relevantes usando FTS (máximo de 5)
        fts_query = query # Usa a pergunta do usuário diretamente como termo de busca
        
        # Seleciona o rowid (que é o verse_id)
        cursor.execute("SELECT rowid FROM full_text_search WHERE full_text_search MATCH ? LIMIT 5", (fts_query,))
        
        verse_ids = [row[0] for row in cursor.fetchall()]
        
        if not verse_ids:
            return "" # Retorna string vazia se nenhum versículo for encontrado

        # 2. Constrói a query para buscar os detalhes dos versículos USANDO OS IDs ENCONTRADOS
        placeholders = ','.join('?' * len(verse_ids))
        
        detail_query = f"""
        SELECT T1.text, T2.name AS book_name, T1.chapter, T1.verse
        FROM verse T1
        JOIN book T2 ON T1.book_id = T2.id
        WHERE T1.id IN ({placeholders})
        """
        
        # Executa a busca pelos detalhes dos versículos encontrados
        cursor.execute(detail_query, verse_ids)
        
        for result in cursor.fetchall():
            results.append(
                f"[{result['book_name']} {result['chapter']}:{result['verse']}]: {result['text']}"
            )
        
        return "\n".join(results)
        
    except sqlite3.Error as e:
        # Erro de SQL (p.ex., tabela full_text_search não encontrada)
        print(f"SQL_QUERY_FAILED (FTS): {e}")
        return None
    finally:
        conn.close()

#_________________________________________________________________________________________________________________
# --- FUNÇÃO DE GERAÇÃO DA RESPOSTA (GEMINI) ---

def generate_answer_with_gemini(user_query, relevant_context):
    """
    Usa o modelo Gemini 2.5 Flash para gerar uma resposta baseada no contexto.
    Esta é a parte de Raciocínio (Generation) - AGORA COM TRATAMENTO DE CONTEXTO VAZIO.
    """
    if not client or GEMINI_API_KEY == "CHAVE_VAZIA_PARA_TESTE":
        return None, "CLIENT_NOT_INITIALIZED"

    # 1. Definir a Persona e Regras do Sistema (System Instruction)
    system_instruction = (
        "Você é Salomão, o ChatBot da Sabedoria. Sua persona é sábia, calma e teológica. "
        "Sua principal função é atuar como um conselheiro teológico, respondendo a perguntas do usuário. "
        "Sempre priorize e fundamente sua resposta no CONTEXTO bíblico fornecido, transformando-o "
        "em um texto pastoral e relevante. Mantenha a resposta concisa, direta e **sempre cite a referência "
        "do(s) versículo(s) utilizado(s) no final da sua resposta.** Se o contexto for vazio, use seu "
        "conhecimento geral bíblico para responder, indicando que a sabedoria vem de um lugar mais amplo."
    )

    # 2. Montar o Prompt RAG
    context_prefix = "CONTEXTO BÍBLICO PARA REFERÊNCIA:\n---\n"
    context_suffix = "\n---\n"
    
    if not relevant_context:
        # Contexto de fallback para a IA quando a busca não encontra versículos
        context_prefix = "CONTEXTO INDISPONÍVEL. A busca não retornou versículos relevantes.\n---\n"
        context_suffix = "\n---\n"

    prompt = (
        f"{context_prefix}{relevant_context}{context_suffix}\n"
        f"PERGUNTA DO USUÁRIO: {user_query}\n\n"
        "Com base no contexto (ou em seu conhecimento geral se o contexto estiver indisponível), "
        "forneça uma resposta única, completa e pastoral para o usuário."
    )

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction
            )
        )
        if response.candidates and response.candidates[0].finish_reason == types.FinishReason.SAFETY:
            return None, "SAFETY_BLOCKED"
            
        return response.text, None

    except APIError as e:
        print(f"ERRO API GEMINI: {e}")
        return None, "API_ERROR"
    except Exception as e:
        print(f"ERRO INESPERADO: {e}")
        return None, "UNKNOWN_ERROR"

#_________________________________________________________________________________________________________________
# --- APLICAÇÃO FLASK (ROUTING) ---

app = Flask(__name__)
CORS(app) 

# Rota de Teste Simples
@app.route('/')
def home():
    """Confirma que o servidor Flask está rodando."""
    return "Bem-vindo ao ChatBot Salomão! O servidor Flask está ativo."

# Rota Principal da API do Chat (RF.01)
@app.route('/api/chat', methods=['POST'])
def process_chat_query():
    """
    Recebe a pergunta do usuário, busca o contexto e usa a IA para gerar a resposta.
    """
    try:
        data = request.get_json()
        user_query = data.get('query', 'Pergunta Vazia')
        
    except Exception:
        return jsonify({"error": "Formato de requisição JSON inválido."}), 400

    if not client or GEMINI_API_KEY == "CHAVE_VAZIA_PARA_TESTE":
        return jsonify({"answer": "O servidor não conseguiu inicializar a conexão com a IA. Verifique sua GEMINI_API_KEY no arquivo .env.", "source": "Erro de Chave API"}), 503

    # 1. Fase RAG - Retrieval (Busca de Contexto com FTS)
    relevant_context = fetch_relevant_verses(user_query)
    
    # Trata erro crítico de CONEXÃO/SQL (None), mas permite contexto vazio ("")
    if relevant_context is None:
        return jsonify({
            "answer": "Sinto muito, houve um erro crítico ao consultar a Base de Dados. Verifique o log do servidor.",
            "source": "Erro DB"
        }), 500

    # 2. Fase RAG - Generation (Geração da Resposta com a IA)
    # Se relevant_context for "", a IA usará seu conhecimento geral, como um ChatGPT.
    generated_text, error_code = generate_answer_with_gemini(user_query, relevant_context) 

    # 3. Tratamento de Erro da IA
    if error_code == "API_ERROR" or error_code == "UNKNOWN_ERROR":
        return jsonify({
            "answer": "Houve uma falha de comunicação com os Céus. Tente novamente.",
            "source": f"Erro API: {error_code}"
        }), 500
    if error_code == "SAFETY_BLOCKED":
        return jsonify({
            "answer": "Sinto muito, essa pergunta tocou em um tópico sensível. Minha Sabedoria está limitada a questões teológicas.",
            "source": "Bloqueio de Segurança"
        }), 400
    
    # 4. Sucesso: Retorno JSON
    if relevant_context:
        source_citation = "Referências dinâmicas (FTS) utilizadas: " + relevant_context.replace('\n', ' | ')
    else:
        source_citation = "Resposta baseada em conhecimento geral (nenhum versículo relevante encontrado na base de dados)."

    return jsonify({
        "answer": generated_text,
        "source": source_citation,
        "is_rag_active": True
    })



#________________________________________________________________________________________________________
# Executa o servidor Flask na porta 5000 (padrão)
if __name__ == '__main__':
    app.run(debug=True)