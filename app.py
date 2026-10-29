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
                andar TEXT, ambiente TEXT, disciplina TEXT, 
                identificacao TEXT, area_total_m2 NUMERIC)
        '''))
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS tb_regras_metragem (
                disciplina TEXT, etapa TEXT, multiplicador NUMERIC)
        '''))
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS tb_apontamentos_v2 (
                id_apontamento SERIAL PRIMARY KEY,
                id_elemento INTEGER, etapa TEXT, data_registo TEXT)
        '''))
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS tb_efetivo (
                data_registo TEXT, disciplina TEXT, qtd_funcionarios INTEGER,
                PRIMARY KEY (data_registo, disciplina))
        '''))
        
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
            query_regra = text("INSERT INTO tb_regras_metragem (disciplina, etapa, multiplicador) VALUES (:1, :2, :3)")
            for r in regras:
                conn.execute(query_regra, {"1": r[0], "2": r[1], "3": r[2]})
            
        result_elem = conn.execute(text("SELECT COUNT(*) FROM tb_elementos_v2")).scalar()
        if result_elem == 0:
            andares_todos = ['10º Pavimento', '09º Pavimento', '08º Pavimento', '07º Pavimento', '06º Pavimento', '05º Pavimento', '04º Pavimento', '03º Pavimento']
            query_insert = text("INSERT INTO tb_elementos_v2 (andar, ambiente, disciplina, identificacao, area_total_m2) VALUES (:1, :2, :3, :4, :5)")
            
            for andar in andares_todos:
                for wc in ['WC 1', 'WC 2']:
                    for p in ['Parede 01', 'Parede 02', 'Parede 03', 'Parede 04']:
                        conn.execute(query_insert, {"1": andar, "2": wc, "3": "Drywall", "4": p, "5": 2.50 * 3})
                    conn.execute(query_insert, {"1": andar, "2": wc, "3": "Forro Gesso Liso", "4": "Teto", "5": 5.00})
                    conn.execute(query_insert, {"1": andar, "2": wc, "3": "Pintura", "4": "Teto", "5": 5.00})

                paredes_copa = [('Parede 01', 7.30), ('Parede 02', 7.30), ('Parede 04', 7.30), ('Pórtico', 7.30)]
                for p_nome, p_medida in paredes_copa:
                    conn.execute(query_insert, {"1": andar, "2": "Copa", "3": "Drywall", "4": p_nome, "5": p_medida * 3})
                
                conn.execute(query_insert, {"1": andar, "2": "Core", "3": "Pintura", "4": "Parede 01", "5": 21.65 * 3})
                conn.execute(query_insert, {"1": andar, "2": "Core", "3": "Pintura", "4": "Parede 02", "5": 9.80 * 3})

                qtd_booths = 2 if andar == '10º Pavimento' else 3
                for i in range(1, qtd_booths + 1):
                    booth = f'Booth 0{i}'
                    paredes_booth = [('Parede 01', 2.25), ('Parede 02', 2.40), ('Parede 03', 2.25), ('Parede 04', 2.40)]
                    for p_nome, p_medida in paredes_booth:
                        conn.execute(query_insert, {"1": andar, "2": booth, "3": "Drywall", "4": p_nome, "5": p_medida * 3})
                    conn.execute(query_insert, {"1": andar, "2": booth, "3": "Forro Modular", "4": "Teto", "5": 3.50})

                if andar == '04º Pavimento':
                    reuniao_4 = [
                        ('Reunião 01', [('Parede 01', 3.65), ('Parede 02', 3.85), ('Parede 03', 3.65), ('Parede 04', 3.85)]),
                        ('Reunião 02', [('Parede 01', 3.65), ('Parede 02', 3.85), ('Parede 03', 3.65), ('Parede 04', 3.85)]),
                        ('Reunião 03', [('Parede 01', 3.00), ('Parede 03', 3.00), ('Parede 04', 3.75)])
                    ]
                    for r_nome, r_paredes in reuniao_4:
                        for p_nome, p_medida in r_paredes:
                            conn.execute(query_insert, {"1": andar, "2": r_nome, "3": "Drywall", "4": p_nome, "5": p_medida * 3})
                else:
                    for i in range(1, 4):
                        r_nome = f'Reunião 0{i}'
                        paredes_r = [('Parede 01', 4.50), ('Parede 02', 7.35), ('Parede 04', 7.35)]
                        for p_nome, p_medida in paredes_r:
                            conn.execute(query_insert, {"1": andar, "2": r_nome, "3": "Drywall", "4": p_nome, "5": p_medida * 3})
        conn.commit()

