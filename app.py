import streamlit as st
import sqlite3
import pandas as pd
import requests
import io
from datetime import datetime
import base64
import time
from PIL import Image
from io import BytesIO

# Função para inicializar o banco de dados e criar tabelas se não existirem
def inicializar_banco_de_dados():
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()

    # Criar tabela de usuários
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            password TEXT NOT NULL
        )
    ''')

    # Criar tabela de configuração
    c.execute('''
        CREATE TABLE IF NOT EXISTS config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_template TEXT NOT NULL
        )
    ''')

    # Criar tabela de logs de presença
    c.execute('''
        CREATE TABLE IF NOT EXISTS attendance_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aluno TEXT NOT NULL,
            serie TEXT NOT NULL,
            data TEXT NOT NULL,
            responsavel TEXT,
            numero TEXT,
            status TEXT NOT NULL,
            resposta TEXT
        )
    ''')

    # Inserir usuários admin padrão se eles não existirem
    c.execute("SELECT * FROM users WHERE username='Marcelo'")
    if not c.fetchone():
        c.execute("INSERT INTO users (username, password) VALUES ('Marcelo', 'Edu2024')")
        c.execute("INSERT INTO users (username, password) VALUES ('Simone', '300190')")
        conn.commit()

    # Inserir um modelo de mensagem padrão se ele não existir
    c.execute("SELECT * FROM config WHERE id=1")
    if not c.fetchone():
        c.execute("INSERT INTO config (message_template) VALUES ('Prezado {nome_responsavel}, informamos que o aluno {nome_aluno} esteve ausente na data de hoje.')")
        conn.commit()

    conn.close()

# Inicializa o banco de dados
inicializar_banco_de_dados()

# Função para melhorar o layout
def set_page_style():
    st.markdown(
        """
        <style>
        .reportview-container {
            background: #f4f4f4;
        }
        .sidebar .sidebar-content {
            background: #004466;
            color: white;
        }
        h1 {
            color: #004466;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

# Função para enviar mensagem via API do Node.js
def enviar_mensagem(numero, mensagem):
    url = 'http://localhost:3000/send'  # Certifique-se de que o backend Node.js esteja rodando nessa URL
    payload = {
        'numero': str(int(numero)),  # Garantir que o número seja tratado como string e sem decimais
        'mensagem': mensagem
    }
    try:
        # Tentar enviar a mensagem via API do Node.js
        response = requests.post(url, json=payload)
        response.raise_for_status()  # Isso vai gerar um erro se o status não for 200 OK
        return {'status': 'sucesso', 'mensagem': f'Mensagem enviada para {numero}'}
    except requests.exceptions.RequestException as e:
        # Captura qualquer erro durante a requisição e retorna a mensagem de erro
        st.error(f"Erro ao enviar mensagem: {e}")
        return {'status': 'erro', 'mensagem': f'Erro ao enviar mensagem para {numero}: {e}'}

# Conexão ao banco de dados SQLite usando "with" para garantir que a conexão seja fechada corretamente
def registrar_presenca(aluno, serie, data, responsavel, numero, status):
    try:
        with sqlite3.connect('attendance.db') as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO attendance_log (aluno, serie, data, responsavel, numero, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (aluno, serie, data, responsavel, numero, status))
            conn.commit()
    except sqlite3.Error as e:
        st.error(f"Erro ao registrar presença: {e}")

# Função para resetar o WhatsApp via API do backend
def reset_whatsapp():
    try:
        response = requests.post('http://localhost:3000/reset-whatsapp')
        if response.status_code == 200:
            st.success("WhatsApp desconectado com sucesso. Aguardando novo QR Code...")
        else:
            st.error(f"Erro ao resetar WhatsApp: {response.json().get('error', 'Desconhecido')}")
    except Exception as e:
        st.error(f"Erro ao conectar com a API de reset: {e}")

# Função para obter o QR Code via API do backend
def get_qr_code():
    try:
        response = requests.get('http://localhost:3000/get-qr')
        if response.status_code == 200 and 'qr' in response.json():
            # Decodificar o QR Code em base64
            qr_code_base64 = response.json()['qr'].split(',')[1]  # Remove o cabeçalho 'data:image/png;base64,'
            qr_code_bytes = base64.b64decode(qr_code_base64)
            return qr_code_bytes  # Retorna os bytes da imagem
        else:
            st.error("Erro ao obter QR Code.")
            return None
    except Exception as e:
        st.error(f"Erro ao conectar com a API de QR Code: {e}")
        return None

# Função principal do Streamlit para rodar a interface
def run_streamlit():
    set_page_style()
    st.title("Sistema de Presença e Mensagens Automáticas")

    # Página de Login
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False

    if not st.session_state['logged_in']:
        st.header("Login")
        username = st.text_input("Usuário", placeholder="Digite seu usuário")
        password = st.text_input("Senha", type="password", placeholder="Digite sua senha")
        if st.button("Entrar"):
            with sqlite3.connect('attendance.db') as conn:
                c = conn.cursor()
                c.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
                user = c.fetchone()
                if user:
                    st.session_state['logged_in'] = True
                    st.session_state['username'] = username
                    st.success(f"Bem-vindo, {username}!")
                else:
                    st.error("Usuário ou senha inválidos")
    else:
        st.sidebar.header(f"Bem-vindo, {st.session_state['username']}")

        # Adicionar botão de logout no sidebar
        if st.sidebar.button("Logout"):
            st.session_state['logged_in'] = False
            st.rerun()

        # Adicionando o botão de reset no menu lateral
        if st.sidebar.button("Reset WhatsApp Number"):
            reset_whatsapp()

        # Exibe o QR Code atualizado, se houver
        st.subheader("QR Code para Conectar no WhatsApp")
        qr_code_image = get_qr_code()
        if qr_code_image:
            # Converte a imagem para bytes para o download
            download_button = st.download_button(
                label="Baixar QR Code",
                data=qr_code_image,
                file_name="whatsapp_qr.png",
                mime="image/png"
            )
        else:
            st.warning("Aguardando novo QR Code...")

        # Menu lateral para navegação
        page = st.sidebar.selectbox("Escolha a página", ["Página Principal", "Configurações", "Exportar/Importar Alunos", "Exportar Logs", "Mensagens Recebidas", "Editar Aluno"])

        if page == "Página Principal":
            # Página principal com calendário e série
            st.header("Registro de Presença")

            current_date = st.date_input("Selecione a data", datetime.now())
            if current_date.weekday() in (5, 6):
                st.error("Finais de semana não são permitidos.")
            else:
                # Carregar e exibir séries e alunos
                file_path = 'alunos_atualizados.xlsx'
                df = pd.read_excel(file_path)
                series = df['série'].unique()
                selected_series = st.selectbox("Selecione a série", series)
                selected_students = df[df['série'] == selected_series]

                st.subheader(f"Alunos da Série {selected_series}")
                attendance = {}
                for i, row in selected_students.iterrows():
                    responsavel = row['responsavel'] if not pd.isna(row['responsavel']) else 'N/A'
                    attendance[row['Nome do Aluno']] = st.checkbox(f"{row['Nome do Aluno']} - Responsável: {responsavel}")

                if st.button("Enviar Mensagens"):
                    # Pegar mensagem template do banco
                    with sqlite3.connect('attendance.db') as conn:
                        c = conn.cursor()
                        c.execute("SELECT message_template FROM config WHERE id=1")
                        template = c.fetchone()
                        if template:
                            template = template[0]
                        else:
                            template = "Prezado {nome_responsavel}, informamos que o aluno {nome_aluno} esteve ausente na data de hoje."

                    # Enviar mensagens reais via API do Node.js e registrar no banco de dados
                    for aluno, faltou in attendance.items():
                        if faltou:
                            responsavel = selected_students[selected_students['Nome do Aluno'] == aluno]['responsavel'].values[0]
                            numero = str(int(selected_students[selected_students['Nome do Aluno'] == aluno]['Celular responsável'].values[0]))  # Converte o número para string sem ponto decimal
                            if pd.isna(numero):
                                st.warning(f"Mensagem não enviada para {aluno}. Número de telefone faltando.")
                            else:
                                mensagem = template.replace("{nome_aluno}", aluno).replace("{nome_responsavel}", responsavel)
                                resultado = enviar_mensagem(numero, mensagem)
                                st.write(f"Resultado: {resultado['mensagem']}")

                                # Registrar log de presença no banco de dados
                                registrar_presenca(aluno, selected_series, str(current_date), responsavel, numero, "Mensagem enviada")

        elif page == "Configurações":
            # Página de configuração
            st.header("Configurações de Mensagens")

            # Carregar o modelo de mensagem atual
            with sqlite3.connect('attendance.db') as conn:
                c = conn.cursor()
                c.execute("SELECT message_template FROM config WHERE id=1")
                template = c.fetchone()

            # Verificar se o template já existe
            if template:
                template = template[0]
            else:
                template = "Prezado {nome_responsavel}, informamos que o aluno {nome_aluno} esteve ausente na data de hoje."

            # Exibir área para editar a mensagem
            new_template = st.text_area("Modelo de mensagem", template)

            # Salvar o modelo de mensagem atualizado
            if st.button("Salvar Modelo"):
                with sqlite3.connect('attendance.db') as conn:
                    c = conn.cursor()
                    c.execute("SELECT * FROM config WHERE id=1")
                    if c.fetchone():
                        c.execute("UPDATE config SET message_template = ? WHERE id = 1", (new_template,))
                    else:
                        c.execute("INSERT INTO config (message_template) VALUES (?)", (new_template,))
                    conn.commit()
                st.success("Modelo de mensagem atualizado com sucesso!")

        elif page == "Exportar/Importar Alunos":
            # Página para exportar ou importar planilhas
            st.header("Exportar ou Importar Alunos")
            file_path = 'alunos_atualizados.xlsx'

            if st.button("Exportar Planilha de Alunos"):
                df = pd.read_excel(file_path)
                df.to_excel('alunos_exportados.xlsx', index=False)
                st.success("Planilha exportada com sucesso.")

            uploaded_file = st.file_uploader("Importar nova planilha de alunos", type="xlsx")
            if uploaded_file:
                df_new = pd.read_excel(uploaded_file)
                df_new.to_excel(file_path, index=False)
                st.success("Nova planilha importada com sucesso!")

        elif page == "Exportar Logs":
            # Página para exportar logs de presença
            st.header("Exportar Logs de Presença")

            selected_date = st.date_input("Selecione a data dos logs", datetime.now())
            selected_series = st.text_input("Digite a série (ex: 1A, 2B)")

            if st.button("Exportar Logs"):
                with sqlite3.connect('attendance.db') as conn:
                    query = "SELECT * FROM attendance_log WHERE data = ? AND serie = ?"
                    logs = pd.read_sql_query(query, conn, params=(str(selected_date), selected_series))

                if logs.empty:
                    st.warning("Nenhum log encontrado para a data e série selecionada.")
                else:
                    # Gerar o arquivo Excel para download
                    log_file = io.BytesIO()
                    logs.to_excel(log_file, index=False)
                    log_file.seek(0)

                    st.download_button(
                        label="Baixar Logs",
                        data=log_file,
                        file_name=f'logs_{selected_series}_{selected_date}.xlsx',
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                    st.success(f"Logs exportados com sucesso.")

        elif page == "Mensagens Recebidas":
            # Página para exibir mensagens recebidas
            st.header("Mensagens Recebidas")

            # Certifique-se de abrir a conexão com o banco de dados
            with sqlite3.connect('attendance.db') as conn:
                logs = pd.read_sql_query("SELECT * FROM attendance_log WHERE resposta IS NOT NULL", conn)

                if logs.empty:
                    st.write("Nenhuma resposta foi recebida ainda.")
                else:
                    st.write(f"{len(logs)} respostas recebidas.")
                    st.dataframe(logs[['aluno', 'responsavel', 'data', 'resposta']])

        elif page == "Editar Aluno":
            # Página para editar um aluno individualmente
            st.header("Editar Informações de Aluno")

            df = pd.read_excel('alunos_atualizados.xlsx')
            alunos = df['Nome do Aluno'].unique()

            # Selecionar aluno para edição
            selected_aluno = st.selectbox("Selecione o aluno", alunos)

            aluno_data = df[df['Nome do Aluno'] == selected_aluno]

            # Exibir dados atuais do aluno e permitir edição
            nome = st.text_input("Nome do Aluno", aluno_data['Nome do Aluno'].values[0])
            responsavel = st.text_input("Responsável", aluno_data['responsavel'].values[0])
            celular = st.text_input("Celular do Responsável", aluno_data['Celular responsável'].values[0])
            serie = st.text_input("Série", aluno_data['série'].values[0])

            if st.button("Salvar Alterações"):
                # Atualizar os dados no DataFrame
                df.loc[df['Nome do Aluno'] == selected_aluno, ['Nome do Aluno', 'responsavel', 'Celular responsável', 'série']] = [nome, responsavel, celular, serie]
                
                # Salvar a planilha atualizada
                df.to_excel('alunos_atualizados.xlsx', index=False)
                st.success(f"Dados de {selected_aluno} atualizados com sucesso!")

# Executar o Streamlit
if __name__ == '__main__':
    run_streamlit()
