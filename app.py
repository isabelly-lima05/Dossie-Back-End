import sys

# Compatibilidade para servidores assíncronos em ambientes Linux/Production
if sys.platform != "win32":
    try:
        from gevent import monkey
        monkey.patch_all()
    except ImportError:
        print("Gevent não instalado!")

from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from google import genai
from google.genai import types
from dotenv import load_dotenv
import os

# Carrega as variáveis ocultas do arquivo .env
load_dotenv()

# Define o modelo de IA estável e rápido para chat dinâmico
MODELO = "gemini-2.5-flash"

# MANUAL DE OPERAÇÕES DO SISTEMA: DETETIVE DE TRUE CRIME (RPG IMERSIVO)
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
O jogador tem acesso a uma biblioteca virtual infinita de casos (representando mais de 20.000 investigações possíveis):

### DIRETRIZ A - CASOS REAIS HISTÓRICOS
Se o usuário solicitar um caso real histórico (exemplos: Caso Suzane von Richthofen, Caso Elize Matsunaga, Caso Isabella Nardoni, Caso Ted Bundy, Caso Jack o Estripador, etc.):
1. **Fidelidade Histórica**: Reconstitua os fatos, datas, nomes de suspeitos, pistas reais e a solução jurídica exata do caso histórico de forma rigorosa. Não altere o culpado ou os fatos documentados pela história.
2. **Pacing Investigativo**: Não entregue a solução imediatamente. Apresente o caso na fase inicial de investigação (como se vocês estivessem atuando no dia seguinte ao ocorrido) e permita que o usuário explore os depoimentos e pistas originais da época para chegar à mesma conclusão histórica.

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
* **Desfecho de Vitória**: Se a linha lógica estiver correta, narre com suspense e realismo a prisão do criminoso, o interrogatório de confissão final e a elaboração do relatório para o Ministério Público.
* **Desfecho de Derrota**: Se o usuário insistir em acusações sem fundamento, negligenciar as pistas principais ou acusar inocentes repetidamente, narre de forma trágica as consequências (por exemplo: o suspeito real descobre a investigação e foge, as provas prescrevem, ou o culpado realiza uma nova ação criminosa para encobrir seus rastros).
"""

# Inicializa o cliente do Gemini usando a nova API do Google GenAI
client = genai.Client(api_key=os.getenv("GENAI_KEY"))

# Cria o aplicativo principal Flask
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "ch@tb07")

# Configuração de SocketIO com suporte CORS e sem persistência de cookie session do Flask
socketio = SocketIO(app, cors_allowed_origins="*", manage_session=False)

# Dicionário na memória do servidor para gerenciar as instâncias ativas do chat por ID do socket (request.sid)
active_chats = {}

def get_user_chat(sid):
    """
    Função de gerenciamento de sessões individuais usando o identificador de socket.
    Dessa forma, cada conexão mantém sua própria instância do chat sem depender de cookies.
    """
    if sid not in active_chats or active_chats[sid] is None:
        print(f"Instanciando prontuário investigativo para a conexão: {sid}")
        try:
            chat_session = client.chats.create(
                model=MODELO,
                config=types.GenerateContentConfig(system_instruction=instrucoes)
            )
            active_chats[sid] = chat_session
        except Exception as e:
            app.logger.error(f"Falha ao iniciar o chat Gemini para a conexão {sid}: {e}", exc_info=True)
            raise
    
    return active_chats[sid]


@app.route('/')
def root():
    return jsonify({
        "api-websocket": "Detetive de True Crime Dinâmico",
        "status": "Funcionando"
    })


# ------------------------------------------------------------------
# EVENTOS SOCKET.IO
# ------------------------------------------------------------------

@socketio.on('connect')
def handle_connect():
    """
    Disparado assim que a conexão de rede do terminal do usuário é estabelecida.
    Gera o monólogo de abertura inicial dinamicamente usando a API.
    """
    sid = request.sid
    print(f"Terminal conectado: {sid}")
    
    try:
        # Prepara a sessão de chat correspondente para esta conexão única
        user_chat = get_user_chat(sid)
        print(f"Sessão de trabalho para {sid} inicializada com sucesso.")
        
        # Envia a diretriz inicial silenciosa para introduzir o caso de forma literária e imersiva
        resposta_inicial = user_chat.send_message(
            "Execute a FASE I das suas instruções de sistema. Escreva um monólogo de abertura atmosférico ambientando a delegacia, descreva a noite e convide o usuário de forma imersiva a escolher entre um caso real histórico conhecido (como Suzane von Richthofen ou Elize Matsunaga) ou um caso fictício gerado na hora. Utilize parágrafos descritivos completos."
        )
        
        texto_inicial = (
            resposta_inicial.text
            if hasattr(resposta_inicial, 'text')
            else resposta_inicial.candidates[0].content.parts[0].text
        )
        
        # Envia as saídas de conexão de segurança e a primeira resposta narrativa da IA
        emit('status_conexao', {'data': 'Conexão autorizada.', 'session_id': sid})
        emit('nova_mensagem', {"remetente": "bot", "texto": texto_inicial, "session_id": sid})
        
    except Exception as e:
        app.logger.error(f"Erro ao conectar e iniciar histórico do prontuário para {sid}: {e}", exc_info=True)
        emit('erro', {'erro': 'Não foi possível carregar o banco de dados de crimes do servidor.'})


@socketio.on('enviar_mensagem')
def handle_enviar_mensagem(data):
    """
    Disparado quando o usuário envia uma nova anotação ou comando ao servidor.
    """
    sid = request.sid
    try:
        mensagem_usuario = data.get("mensagem")
        app.logger.info(f"Mensagem recebida do Inspetor {sid}: {mensagem_usuario}")

        if not mensagem_usuario:
            emit('erro', {"erro": "A anotação de comando está em branco."})
            return

        # Recupera a sessão ativa do dicionário em memória
        user_chat = get_user_chat(sid)
        if user_chat is None:
            emit('erro', {"erro": "Arquivo criminal de trabalho inacessível."})
            return

        # Envia a ação para processamento cognitivo do Gemini
        resposta_gemini = user_chat.send_message(mensagem_usuario)

        resposta_texto = (
            resposta_gemini.text
            if hasattr(resposta_gemini, 'text')
            else resposta_gemini.candidates[0].content.parts[0].text
        )
        
        # Retorna a saída para exibição na folha de relatórios do front-end
        emit('nova_mensagem', {"remetente": "bot", "texto": resposta_texto, "session_id": sid})
        app.logger.info(f"Dados enviados para o terminal {sid}: {resposta_texto}")

    except Exception as e:
        app.logger.error(f"Erro ao processar as deduções de {sid}: {e}", exc_info=True)
        emit('erro', {"erro": f"Ocorreu uma falha ao compilar o relatório: {str(e)}"})


@socketio.on('disconnect')
def handle_disconnect():
    """
    Disparado quando a conexão do usuário é perdida ou encerrada.
    Limpa a memória do servidor para evitar acúmulo de dados desnecessários.
    """
    sid = request.sid
    if sid in active_chats:
        del active_chats[sid]
    print(f"Terminal desconectado e recursos limpos para: {sid}")


if __name__ == "__main__":
    socketio.run(app)