init_db()

# ---------------------------------------------------------
# 2. INTERFACE E NAVEGAÇÃO
# ---------------------------------------------------------
st.title("🏗️ Prodigy - Controle de Produção")
aba1, aba2, aba3 = st.tabs(["📋 Lançamento de Produção", "👷 Controle de Efetivo", "📊 Dashboard Gerencial"])

with aba1:
    df_elem = pd.read_sql("SELECT DISTINCT andar, ambiente, disciplina FROM tb_elementos_v2", engine)
    
    if not df_elem.empty:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            andares_lista = sorted(df_elem['andar'].unique(), reverse=True)
            andar_sel = st.selectbox("Andar", andares_lista)
        
        with col2:
            ambientes_lista = sorted(df_elem[df_elem['andar'] == andar_sel]['ambiente'].unique())
            amb_sel = st.selectbox("Ambiente", ambientes_lista) if len(ambientes_lista) > 0 else None
            
        with col3:
            if amb_sel:
                filtro = (df_elem['andar'] == andar_sel) & (df_elem['ambiente'] == amb_sel)
                disciplinas_lista = df_elem[filtro]['disciplina'].unique()
                disc_sel = st.selectbox("Disciplina", disciplinas_lista) if len(disciplinas_lista) > 0 else None
            else:
                disc_sel = None

        if andar_sel and amb_sel and disc_sel:
            st.markdown(f"### {disc_sel} - {amb_sel} ({andar_sel})")
            
            query_elem = f"SELECT * FROM tb_elementos_v2 WHERE andar='{andar_sel}' AND ambiente='{amb_sel}' AND disciplina='{disc_sel}' ORDER BY identificacao"
            elementos_atuais = pd.read_sql(query_elem, engine)
            
            query_etapas = f"SELECT etapa, multiplicador FROM tb_regras_metragem WHERE disciplina='{disc_sel}'"
            etapas = pd.read_sql(query_etapas, engine)

            for _, row in elementos_atuais.iterrows():
                area_base = row['area_total_m2']
                nome = row['identificacao']
                id_elem = row['id_elemento']
                
                with st.expander(f"{nome} (Área Base: {area_base:.2f} m²)"):
                    if not etapas.empty:
                        cols = st.columns(len(etapas))
                        for i, etapa_row in etapas.iterrows():
                            etapa = etapa_row['etapa']
                            mult = float(etapa_row['multiplicador'])
                            metragem_etapa = area_base * mult
                            
                            q_apont = f"SELECT 1 FROM tb_apontamentos_v2 WHERE id_elemento={id_elem} AND etapa='{etapa}'"
                            df_apont = pd.read_sql(q_apont, engine)
                            foi_apontado = not df_apont.empty
                            
                            with cols[i]:
                                st.caption(f"{metragem_etapa:.2f} m²")
                                btn_txt = f"✔️ {etapa}" if foi_apontado else f"➕ {etapa}"
                                if st.button(btn_txt, key=f"{id_elem}_{etapa}"):
                                    if not foi_apontado:
                                        with engine.connect() as conn:
                                            inserir_apont = text("INSERT INTO tb_apontamentos_v2 (id_elemento, etapa, data_registo) VALUES (:1, :2, :3)")
                                            conn.execute(inserir_apont, {"1": id_elem, "2": etapa, "3": str(date.today())})
                                            conn.commit()
                                        st.rerun()

