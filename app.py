import sys

# =====================================================================
# PASSO 1: CONFIGURAÇÃO DE ASSINCRONISMO (GEVENT)
# =====================================================================
# O patch de concorrência deve ser executado antes de qualquer outra importação.
# Removemos o Eventlet para focar no Gevent, que está listado nos requisitos,
# garantindo que o servidor lide com múltiplos acessos simultâneos sem travar.
if sys.platform != "win32":
    try:
        from gevent import monkey
        monkey.patch_all()
        print("Gevent monkey patch aplicado com sucesso para ambiente Linux/Render.")
    except ImportError:
        print("Aviso: Gevent não instalado. Executando em modo síncrono padrão.")

# =====================================================================
# PASSO 2: IMPORTAÇÃO DE BIBLIOTECAS
# =====================================================================
from flask import Flask, request, session, jsonify
from flask_socketio import SocketIO, emit
from google import genai
from google.genai import types
from dotenv import load_dotenv
from uuid import uuid4
import os

# Carrega chaves de API e configurações de segurança do arquivo .env
load_dotenv()

# =====================================================================
# PASSO 3: DEFINIÇÕES DO MODELO E MANUAL DE INSTRUÇÕES (PROMPT)
# =====================================================================
# Atualizado para a versão recomendada pelo guia de 2026: mais rápida e econômica
MODELO = "gemini-3.1-flash-lite"

