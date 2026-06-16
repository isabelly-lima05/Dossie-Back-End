# -*- coding: utf-8 -*-
import sys

# =====================================================================
# CONFIGURAÇÃO DE CONCORRÊNCIA ASSÍNCRONA (GEVENT)
# =====================================================================
# O patch de concorrência deve ser executado no topo do arquivo para
# garantir que as conexões WebSocket via Socket.IO funcionem de forma
# não bloqueante em servidores de produção.
if sys.platform != "win32":
    try:
        from gevent import monkey
        monkey.patch_all()
        print("[INFO] Monkey patch do Gevent aplicado com sucesso.")
    except ImportError:
        print("[AVISO] Gevent não encontrado. Executando em modo síncrono padrão.")

import os
from uuid import uuid4
from flask import Flask, request, session, jsonify
from flask_socketio import SocketIO, emit
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Importa as diretrizes detalhadas de cada bot do arquivo externo
from instrucoes import BOTS_CONFIG

# Carrega as variáveis de ambiente a partir do arquivo .env
load_dotenv()

# Definição do modelo otimizado para conversação rápida
MODELO_GEMINI = "gemini-3.1-flash-lite"

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "chave_secreta_padrao_investigacao_123")

# Inicialização do Socket.IO com suporte a CORS para o front-end
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent' if sys.platform != "win32" else None)

# Cliente global do Gemini inicializado sob demanda (lazy initialization)
client_gemini = None

# Estrutura em memória para armazenar chats ativos:
# active_chats = { "session_id": { "bot_id": "nome_do_bot", "chat": chat_session_object } }
active_chats = {}

def get_gemini_client():
    """
    Inicializa o cliente oficial do Google GenAI utilizando a chave de API configurada.
    """
    global client_gemini
    if client_gemini is None:
        api_key = os.getenv("GENAI_KEY")
        if not api_key:
            app.logger.error("A variável de ambiente 'GENAI_KEY' não foi encontrada.")
            raise RuntimeError("Chave de API do Gemini (GENAI_KEY) ausente.")
        client_gemini = genai.Client(api_key=api_key)
    return client_gemini

def obter_ou_criar_chat(session_id, bot_id):
    """
    Recupera uma sessão de chat existente ou cria uma nova com base no bot_id fornecido.
    Se o bot_id de uma sessão existente for alterado, o histórico é redefinido para o novo bot.
    """
    gemini_client = get_gemini_client()

    # Fallback para o bot padrão caso o id enviado seja inválido
    if bot_id not in BOTS_CONFIG:
        bot_id = "detetive"

    bot_info = BOTS_CONFIG[bot_id]

    # Verifica se a sessão precisa ser criada ou reiniciada para um novo bot
    if (session_id not in active_chats 
            or active_chats[session_id] is None 
            or active_chats[session_id].get("bot_id") != bot_id):
        
        print(f"[CHAT] Inicializando sessão para ID: {session_id} | Bot: {bot_id} ({bot_info['nome']})")
        
        try:
            # Cria a configuração contendo as instruções específicas do bot selecionado
            configuracao = types.GenerateContentConfig(
                system_instruction=bot_info["system_instruction"]
            )
            
            # Instancia o chat persistente no lado da API do Gemini
            nova_sessao_chat = gemini_client.chats.create(
                model=MODELO_GEMINI,
                config=configuracao
            )
            
            active_chats[session_id] = {
                "bot_id": bot_id,
                "chat": nova_sessao_chat
            }
        except Exception as e:
            app.logger.error(f"Falha ao iniciar chat do Gemini para {session_id}: {e}", exc_info=True)
            raise e

    return active_chats[session_id]["chat"], bot_info

# =====================================================================
# ROTAS HTTP PADRÃO
# =====================================================================

@app.route('/')
def index():
    """
    Rota informativa básica para verificar a integridade da API e listar os bots ativos.
    """
    return jsonify({
        "servico": "API - Polaris",
        "status": "Online",
        "total_bots_configurados": len(BOTS_CONFIG),
        "bots_disponiveis": [
            {"id": key, "nome": value["nome"]} for key, value in BOTS_CONFIG.items()
        ]
    })

# =====================================================================
# CANAL DE COMUNICAÇÃO (SOCKET.IO EVENTS)
# =====================================================================

