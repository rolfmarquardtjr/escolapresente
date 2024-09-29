from flask import Flask, request
import sqlite3

app = Flask(__name__)

# Função para registrar a resposta no banco de dados
def registrar_resposta(numero, resposta):
    try:
        # Conectando ao banco de dados SQLite
        conn = sqlite3.connect('attendance.db')
        c = conn.cursor()

        # Verificação para garantir que estamos salvando no número correto
        print(f"Salvando resposta no banco de dados. Número: {numero}, Resposta: {resposta}")
        
        # Atualizar o banco de dados com a resposta recebida
        c.execute("UPDATE attendance_log SET resposta = ? WHERE numero = ?", (resposta, numero))
        conn.commit()

        # Adiciona verificação para garantir que o registro foi atualizado
        c.execute("SELECT resposta FROM attendance_log WHERE numero = ?", (numero,))
        saved_resposta = c.fetchone()
        if saved_resposta:
            print(f"Resposta salva com sucesso no banco de dados: {saved_resposta[0]}")
        else:
            print("Falha ao salvar a resposta no banco de dados.")
        
    except sqlite3.Error as e:
        print(f"Erro ao salvar a resposta no banco de dados: {e}")
    finally:
        # Fechar a conexão com o banco de dados
        conn.close()


@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    print(f"Dados recebidos no webhook: {data}")  # Log para verificar o que está sendo recebido

    # Garantir que os dados esperados estão sendo recebidos
    if 'from' in data and 'body' in data:
        # No backend.py, remova o @c.us e garanta que o número seja uma string
        numero = data['from'].replace('@c.us', '').replace('+', '').strip()  # Remove o + e espaços extras

        resposta = data['body']  # Captura o texto da mensagem
        
        # Registrar a resposta no banco de dados
        registrar_resposta(numero, resposta)
        
        return "Resposta registrada com sucesso", 200
    return "Dados inválidos", 400

if __name__ == '__main__':
    app.run(port=5000)
