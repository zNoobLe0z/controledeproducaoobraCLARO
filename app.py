import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date
from sqlalchemy import create_engine, text

st.set_page_config(page_title="Prodigy - Gestão de Obras", layout="wide")

# ---------------------------------------------------------
# 0. TELA DE LOGIN SIMPLES
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
# 1. CONEXÃO COM POSTGRESQL (Supabase)
# ---------------------------------------------------------
@st.cache_resource
def init_connection():
    # Conecta usando a URL configurada nos Secrets do Streamlit Cloud
    return create_engine(st.secrets["DB_URL"])

engine = init_connection()

def init_db():
    with engine.connect() as conn:
        # Criar Tabelas no padrão PostgreSQL
        conn.execute(text('''CREATE TABLE IF NOT EXISTS tb_elementos (
                        id_elemento SERIAL PRIMARY KEY,
                        andar TEXT, ambiente TEXT, disciplina TEXT, 
                        identificacao TEXT, area_total_m2 NUMERIC)'''))
        
        conn.execute(text('''CREATE TABLE IF NOT EXISTS tb_pesos (
                        disciplina TEXT, etapa TEXT, peso NUMERIC)'''))
                        
        conn.execute(text('''CREATE TABLE IF NOT EXISTS tb_apontamentos (
                        id_apontamento SERIAL PRIMARY KEY,
                        id_elemento INTEGER, etapa TEXT, data_registo TEXT)'''))
                        
        conn.execute(text('''CREATE TABLE IF NOT EXISTS tb_efetivo (
                        data_registo TEXT, disciplina TEXT, qtd_funcionarios INTEGER,
                        PRIMARY KEY (data_registo, disciplina))'''))
        
        # Popular Pesos (Se vazio)
        result_pesos = conn.execute(text("SELECT COUNT(*) FROM tb_pesos")).scalar()
        if result_pesos == 0:
            pesos = [
                ('Drywall', '1ª Face', 0.25), ('Drywall', 'Reforços', 0.25), 
                ('Drywall', '2ª Face', 0.25), ('Drywall', 'Acabamentos', 0.25),
                ('Pintura', 'Emassamento', 0.20), ('Pintura', 'Lixa', 0.20), 
                ('Pintura', '1ª Demão', 0.20), ('Pintura', '2ª Demão', 0.20), ('Pintura', '3ª Demão', 0.20),
                ('Forro Modular', 'Estruturação', 0.50), ('Forro Modular', 'Plaqueamento', 0.50)
            ]
            for p in pesos:
                conn.execute(text("INSERT INTO tb_pesos (disciplina, etapa, peso) VALUES (:1, :2, :3)"), 
                             {"1": p[0], "2": p[1], "3": p[2]})
            
        # Popular Levantamento Físico (Andares Padrões)
        result_elem = conn.execute(text("SELECT COUNT(*) FROM tb_elementos")).scalar()
        if result_elem == 0:
            andares_padrao = ['10º Pavimento', '09º Pavimento', '08º Pavimento', '06º Pavimento', '05º Pavimento', '03º Pavimento']
            for andar in andares_padrao:
                # Copa
                paredes_copa = [('Parede 01', 7.30), ('Parede 02', 7.30), ('Parede 04', 7.30), ('Pórtico', 7.30)]
                for p_nome, p_medida in paredes_copa:
                    conn.execute(text("INSERT INTO tb_elementos (andar, ambiente, disciplina, identificacao, area_total_m2) VALUES (:1, 'Copa', 'Drywall', :2, :3)"),
                                 {"1": andar, "2": p_nome, "3": p_medida * 3})
                
                # Booths
                for booth in ['Booth 01', 'Booth 02']:
                    paredes_booth = [('Parede 01', 2.25), ('Parede 02', 2.40), ('Parede 03', 2.25), ('Parede 04', 2.40)]
                    for p_nome, p_medida in paredes_booth:
                        conn.execute(text("INSERT INTO tb_elementos (andar, ambiente, disciplina, identificacao, area_total_m2) VALUES (:1, :2, 'Drywall', :3, :4)"),
                                     {"1": andar, "2": booth, "3": p_nome, "4": p_medida * 3})
                    # Forro Booth
                    conn.execute(text("INSERT INTO tb_elementos (andar, ambiente, disciplina, identificacao, area_total_m2) VALUES (:1, :2, 'Forro Modular', 'Teto (Modular)', 3.50)"),
                                 {"1": andar, "2": booth})
                
                # Core Pintura
                conn.execute(text("INSERT INTO tb_elementos (andar, ambiente, disciplina, identificacao, area_total_m2) VALUES (:1, 'Core', 'Pintura', 'Parede 01', :2)"),
                             {"1": andar, "2": 21.65 * 3})
                conn.execute(text("INSERT INTO tb_elementos (andar, ambiente, disciplina, identificacao, area_total_m2) VALUES (:1, 'Core', 'Pintura', 'Parede 02', :2)"),
                             {"1": andar, "2": 9.80 * 3})
        conn.commit()

init_db()

# ---------------------------------------------------------
# 2. INTERFACE E NAVEGAÇÃO
# ---------------------------------------------------------
st.title("🏗️ Prodigy - Controle de Produção")
aba1, aba2, aba3 = st.tabs(["📋 Lançamento de Produção", "👷 Controle de Efetivo", "📊 Dashboard Gerencial"])