@socketio.on('connect')
def ao_conectar():
    """
    Acionado quando o cliente estabelece conexão WebSocket.
    O bot desejado pode ser passado como query parameter (ex: ?bot_id=socrates).
    """
    sid = request.sid
    # Captura o bot_id enviado pelo cliente na conexão ou adota o detetive como padrão
    bot_id = request.args.get('bot_id', 'detetive')
    
    print(f"[CONEXÃO] Cliente conectado: {sid} | Bot solicitado: {bot_id}")

    try:
        # Gera ou recupera um identificador único de sessão para o cliente
        session_id = request.args.get('session_id') or str(uuid4())
        
        # Recupera a sessão de chat correspondente e os metadados do bot
        chat_sessao, bot_info = obter_ou_criar_chat(session_id, bot_id)
        
        # Envia a primeira mensagem de introdução configurada nas diretrizes do bot
        resposta_inicial = chat_sessao.send_message(bot_info["primeira_mensagem"])
        
        # Extração de texto segura, compatível com as respostas da biblioteca Google GenAI
        texto_inicial = (
            resposta_inicial.text
            if hasattr(resposta_inicial, 'text') and resposta_inicial.text
            else resposta_inicial.candidates[0].content.parts[0].text
        )
        
        # Retorna o status de conexão confirmada ao cliente junto da primeira mensagem
        emit('status_conexao', {
            'status': 'conectado',
            'session_id': session_id,
            'bot_id': bot_id,
            'nome_bot': bot_info["nome"]
        })
        
        emit('nova_mensagem', {
            "remetente": "bot",
            "texto": texto_inicial,
            "session_id": session_id
        })

    except Exception as e:
        app.logger.error(f"Erro no evento de conexão para o cliente {sid}: {e}", exc_info=True)
        emit('erro', {"erro": "Não foi possível carregar as configurações do assistente."})


@socketio.on('enviar_mensagem')
def ao_receber_mensagem(data):
    """
    Processa os inputs de texto enviados pelo usuário e retorna a resposta gerada pela IA.
    """
    sid = request.sid
    try:
        mensagem_usuario = data.get("mensagem")
        session_id = data.get("session_id")
        bot_id = data.get("bot_id", "detetive")

        if not mensagem_usuario:
            emit('erro', {"erro": "A entrada de texto enviada está vazia."})
            return

        if not session_id:
            emit('erro', {"erro": "Identificador de sessão ausente."})
            return

        # Recupera o chat ativo com base na sessão e bot indicados
        chat_sessao, _ = obter_ou_criar_chat(session_id, bot_id)
        
        # Envia a entrada do usuário para o fluxo de histórico da API do Gemini
        resposta_gemini = chat_sessao.send_message(mensagem_usuario)
        
        # Extração de texto segura
        resposta_texto = (
            resposta_gemini.text
            if hasattr(resposta_gemini, 'text') and resposta_gemini.text
            else resposta_gemini.candidates[0].content.parts[0].text
        )
        
        # Devolve a resposta estruturada para o front-end do usuário
        emit('nova_mensagem', {
            "remetente": "bot",
            "texto": resposta_texto,
            "session_id": session_id
        })

    except Exception as e:
        app.logger.error(f"Erro ao processar mensagem do cliente {sid}: {e}", exc_info=True)
        emit('erro', {"erro": "Falha interna ao gerar a resposta do assistente."})


@socketio.on('disconnect')
def ao_desconectar():
    """
    Acionado quando a conexão WebSocket é encerrada.
    O estado de active_chats é mantido intacto para que o usuário possa reconectar
    e continuar a mesma sessão sem perda de histórico.
    """
    sid = request.sid
    print(f"[DESCONEXÃO] Conexão encerrada pelo terminal do cliente: {sid}")


# =====================================================================
# INICIALIZAÇÃO DA APLICAÇÃO
# =====================================================================
if __name__ == "__main__":
    # Define a porta de execução de acordo com o ambiente (padrão 5000 para local)
    porta = int(os.environ.get("PORT", 5000))
    host_ip = os.environ.get("HOST", "0.0.0.0")
    
    print(f"[START] Servidor de Chatbots iniciado em http://{host_ip}:{porta}")
    socketio.run(app, host=host_ip, port=porta)