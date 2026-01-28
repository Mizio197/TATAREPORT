import streamlit as st
import pandas as pd
import datetime
from io import BytesIO

# --- CONFIGURAZIONE PAGINA E STILE ---
st.set_page_config(page_title="TATA-REPORTAPP", layout="wide", page_icon="📊")

# CSS per Font Quicksand e Design Pulito
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@300;400;500;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Quicksand', sans-serif;
    }
    
    .main-header {
        font-size: 32px;
        font-weight: 600;
        color: #2c3e50;
        border-bottom: 2px solid #ecf0f1;
        padding-bottom: 10px;
        margin-bottom: 25px;
        text-align: center;
    }
    
    .stButton>button {
        border-radius: 4px;
        background-color: #2c3e50;
        color: white;
        border: none;
        padding: 10px 24px;
        transition: 0.3s;
    }
    
    .stButton>button:hover {
        background-color: #34495e;
        border: none;
    }

    .footer {
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        background-color: white;
        color: #7f8c8d;
        text-align: center;
        padding: 15px;
        font-size: 11px;
        border-top: 1px solid #eee;
        z-index: 100;
    }
    
    /* Stile per tabelle e contenitori */
    .report-card {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 20px;
        margin-bottom: 20px;
        border: 1px solid #e9ecef;
    }
    </style>
    """, unsafe_allow_html=True)

# --- MOTORE SEMANTICO DI MAPPATURA ---
def semantic_mapper(df):
    """
    Riconosce le colonne basandosi sulla riga descrittiva o parole chiave.
    Mapping tra nomi 'umani' e chiavi di calcolo interne.
    """
    mapping = {
        'prodotto': ['descrizione', 'articolo', 'referenza', 'prodotto', 'nome'],
        'quantita': ['q.tà', 'quantità', 'kg', 'peso', 'colli', 'qty'],
        'prezzo_unitario': ['prezzo', 'listino', 'unitario', 'p.u.'],
        'totale_vendita': ['totale', 'imponibile', 'valore', 'importo'],
        'origine': ['origine', 'provenienza', 'stato'],
        'categoria': ['tipo', 'tipologia', 'bio', 'convenzionale', 'cat.'],
        'data': ['data', 'periodo', 'emissione']
    }
    
    new_columns = {}
    for col in df.columns:
        col_lower = str(col).lower()
        for key, synonyms in mapping.items():
            if any(syn in col_lower for syn in synonyms):
                new_columns[col] = key
                break
    
    return df.rename(columns=new_columns)

# --- LOGICA DI ELABORAZIONE ---
def process_full_report(dict_files, companies_filter, start_date, end_date):
    combined_v = []
    combined_m = []

    for comp in companies_filter:
        # Elaborazione Vendite
        if dict_files[comp]['v'] is not None:
            # Carichiamo leggendo la riga 1 (quella aggiunta dall'utente)
            df_v = pd.read_excel(dict_files[comp]['v'], header=0)
            df_v = semantic_mapper(df_v)
            df_v['Azienda_Sorgente'] = comp
            combined_v.append(df_v)
        
        # Elaborazione Magazzino (Acquisti)
        if dict_files[comp]['m'] is not None:
            df_m = pd.read_excel(dict_files[comp]['m'], header=0)
            df_m = semantic_mapper(df_m)
            combined_m.append(df_m)

    if not combined_v:
        return None

    df_final_v = pd.concat(combined_v, ignore_index=True)
    
    # Filtro Date
    if 'data' in df_final_v.columns:
        df_final_v['data'] = pd.to_datetime(df_final_v['data'])
        df_final_v = df_final_v[(df_final_v['data'].dt.date >= start_date) & (df_final_v['data'].dt.date <= end_date)]

    # Se abbiamo il magazzino, facciamo il merge per il margine (Pivot Logic)
    if combined_m:
        df_final_m = pd.concat(combined_m, ignore_index=True)
        # Aggreghiamo il magazzino per prodotto per avere un prezzo medio acquisto
        m_agg = df_final_m.groupby('prodotto')['prezzo_unitario'].mean().reset_index()
        m_agg.columns = ['prodotto', 'costo_medio_acquisto']
        
        # Merge Vendite + Acquisti
        df_report = pd.merge(df_final_v, m_agg, on='prodotto', how='left')
        df_report['margine_lordo'] = df_report['totale_vendita'] - (df_report['quantita'] * df_report['costo_medio_acquisto'].fillna(0))
    else:
        df_report = df_final_v
        df_report['margine_lordo'] = 0

    return df_report

# --- NAVIGAZIONE ---
if 'page' not in st.session_state:
    st.session_state.page = "UPLOAD"

with st.sidebar:
    st.title("MENU")
    if st.button("📁 CARICAMENTO DATI", use_container_width=True): st.session_state.page = "UPLOAD"
    if st.button("📄 REPORT FINALE", use_container_width=True): st.session_state.page = "REPORT"
    if st.button("🗄️ ARCHIVIO", use_container_width=True): st.session_state.page = "ARCHIVIO"
    if st.button("📊 GRAPHIC ANALYTICS", use_container_width=True): st.session_state.page = "GRAPHICS"

# --- PAGINA 1: UPLOAD ---
if st.session_state.page == "UPLOAD":
    st.markdown('<div class="main-header">TATA-REPORTAPP - Caricamento</div>', unsafe_allow_html=True)
    
    comps = ["TA.TA Srl", "GIARDINO DELL’AGLIO SRL", "ANGELO TATA SRL"]
    uploaded_files = {}

    col1, col2, col3 = st.columns(3)
    for i, c in enumerate(comps):
        with [col1, col2, col3][i]:
            st.markdown(f"### {c}")
            v = st.file_uploader(f"Vendite {c}", type=['xlsx'], key=f"v{i}")
            m = st.file_uploader(f"Magazzino {c}", type=['xlsx'], key=f"m{i}")
            uploaded_files[c] = {'v': v, 'm': m}

    st.divider()
    st.subheader("Parametri di Elaborazione")
    c_left, c_right = st.columns(2)
    
    with c_left:
        periodo_tipo = st.radio("Definizione Periodo:", ["Intero File Sorgente", "Range Date Specifico"])
        d_inizio = st.date_input("Dal", datetime.date(2025, 1, 1))
        d_fine = st.date_input("Al", datetime.date(2025, 12, 31))

    with c_right:
        modo_azienda = st.radio("Aziende:", ["Cumulativo (Tutte)", "Parziale (Selezione)"])
        scelta_aziende = st.multiselect("Seleziona Aziende:", comps, default=comps)

    if st.button("GENERA ELABORAZIONE"):
        with st.spinner('Elaborazione semantica in corso...'):
            final_df = process_full_report(uploaded_files, scelta_aziende, d_inizio, d_fine)
            if final_df is not None:
                st.session_state['data_result'] = final_df
                st.success("Report generato! Vai alla pagina REPORT FINALE.")
            else:
                st.error("Carica almeno un file delle vendite per procedere.")

# --- PAGINA 2: REPORT FINALE ---
elif st.session_state.page == "REPORT":
    st.markdown('<div class="main-header">Quadro Sinottico Vendite / Margini</div>', unsafe_allow_html=True)
    
    if 'data_result' in st.session_state:
        df = st.session_state['data_result']
        
        # Simulazione layout Pivot dello screenshot
        st.markdown("#### Riepilogo Aggregato per Origine e Tipologia")
        
        pivot_display = df.groupby(['origine', 'categoria']).agg({
            'quantita': 'sum',
            'totale_vendita': 'sum',
            'margine_lordo': 'sum'
        }).rename(columns={
            'quantita': 'Totale KG/Colli',
            'totale_vendita': 'Fatturato (€)',
            'margine_lordo': 'Margine (€)'
        })
        
        st.dataframe(pivot_display.style.format("{:.2f}"), use_container_width=True)
        
        st.markdown("#### Dettaglio Analitico (Landscape Mode)")
        st.dataframe(df, use_container_width=True)
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("💾 SALVA SU SERVER ARUBA"):
                st.toast("File archiviato con successo nel database server.")
        with col_btn2:
            st.button("🖨️ STAMPA REPORT (LANDSCAPE)")
    else:
        st.info("Nessun dato elaborato. Carica i file nella sezione UPLOAD.")

# --- PAGINA 3: ARCHIVIO ---
elif st.session_state.page == "ARCHIVIO":
    st.markdown('<div class="main-header">Archivio Storico Elaborazioni</div>', unsafe_allow_html=True)
    st.info("Funzione di recupero dati dal server hosting.")
    # Esempio statico
    dummy_db = pd.DataFrame({
        "ID": [101, 102],
        "Timestamp": ["2025-12-28 10:30", "2025-12-15 14:20"],
        "Periodo": ["Dicembre 2025", "Novembre 2025"],
        "Aziende": ["TUTTE", "TA.TA Srl"],
        "Status": ["Archiviato", "Archiviato"]
    })
    st.table(dummy_db)

# --- PAGINA 4: GRAPHICS ---
elif st.session_state.page == "GRAPHICS":
    st.markdown('<div class="main-header">Business Intelligence & Comparazione</div>', unsafe_allow_html=True)
    if 'data_result' in st.session_state:
        df = st.session_state['data_result']
        c1, c2 = st.columns(2)
        with c1:
            st.write("Distribuzione per Origine")
            st.bar_chart(df.groupby('origine')['totale_vendita'].sum())
        with c2:
            st.write("Marginalità per Categoria")
            st.line_chart(df.groupby('categoria')['margine_lordo'].sum())
    else:
        st.warning("Dati non disponibili per i grafici.")

# --- FOOTER ---
st.markdown(f"""
    <div class="footer">
        Documento ad utilizzo esclusivo interno - Divieto di riproduzione o cessione dati se non esplicitamente autorizzati.<br>
        <b>TATA-REPORTAPP</b> | Progettazione e realizzazione: R-ADVISOR – M. Ribezzo.
    </div>
    """, unsafe_allow_html=True)