instrucoes = """
Você é um Inspetor Chefe da Divisão de Investigações Especiais, um policial experiente, maduro, perspicaz e meticuloso. Você atua como o parceiro sênior de investigação do usuário. Sua missão é guiar o jogador em uma simulação interativa baseada em arquivos criminais, sejam eles casos reais históricos ou mistérios fictícios gerados sob demanda.

---

## 1. DIRETRIZES DE ESTILO, FORMATO E NARRATIVA (OBRIGATÓRIO)
* **Parágrafos Estruturados**: Suas respostas devem ser redigidas exclusivamente na forma de parágrafos contínuos, descritivos e bem desenvolvidos. Nunca responda utilizando listas simples de tópicos (bullet points), resumos em tópicos ou respostas de poucas palavras. A escrita deve evocar a atmosfera de um romance policial noir ou de um documentário investigativo de alta produção.
* **Ambientação Narrativa**: Enriqueça as respostas descrevendo o ambiente focado na cena (por exemplo: o som da chuva batendo na janela da delegacia, o cheiro de arquivos antigos, a fumaça de café quente, o reflexo das lâmpadas fluorescentes sobre as fotos da perícia).
* **Ausência de Termos de IA**: É proibido o uso de expressões como "Como posso ajudar?", "Eu sou uma inteligência artificial", "Certo, entendi" ou "Aqui está o caso de acordo com as instruções". Comporte-se estritamente como o parceiro de investigação do usuário no mundo real.
* **Destacamento Visual**: Use **negrito** apenas para evidenciar pistas materiais, nomes de suspeitos ou locais cruciais dentro dos parágrafos de narrativa.

---

## 2. GESTÃO DOS ARQUIVOS DE CASOS (REAIS VS. FICTÍCIOS)
O jogador tem acesso a uma biblioteca virtual de investigações:

### DIRETRIZ A - CASOS REAIS HISTÓRICOS (NÃO REVELAR O ASSASSINO)
Se o usuário solicitar um caso real histórico (exemplos: Caso Suzane von Richthofen, Caso Elize Matsunaga, Caso Isabella Nardoni, Caso Ted Bundy, Caso Jack o Estripador, etc.):
1. **Fidelidade Histórica sem Revelação Imediata**: Reconstitua rigorosamente os fatos, datas, nomes de suspeitos, pistas reais e a solução jurídica exata registrada pela história. **No entanto, é expressamente proibido revelar quem foi o culpado ou assassino no início ou durante a investigação**.
2. **Pacing Investigativo**: Apresente o caso no "dia seguinte" ao ocorrido. Descreva o cenário inicial da descoberta do crime e as primeiras pistas disponíveis na época. Permita que o usuário explore os depoimentos de suspeitos históricos, solicite laudos periciais e tente deduzir quem cometeu o crime por conta própria.
3. **Resolução**: Apenas confirme se o usuário está correto quando ele formalizar a acusação com as respectivas evidências históricas na Fase V.

### DIRETRIZ B - CASOS FICTÍCIOS DINÂMICOS
Se o usuário solicitar um caso fictício, ou disser "Gere um caso aleatório", crie na hora um cenário contendo:
1. **Consistência Lógica**: Um mistério matematicamente lógico, onde o culpado cometeu um deslize sutil que contradiz seu álibi ou que está ligado a uma pista física.
2. **Três Suspeitos**: Defina três personagens com motivações plausíveis (financeiras, passionais, profissionais ou vingança) e álibis inicialmente aceitáveis, mas que escondem segredos.
3. **Três Pistas Físicas**: Distribua as pistas de modo que exijam diferentes ações do usuário (análise laboratorial, reconstituição ou interrogação cruzada).

---

## 3. MECÂNICA E ETAPAS DO JOGO

### FASE I: O INGRESSO E APRESENTAÇÃO
* Inicie o jogo descrevendo a atmosfera da sala de arquivos da delegacia. Apresente as opções de forma imersiva, instigando o usuário a escolher se prefere abrir o arquivo de um crime real histórico ou gerar uma nova ocorrência fictícia.

### FASE II: DESCOBERTA E COLETA DE PROVAS
* Quando o caso for definido, descreva o crime em parágrafos ricos em detalhes (onde o corpo foi encontrado, a causa da morte, o estado da cena do crime e os primeiros relatórios da perícia técnica de campo).
* Permita que o usuário decida para onde ir (visitar o necrotério, analisar a cena do crime, coletar imagens de câmeras ou examinar objetos pessoais).

### FASE III: MOTOR DE INTERROGATÓRIOS
Se o usuário solicitar interrogar um suspeito específico:
1. **Mudança de Voz Temporária**: Inicie o parágrafo assumindo o papel, a linguagem corporal, as hesitações e a fala do suspeito em questão. Mostre as emoções do personagem (medo, arrogância, indiferença, nervosismo).
2. **Comentário de Parceiro**: Na mesma resposta, feche o parágrafo retornando ao papel de detetive parceiro, falando em voz baixa com o usuário sobre o que você acabou de observar (por exemplo: apontando uma contradição de álibi ou um sinal de nervosismo físico).

### FASE IV: PERÍCIA FORENSE E LAUDOS
* O usuário pode solicitar exames avançados ao laboratório (como testes de DNA, toxicologia, balística ou recuperação de dados de celulares).
* Não forneça as respostas laboratoriais de imediato. Descreva o processo do laboratório e apresente o resultado em parágrafos descritivos contendo termos técnicos realistas.

### FASE V: ACUSAÇÃO E ENCERRAMENTO DO CASO
Para encerrar a investigação, o usuário deve declarar formalmente quem é o culpado, o motivo do crime e a prova incontestável que o incrimina.
* **Desfecho de Vitória**: Se a linha lógica estiver correta (ou corresponder ao desfecho real histórico), narre com suspense e realismo a prisão do criminoso, o interrogatório de confissão final e a elaboração do relatório para o Ministério Público.
* **Desfecho de Derrota**: Se o usuário insistir em acusações sem fundamento, negligenciar as pistas principais ou acusar inocentes repetidamente, narre de forma trágica as consequências (por exemplo: o suspeito real descobre a investigação e foge, as provas prescrevem, ou o culpado realiza uma nova ação criminosa para encobrir seus rastros).
"""

# Inicializa o cliente do Gemini usando a chave do .env
client = genai.Client(api_key=os.getenv("GENAI_KEY"))

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "ch@tb07")

# Configuração do Socket.IO para produção:
# Removemos a definição rígida de async_mode='threading' para permitir que o Socket.IO
# detecte o Gevent de forma nativa e automática quando hospedado no Render,
# otimizando o tempo de resposta e a estabilidade.
socketio = SocketIO(app, cors_allowed_origins="*")

# Dicionário em memória que mapeia o session_id persistente para o objeto de chat do Gemini
active_chats = {}

def get_user_chat(client_session_id=None):
    """
    Recupera ou gera uma sessão do Gemini utilizando um identificador de sessão persistente.
    Para evitar a perda de histórico em quedas de rede, prioriza o session_id
    enviado pelo cliente ou o armazenado na sessão do Flask.
    """
    # 1. Tenta recuperar o ID enviado diretamente pelo cliente ou pela sessão do Flask
    session_id = client_session_id
    if not session_id:
        if 'session_id' not in session:
            session['session_id'] = str(uuid4())
            print(f"Nova session_id gerada no Flask: {session['session_id']}")
        session_id = session['session_id']

    # 2. Se a ID não possui um chat associado na memória, cria um novo
    if session_id not in active_chats or active_chats[session_id] is None:
        print(f"Instanciando novo prontuário de inquérito para o ID de sessão: {session_id}")
        try:
            chat_session = client.chats.create(
                model=MODELO,
                config=types.GenerateContentConfig(system_instruction=instrucoes)
            )
            active_chats[session_id] = chat_session
        except Exception as e:
            app.logger.error(f"Falha ao iniciar o chat Gemini para o ID de sessão {session_id}: {e}", exc_info=True)
            raise
    
    return active_chats[session_id], session_id


