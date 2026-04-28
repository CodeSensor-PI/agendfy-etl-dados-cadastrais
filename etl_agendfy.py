import pandas as pd
import re
import mysql.connector
import random
import string
import bcrypt

# =========================
# SEGURANÇA
# =========================

def gerar_email(nome):
    if not nome:
        nome = "user"
    base = nome.lower().replace(" ", "").replace(".", "")
    return f"{base}_{random.randint(10000,99999)}@temp.local"


def gerar_senha():
    senha = ''.join(random.choices(
        string.ascii_letters + string.digits + "!@#$%", k=10
    ))
    hash_senha = bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()
    return senha, hash_senha


# =========================
# TRANSFORMAÇÕES
# =========================

def tratar_endereco(valor):
    if pd.isna(valor):
        return None, None
    partes = valor.split(',')
    if len(partes) < 2:
        return valor.strip(), None
    return ",".join(partes[:-1]).strip(), partes[-1].strip()


def tratar_contato_emergencia(valor):
    try:
        nome = re.search(r'^(.*?)\s*\(', valor).group(1)
        tipo = re.search(r'\((.*?)\)', valor).group(1)
        telefone = re.search(r'-\s*(.*)', valor).group(1)
        return nome, tipo, telefone
    except:
        return None, None, None


def tratar_medicacao(valor):
    if str(valor).strip().lower() == "nenhuma":
        return None, None, None
    try:
        nome = re.search(r'^(.*?)\s*\(', valor).group(1)
        dosagem = re.search(r'\((\d+)([a-zA-Z]+)\)', valor)
        return nome, int(dosagem.group(1)), dosagem.group(2)
    except:
        return None, None, None


def tratar_profissional(valor):
    try:
        nome = re.search(r'^(.*?)\s*\(', valor).group(1)
        especialidade = re.search(r'\((.*?)\)', valor).group(1)
        return nome, especialidade
    except:
        return None, None


def limpar_doc(valor):
    if pd.isna(valor):
        return None
    return re.sub(r'[.\-]', '', str(valor))


# =========================
# CONEXÃO
# =========================

conn = mysql.connector.connect(
    host="localhost",
    user="sptech",
    password="123",
    database="agendfy_etl"
)

cursor = conn.cursor()

# =========================
# EXTRACT
# =========================

df = pd.read_excel(r"C:\Users\2\Documents\dados_cadastrais.xlsx")

# =========================
# CACHE (evitar duplicidade)
# =========================
usuarios_cache = {}

# =========================
# LOAD
# =========================

try:
    for _, row in df.iterrows():

        # ===== TRANSFORM =====
        address, state = tratar_endereco(row.get("Endereço"))
        ec_nome, ec_tipo, ec_tel = tratar_contato_emergencia(row.get("Contato de Emergência"))
        med_nome, med_qtd, med_tipo = tratar_medicacao(row.get("Medicação"))
        prof_nome, prof_esp = tratar_profissional(row.get("Profissionais"))

        rg = limpar_doc(row.get("RG"))
        cpf = limpar_doc(row.get("CPF"))

        # =========================
        # USERS (PSICÓLOGO)
        # =========================
        if prof_nome not in usuarios_cache:

            email_user = gerar_email(prof_nome)
            _, senha_hash_user = gerar_senha()

            cursor.execute("""
                INSERT INTO users (email, password, name, psicolog_especiality, role)
                VALUES (%s, %s, %s, %s, %s)
            """, (email_user, senha_hash_user, prof_nome, prof_esp, "PSICOLOGO"))

            usuarios_cache[prof_nome] = cursor.lastrowid

        user_id = usuarios_cache[prof_nome]

        # =========================
        # MEDICAÇÃO
        # =========================
        medicacao_id = None

        if med_nome:
            cursor.execute("""
                INSERT INTO medicacao (nome, dosagem_qtd, dosagem_tipo)
                VALUES (%s, %s, %s)
            """, (med_nome, med_qtd, med_tipo))

            medicacao_id = cursor.lastrowid

        # =========================
        # PATIENT
        # =========================

        email_patient = gerar_email(row.get("Nome Completo"))
        _, senha_hash_patient = gerar_senha()

        cursor.execute("""
            INSERT INTO patients (
                name, phone, address, state,
                emergency_contact, emergency_contact_type, emergency_phone,
                rg, cpf, fk_psicologo, fk_medicacao,
                email, password
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            row.get("Nome Completo"),
            row.get("Telefone"),
            address,
            state,
            ec_nome,
            ec_tipo,
            ec_tel,
            rg,
            cpf,
            user_id,
            medicacao_id,
            email_patient,
            senha_hash_patient
        ))

    conn.commit()
    print("✅ ETL concluído com sucesso!")

except Exception as e:
    conn.rollback()
    print("❌ Erro no ETL:", e)

finally:
    cursor.close()
    conn.close()