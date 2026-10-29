import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date
from sqlalchemy import create_engine, text

st.set_page_config(page_title="Prodigy - Gestão de Obras", layout="wide")

# ---------------------------------------------------------
# 0. TELA DE LOGIN
# ---------------------------------------------------------
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if not st.session_state["password_correct"]:
        st.markdown("### 🏗️ Prodigy - Acesso Restrito")
        senha = st.text_input("Digite a senha da obra", type="password")
        if st.button("Entrar"):
            if senha == st.secrets["SENHA_OBRA"]:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("Senha incorreta.")
        return False
    return True

if not check_password():
    st.stop()

# ---------------------------------------------------------
# 1. CONEXÃO E ESTRUTURAÇÃO DO BANCO (V2 - Metragem Real)
# ---------------------------------------------------------
@st.cache_resource
def init_connection():
    url = st.secrets["DB_URL"]
    # Força o SQLAlchemy a usar o motorista psycopg2 que instalamos
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return create_engine(url)

engine = init_connection()

def init_db():
    with engine.connect() as conn:
        # Novas tabelas V2 para não conflitar com a versão anterior baseada em percentual
        conn.execute(text('''CREATE TABLE IF NOT EXISTS tb_elementos_v2 (
                        id_elemento SERIAL PRIMARY KEY,
                        andar TEXT, ambiente TEXT, disciplina TEXT, 
                        identificacao TEXT, area_total_m2 NUMERIC)'''))
        
        conn.execute(text('''CREATE TABLE IF NOT EXISTS tb_regras_metragem (
                        disciplina TEXT, etapa TEXT, multiplicador NUMERIC)'''))
                        
        conn.execute(text('''CREATE TABLE IF NOT EXISTS tb_apontamentos_v2 (
                        id_apontamento SERIAL PRIMARY KEY,
                        id_elemento INTEGER, etapa TEXT, data_registo TEXT)'''))
                        
        conn.execute(text('''CREATE TABLE IF NOT EXISTS tb_efetivo (
                        data_registo TEXT, disciplina TEXT, qtd_funcionarios INTEGER,
                        PRIMARY KEY (data_registo, disciplina))'''))
        
        # Inserindo Regras de Multiplicadores (1.0 = 100% da área, 0.10 = 10% da área para reforços)
        result_regras = conn.execute(text("SELECT COUNT(*) FROM tb_regras_metragem")).scalar()
        if result_regras == 0:
            regras = [
                ('Drywall', '1ª Face', 1.0), ('Drywall', 'Reforços', 0.10), 
                ('Drywall', '2ª Face', 1.0), ('Drywall', 'Acabamentos', 1.0),
                ('Pintura', 'Emassamento', 1.0), ('Pintura', 'Lixa', 1.0), 
                ('Pintura', '1ª Demão', 1.0), ('Pintura', '2ª Demão', 1.0), ('Pintura', '3ª Demão', 1.0),
                ('Forro Modular', 'Estruturação', 1.0), ('Forro Modular', 'Plaqueamento', 1.0),
                ('Forro Gesso Liso', 'Estruturação', 1.0), ('Forro Gesso Liso', 'Plaqueamento', 1.0), ('Forro Gesso Liso', 'Acabamento', 1.0)
            ]
            for r in regras:
                conn.execute(text("INSERT INTO tb_regras_metragem (disciplina, etapa, multiplicador) VALUES (:1, :2, :3)"), 
                             {"1": r[0], "2": r[1], "3": r[2]})
            
        # Povoando o Levantamento Físico
        result_elem = conn.execute(text("SELECT COUNT(*) FROM tb_elementos_v2")).scalar()
        if result_elem == 0:
            andares_todos = ['10º Pavimento', '09º Pavimento', '08º Pavimento', '07º Pavimento', '06º Pavimento', '05º Pavimento', '04º Pavimento', '03º Pavimento']
            
            for andar in andares_todos:
                # WC 1 e WC 2 (Em todos os andares)
                for wc in ['WC 1', 'WC 2']:
                    for p in ['Parede 01', 'Parede 02', 'Parede 03', 'Parede 04']:
                        conn.execute(text("INSERT INTO tb_elementos_v2 (andar, ambiente, disciplina, identificacao, area_total_m2) VALUES (:1, :2, 'Drywall', :3, :4)"),
                                     {"1": andar, "2": wc, "3": p, "4": 2.50 * 3})
                    # Forro Gesso Liso WC e Pintura só no forro
                    conn.execute(text("INSERT INTO tb_elementos_v2 (andar, ambiente, disciplina, identificacao, area_total_m2) VALUES (:1, :2, 'Forro Gesso Liso', 'Teto', 5.00)"), {"1": andar, "2": wc})
                    conn.execute(text("INSERT INTO tb_elementos_v2 (andar, ambiente, disciplina, identificacao, area_total_m2) VALUES (:1, :2, 'Pintura', 'Teto', 5.00)"), {"1": andar, "2": wc})

                # Copa e Core (Em todos os andares)
                paredes_copa = [('Parede 01', 7.30), ('Parede 02', 7.30), ('Parede 04', 7.30), ('Pórtico', 7.30)]
                for p_nome, p_medida in paredes_copa:
                    conn.execute(text("INSERT INTO tb_elementos_v2 (andar, ambiente, disciplina, identificacao, area_total_m2) VALUES (:1, 'Copa', 'Drywall', :2, :3)"), {"1": andar, "2": p_nome, "3": p_medida * 3})
                conn.execute(text("INSERT INTO tb_elementos_v2 (andar, ambiente, disciplina, identificacao, area_total_m2) VALUES (:1, 'Core', 'Pintura', 'Parede 01', :2)"), {"1": andar, "2": 21.65 * 3})
                conn.execute(text("INSERT INTO tb_elementos_v2 (andar, ambiente, disciplina, identificacao, area_total_m2) VALUES (:1, 'Core', 'Pintura', 'Parede 02', :2)"), {"1": andar, "2": 9.80 * 3})

                # Booths (Regra geral: 10º andar tem 2 booths, os demais têm 3)
                qtd_booths = 2 if andar == '10º Pavimento' else 3
                for i in range(1, qtd_bo
