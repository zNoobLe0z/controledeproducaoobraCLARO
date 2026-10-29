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
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return create_engine(url)

engine = init_connection()

def init_db():
    with engine.connect() as conn:
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS tb_elementos_v2 (
                id_elemento SERIAL PRIMARY KEY,
                andar TEXT, 
                ambiente TEXT, 
                disciplina TEXT, 
                identificacao TEXT, 
                area_total_m2 NUMERIC
            )
        '''))
        
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS tb_regras_metragem (
                disciplina TEXT, 
                etapa TEXT, 
                multiplicador NUMERIC
            )
        '''))
                        
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS tb_apontamentos_v2 (
                id_apontamento SERIAL PRIMARY KEY,
                id_elemento INTEGER, 
                etapa TEXT, 
                data_registo TEXT
            )
        '''))
                        
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS tb_efetivo (
                data_registo TEXT, 
                disciplina TEXT, 
                qtd_funcionarios INTEGER,
                PRIMARY KEY (data_registo, disciplina)
            )
        '''))
        
        result_regras = conn.execute(text(
            "SELECT COUNT(*) FROM tb_regras_metragem"
        )).scalar()
        
        if result_regras == 0:
            regras = [
                ('Drywall', '1ª Face', 1.0), 
                ('Drywall', 'Reforços', 0.10), 
                ('Drywall', '2ª Face', 1.0), 
                ('Drywall', 'Acabamentos', 1.0),
                ('Pintura', 'Emassamento', 1.0), 
                ('Pintura', 'Lixa', 1.0), 
                ('Pintura', '1ª Demão', 1.0), 
                ('Pintura', '2ª Demão', 1.0), 
                ('Pintura', '3ª Demão', 1.0),
                ('Forro Modular', 'Estruturação', 1.0), 
                ('Forro Modular', 'Plaqueamento', 1.0),
                ('Forro Gesso Liso', 'Estruturação', 1.0), 
                ('Forro Gesso Liso', 'Plaqueamento', 1.0), 
                ('Forro Gesso Liso', 'Acabamento', 1.0)
            ]
            query_regra = text("""
                INSERT INTO tb_regras_metragem (disciplina, etapa, multiplicador) 
                VALUES (:1, :2, :3)
            """)
            for r in regras:
                conn.execute(query_regra, {"1": r[0], "2": r[1], "3": r[2]})
            
        result_elem = conn.execute(text(
            "SELECT COUNT(*) FROM tb_elementos_v2"
        )).scalar()
        
        if result_elem == 0:
            andares_todos = [
                '10º Pavimento', '09º Pavimento', '08º Pavimento', 
                '07º Pavimento', '06º Pavimento', '05º Pavimento', 
                '04º Pavimento', '03º Pavimento'
            ]
            
            query_insert = text("""
                INSERT INTO tb_elementos_v2 
                (andar, ambiente, disciplina, identificacao, area_total_m2) 
                VALUES (:1, :2, :3, :4, :5)
            """)
            
            for andar in andares_todos:
                for wc in ['WC 1', 'WC 2']:
                    paredes_wc = ['Parede 01', 'Parede 02', 'Parede 03', 'Parede 04']
                    for p in paredes_wc:
                        conn.execute(query_insert, {
                            "1": andar, "2": wc, "3": "Drywall", 
                            "4": p, "5": 2.50 * 3
                        })
                    conn.execute(query_insert, {
                        "1": andar, "2": wc, "3": "Forro Gesso Liso", 
                        "4": "Teto", "5": 5.00
                    })
                    conn.execute(query_insert, {
                        "1": andar, "2": wc, "3": "Pintura", 
                        "4": "Teto", "5": 5.00
                    })

                paredes_copa = [
                    ('Parede 01', 7.30), ('Parede 02', 7.30), 
                    ('Parede 04', 7.30), ('Pórtico', 7.30)
                ]
                for p_nome, p_medida in paredes_copa:
                    conn.execute(query_insert, {
                        "1": andar, "2": "Copa", "3": "Drywall", 
                        "4": p_nome, "5": p_medida * 3
                    })
                
                conn.execute(query_insert, {
                    "1": andar, "2": "Core", "3": "Pintura", 
                    "4": "Parede 01", "5": 21.65 * 3
                })
                conn.execute(query_insert, {
                    "1": andar, "2": "Core", "3": "Pintura", 
                    "4": "Parede 02", "5": 9.80 * 3
                })

                qtd_booths = 2 if andar == '10º Pavimento' else 3
                for i in range(1, qtd_booths + 1):
                    booth = f'Booth 0{i}'
                    paredes_booth = [
                        ('Parede 01', 2.25), 
                        ('Parede 02', 2.40), 
                        ('Parede 03', 2.25), 
                        ('Parede 04', 2.40)
                    ]
                    for p_nome, p_medida in paredes_booth:
                        conn.execute(query_insert, {
                            "1": andar, "2": booth, "3": "Drywall", 
                            "4": p_nome, "5": p_medida * 3
                        })
                    conn.execute(query_insert, {
                        "1": andar, "2": booth, "3": "Forro Modular", 
                        "4": "Teto", "5": 3.50
                    })

                if andar == '04º Pavimento':
                    reuniao_4 = [
                        ('Reunião 01', [
                            ('Parede 01', 3.65), ('Parede 02', 3.85), 
                            ('Parede 03', 3.65), ('Parede 04', 3.85)
                        ]),
                        ('Reunião 02', [
                            ('Parede 01', 3.65), ('Parede 02', 3.85), 
                            ('Parede 03', 3.65), ('Parede 04', 3.85)
                        ]),
                        ('Reunião 03', [
                            ('Parede 01', 3.00), ('Parede 03', 3.00), 
                            ('Parede 04', 3.75)
                        ])
                    ]
                    for r_nome, r_paredes in reuniao_4:
                        for p_nome, p_medida in r_paredes:
                            conn.execute(query_insert, {
                                "1": andar, "2": r_nome, "3": "Drywall", 
                                "4": p_nome, "5": p_medida * 3
                            })
                else:
                    for i in range(1, 4):
                        r_nome = f'Reunião 0{i}'
                        paredes_r = [
                            ('Parede 01', 4.50), 
                            ('Parede 02', 7.35), 
                            ('Parede 04', 7.35)
                        ]
                        for p_nome, p_medida in paredes_r:
                            conn.execute(query_insert, {
                                "1": andar, "2": r_nome, "3": "Drywall", 
                                "4": p_nome, "5": p_medida * 3
                            })

        conn.commit()

init_db()

# ---------------------------------------------------------
# 2. INTERFACE E NAVEGAÇÃO
# ---------------------------------------------------------
st.title("🏗️ Prodigy - Controle de Produção")
aba1, aba2, aba3 = st.tabs([
    "📋 Lançamento de Produção", 
    "👷 Controle de Efetivo", 
    "📊 Dashboard Gerencial"
])

with aba1:
    col1, col2, col3 = st.columns(3)
    df_elem = pd.read_sql(
        "SELECT DISTINCT andar, ambiente, disciplina FROM tb_elementos_v2", 
        engine
    )
    
    if not df_elem.empty:
        with col1:
            andares_lista = sorted(df_elem['andar'].unique(), reverse=True)
            andar_sel = st.selectbox("Andar", andares_lista)
        with col2:
            ambientes = sorted(df_elem[df_elem['andar'] == andar_sel]['ambiente'].unique())
            amb_sel