with aba2:
    st.markdown("### Lançamento Diário de Mão de Obra")
    with st.form("form_efetivo"):
        dt_efetivo = st.date_input("Data do Efetivo")
        colA, colB, colC = st.columns(3)
        with colA: qtd_drywall = st.number_input("Oficiais Drywall", min_value=0, step=1)
        with colB: qtd_pintura = st.number_input("Oficiais Pintura", min_value=0, step=1)
        with colC: qtd_forro = st.number_input("Oficiais Forros", min_value=0, step=1)
        
        if st.form_submit_button("Salvar Efetivo"):
            with engine.connect() as conn:
                query_efetivo = text("""
                    INSERT INTO tb_efetivo (data_registo, disciplina, qtd_funcionarios) 
                    VALUES (:1, :2, :3) 
                    ON CONFLICT (data_registo, disciplina) 
                    DO UPDATE SET qtd_funcionarios = EXCLUDED.qtd_funcionarios
                """)
                lista_efetivo = [('Drywall', qtd_drywall), ('Pintura', qtd_pintura), ('Forro Modular', qtd_forro), ('Forro Gesso Liso', qtd_forro)]
                for disc, qtd in lista_efetivo:
                    if qtd > 0:
                        conn.execute(query_efetivo, {"1": str(dt_efetivo), "2": disc, "3": qtd})
                conn.commit()
            st.success("Efetivo gravado com sucesso!")

with aba3:
    query_dash = """
        WITH Escopo AS (
            SELECT e.andar, e.disciplina, sum(e.area_total_m2 * p.multiplicador) as area_total_escopo
            FROM tb_elementos_v2 e
            JOIN tb_regras_metragem p ON e.disciplina = p.disciplina
            GROUP BY e.andar, e.disciplina
        ),
        Executado AS (
            SELECT e.andar, e.disciplina, sum(e.area_total_m2 * p.multiplicador) as area_executada
            FROM tb_elementos_v2 e
            JOIN tb_apontamentos_v2 a ON e.id_elemento = a.id_elemento
            JOIN tb_regras_metragem p ON a.etapa = p.etapa AND e.disciplina = p.disciplina
            GROUP BY e.andar, e.disciplina
        )
        SELECT es.andar, es.disciplina, es.area_total_escopo, COALESCE(ex.area_executada, 0) as area_executada
        FROM Escopo es
        LEFT JOIN Executado ex ON es.andar = ex.andar AND es.disciplina = ex.disciplina
    """
    df_dash = pd.read_sql(query_dash, engine)
    
    if not df_dash.empty:
        df_dash['% Concluído'] = df_dash.apply(lambda row: (row['area_executada'] / row['area_total_escopo'] * 100) if row['area_total_escopo'] > 0 else 0, axis=1)
        
        st.markdown("### Avanço por Disciplina e Andar")
        fig = px.bar(df_dash, x="andar", y="% Concluído", color="disciplina", barmode="group", text_auto='.1f', title="Status de Conclusão (%)")
        st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("### Indicador de Produtividade Diária (Hoje)")
        hoje = str(date.today())
        
        query_prod = f"SELECT e.disciplina, sum(e.area_total_m2 * p.multiplicador) as prod_m2 FROM tb_apontamentos_v2 a JOIN tb_elementos_v2 e ON a.id_elemento = e.id_elemento JOIN tb_regras_metragem p ON a.etapa = p.etapa AND e.disciplina = p.disciplina WHERE a.data_registo = '{hoje}' GROUP BY e.disciplina"
        df_prod = pd.read_sql(query_prod, engine)
        
        q_efetivo = f"SELECT disciplina, qtd_funcionarios FROM tb_efetivo WHERE data_registo = '{hoje}'"
        df_efetivo = pd.read_sql(q_efetivo, engine)
        
        m_cols = st.columns(3)
        for idx, row in df_prod.iterrows():
            disc = row['disciplina']
            area_feita = row['prod_m2']
            efetivo = df_efetivo[df_efetivo['disciplina'] == disc]['qtd_funcionarios'].sum() if not df_efetivo.empty else 0
            rendimento = (area_feita / efetivo) if efetivo > 0 else 0
            m_cols[idx % 3].metric(label=f"Rendimento {disc}", value=f"{rendimento:.1f} m²/homem", delta=f"{area_feita:.1f} m² totais hoje")