@app.route('/')
def root():
    return jsonify({
        "api-websocket": "Detetive de True Crime Dinâmico",
        "status": "Funcionando",
        "version": "1,0"
    })


# =====================================================================
# EVENTOS SOCKET.IO
# =====================================================================

@socketio.on('connect')
def handle_connect():
    """
    Acionado no momento em que a conexão é estabelecida.
    Gera a mensagem de abertura imersiva sem revelar detalhes do desfecho dos casos.
    """
    sid = request.sid
    print(f"Conexão aceita via rádio: {sid}")
    
    try:
        # Recupera ou inicializa a sessão associada
        user_chat, session_id = get_user_chat()
        
        # Envia comando de inicialização solicitando a Fase I
        resposta_inicial = user_chat.send_message(
            "Execute a FASE I das suas instruções de sistema. Escreva uma mensagem curta e imersiva de boas-vindas ambientando o escritório e convide o usuário a digitar ou selecionar se prefere abrir o arquivo de um caso real histórico conhecido ou de um novo caso fictício gerado na hora. Mantenha o mistério sobre qualquer suspeito."
        )
        
        texto_inicial = (
            resposta_inicial.text
            if hasattr(resposta_inicial, 'text')
            else resposta_inicial.candidates[0].content.parts[0].text
        )
        
        # Envia a confirmação de conexão e a mensagem inicial para o front-end
        emit('status_conexao', {'data': 'Conectado com sucesso.', 'session_id': session_id})
        emit('nova_mensagem', {"remetente": "bot", "texto": texto_inicial, "session_id": session_id})
        
    except Exception as e:
        app.logger.error(f"Erro ao conectar ou abrir inquérito para {sid}: {e}", exc_info=True)
        emit('erro', {'erro': 'Não foi possível estabelecer contato com o arquivo central.'})


@socketio.on('enviar_mensagem')
def handle_enviar_mensagem(data):
    """
    Processa os comandos e deduções do jogador.
    Aceita um 'session_id' opcional enviado pelo payload do cliente para maior resiliência.
    """
    sid = request.sid
    try:
        mensagem_usuario = data.get("mensagem")
        client_session_id = data.get("session_id") # Opcional enviado pelo front-end para evitar perda de histórico
        
        app.logger.info(f"Dados recebidos do terminal {sid}: {mensagem_usuario}")

        if not mensagem_usuario:
            emit('erro', {"erro": "A anotação de comando está em branco."})
            return

        # Recupera o chat persistente usando o session_id recebido
        user_chat, session_id = get_user_chat(client_session_id)
        if user_chat is None:
            emit('erro', {"erro": "Arquivo criminal inacessível no momento."})
            return

        # Envia a entrada do usuário para o modelo do Gemini
        resposta_gemini = user_chat.send_message(mensagem_usuario)

        resposta_texto = (
            resposta_gemini.text
            if hasattr(resposta_gemini, 'text')
            else resposta_gemini.candidates[0].content.parts[0].text
        )
        
        emit('nova_mensagem', {"remetente": "bot", "texto": resposta_texto, "session_id": session_id})

    except Exception as e:
        app.logger.error(f"Erro ao processar as deduções de {sid}: {e}", exc_info=True)
        emit('erro', {"erro": f"Falha ao gerar o relatório: {str(e)}"})


@socketio.on('disconnect')
def handle_disconnect():
    """
    Acionado quando a conexão cai ou é fechada pelo usuário.
    IMPORTANTÍSSIMO: Para evitar que o usuário perca todo o progresso do inquérito policial
    durante oscilações de rede ou recargas de página, NÃO removemos os dados de 'active_chats' aqui.
    A sessão permanecerá segura em memória sob o ID da sessão.
    """
    sid = request.sid
    print(f"Sessão de rádio interrompida temporariamente para a conexão: {sid}")


if __name__ == "__main__":
    socketio.run(app)