# --- ABA 1: LANÇAMENTO DE PRODUÇÃO ---
with aba1:
    col1, col2, col3 = st.columns(3)
    df_elem = pd.read_sql("SELECT DISTINCT andar, ambiente, disciplina FROM tb_elementos", engine)
    
    if not df_elem.empty:
        with col1:
            andar_sel = st.selectbox("Andar", df_elem['andar'].unique())
        with col2:
            ambientes = df_elem[df_elem['andar'] == andar_sel]['ambiente'].unique()
            amb_sel = st.selectbox("Ambiente", ambientes)
        with col3:
            disciplinas = df_elem[(df_elem['andar'] == andar_sel) & (df_elem['ambiente'] == amb_sel)]['disciplina'].unique()
            disc_sel = st.selectbox("Disciplina", disciplinas)

        st.markdown(f"### {disc_sel} - {amb_sel} ({andar_sel})")
        
        query = f"SELECT * FROM tb_elementos WHERE andar='{andar_sel}' AND ambiente='{amb_sel}' AND disciplina='{disc_sel}'"
        elementos_atuais = pd.read_sql(query, engine)
        etapas = pd.read_sql(f"SELECT etapa FROM tb_pesos WHERE disciplina='{disc_sel}'", engine)['etapa'].tolist()

        for _, row in elementos_atuais.iterrows():
            with st.expander(f"{row['identificacao']} (Área Total: {row['area_total_m2']:.2f} m²)"):
                cols = st.columns(len(etapas))
                for i, etapa in enumerate(etapas):
                    df_apont = pd.read_sql(f"SELECT 1 FROM tb_apontamentos WHERE id_elemento={row['id_elemento']} AND etapa='{etapa}'", engine)
                    foi_apontado = not df_apont.empty
                    
                    with cols[i]:
                        if st.button(f"✔️ {etapa}" if foi_apontado else f"➕ {etapa}", key=f"{row['id_elemento']}_{etapa}"):
                            if not foi_apontado:
                                with engine.connect() as conn:
                                    conn.execute(text("INSERT INTO tb_apontamentos (id_elemento, etapa, data_registo) VALUES (:1, :2, :3)"),
                                                 {"1": row['id_elemento'], "2": etapa, "3": str(date.today())})
                                    conn.commit()
                                st.rerun()

# --- ABA 2: CONTROLE DE EFETIVO ---
with aba2:
    st.markdown("### Lançamento Diário de Mão de Obra")
    with st.form("form_efetivo"):
        dt_efetivo = st.date_input("Data do Efetivo")
        colA, colB, colC = st.columns(3)
        with colA: qtd_drywall = st.number_input("Oficiais Drywall", min_value=0, step=1)
        with colB: qtd_pintura = st.number_input("Oficiais Pintura", min_value=0, step=1)
        with colC: qtd_forro = st.number_input("Oficiais Forro", min_value=0, step=1)
        
        if st.form_submit_button("Salvar Efetivo"):
            with engine.connect() as conn:
                for disc, qtd in [('Drywall', qtd_drywall), ('Pintura', qtd_pintura), ('Forro Modular', qtd_forro)]:
                    if qtd > 0:
                        # Sintaxe PostgreSQL para "Insert or Update" (Upsert)
                        conn.execute(text("""
                            INSERT INTO tb_efetivo (data_registo, disciplina, qtd_funcionarios) 
                            VALUES (:1, :2, :3) 
                            ON CONFLICT (data_registo, disciplina) 
                            DO UPDATE SET qtd_funcionarios = EXCLUDED.qtd_funcionarios
                        """), {"1": str(dt_efetivo), "2": disc, "3": qtd})
                conn.commit()
            st.success("Efetivo gravado com sucesso!")

# --- ABA 3: DASHBOARD ---
with aba3:
    query_avanco = """
        SELECT e.andar, e.disciplina, sum(e.area_total_m2) as area_total,
               sum(e.area_total_m2 * COALESCE(p.peso, 0)) as area_executada
        FROM tb_elementos e
        LEFT JOIN tb_apontamentos a ON e.id_elemento = a.id_elemento
        LEFT JOIN tb_pesos p ON a.etapa = p.etapa AND e.disciplina = p.disciplina
        GROUP BY e.andar, e.disciplina
    """
    df_dash = pd.read_sql(query_avanco, engine)
    
    if not df_dash.empty and df_dash['area_total'].sum() > 0:
        df_dash['% Concluído'] = (df_dash['area_executada'] / df_dash['area_total']) * 100
        
        st.markdown("### Avanço por Disciplina e Andar")
        fig = px.bar(df_dash, x="andar", y="% Concluído", color="disciplina", barmode="group",
                     text_auto='.1f', title="Status de Conclusão (%)")
        st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("### Indicador de Produtividade (Hoje)")
        hoje = str(date.today())
        
        query_prod = f"""
            SELECT e.disciplina, sum(e.area_total_m2 * p.peso) as prod_hoje
            FROM tb_apontamentos a
            JOIN tb_elementos e ON a.id_elemento = e.id_elemento
            JOIN tb_pesos p ON a.etapa = p.etapa AND e.disciplina = p.disciplina
            WHERE a.data_registo = '{hoje}'
            GROUP BY e.disciplina
        """
        df_prod = pd.read_sql(query_prod, engine)
        df_efetivo = pd.read_sql(f"SELECT disciplina, qtd_funcionarios FROM tb_efetivo WHERE data_registo = '{hoje}'", engine)
        
        m_cols = st.columns(3)
        for idx, row in df_prod.iterrows():
            disc = row['disciplina']
            area_feita = row['prod_hoje']
            efetivo = df_efetivo[df_efetivo['disciplina'] == disc]['qtd_funcionarios'].sum() if not df_efetivo.empty else 0
            rendimento = (area_feita / efetivo) if efetivo > 0 else 0
            
            m_cols[idx % 3].metric(label=f"Rendimento {disc}", value=f"{rendimento:.1f} m²/homem", 
                                   delta=f"{area_feita:.1f} m² totais hoje")
    else:
        st.info("Faça os primeiros lançamentos para gerar o Dashboard.")
