import streamlit as st
import pandas as pd
import datetime
from io import BytesIO

# --- CONFIGURAZIONE PAGINA E DESIGN ---
st.set_page_config(page_title="TATA-REPORTAPP", layout="wide", page_icon="📊")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@300;400;500;600&display=swap');
    html, body, [class*="css"] { font-family: 'Quicksand', sans-serif; }
    .main-header { font-size: 30px; font-weight: 600; color: #1a1a1a; border-bottom: 1px solid #ddd; padding-bottom: 10px; margin-bottom: 20px; }
    .stButton>button { border-radius: 2px; background-color: #2c3e50; color: white; border: none; }
    .footer { position: fixed; bottom: 0; left: 0; width: 100%; background: white; text-align: center; padding: 10px; font-size: 11px; color: #999; border-top: 1px solid #eee; z-index: 999; }
    </style>
    """, unsafe_allow_html=True)

# --- MAPPATURA TECNICA (Dati Grezzi -> Significato) ---
# Qui ho inserito i codici estratti dal tuo esempio (es. andescri = CLIENTE)
MAPPING_VENDITE = {
    'andescri': 'Cliente',
    'mmcodcon': 'Cod_Cliente',
    'ddnomdes': 'Piattaforma',
    'ardesart': 'Articolo_Desc',
    'mmcodart': 'Cod_Articolo',
    'mmdatdoc': 'Data',
    'mmcolli': 'Colli',
    'mmqtamov': 'Qta_Movimento',
    'mmprezzo': 'Prezzo_Unitario',
    'arcodfam': 'Categoria',
    'qtano': 'KG_Venduti',
    'mvnumlot': 'Lotto'
}

MAPPING_MAGAZZINO = {
    'ORIGINE': 'Origine',
    'CAT': 'Tipologia',
    'ARTICOLO DESCRIZIONE': 'Articolo_Desc',
    'PREZZO': 'Costo_Unitario',
    'KG ACQUISTATI': 'KG_Acquistati',
    'COSTO TOTALE ACQUISTO': 'Costo_Totale'
}

# --- FUNZIONE DI PULIZIA DATI ---
def clean_raw_data(df, mapping):
    # Rinomina le colonne solo se trova i codici tecnici del tuo gestionale
    df = df.rename(columns=mapping)
    # Assicurati che le colonne numeriche siano tali
    numeric_cols = ['KG_Venduti', 'Qta_Movimento', 'Prezzo_Unitario', 'Colli', 'Costo_Unitario', 'KG_Acquistati']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # Conversione Data
    if 'Data' in df.columns:
        df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
    
    return df

# --- LOGICA DI ELABORAZIONE ---
def process_data(dict_files, companies, start_date, end_date):
    v_list = []
    m_list = []
    
    for comp in companies:
        if dict_files[comp]['v'] is not None:
            df_v = pd.read_excel(dict_files[comp]['v'])
            df_v = clean_raw_data(df_v, MAPPING_VENDITE)
            df_v['Azienda'] = comp
            v_list.append(df_v)
            
        if dict_files[comp]['m'] is not None:
            df_m = pd.read_excel(dict_files[comp]['m'])
            df_m = clean_raw_data(df_m, MAPPING_MAGAZZINO)
            df_m['Azienda'] = comp
            m_list.append(df_m)
            
    if not v_list: return None
    
    full_v = pd.concat(v_list, ignore_index=True)
    
    # Filtro periodo
    full_v = full_v[(full_v['Data'].dt.date >= start_date) & (full_v['Data'].dt.date <= end_date)]
    
    # Calcolo Margine (Join con Magazzino)
    if m_list:
        full_m = pd.concat(m_list, ignore_index=True)
        # Costo medio per articolo
        costs = full_m.groupby('Articolo_Desc')['Costo_Unitario'].mean().reset_index()
        full_v = pd.merge(full_v, costs, on='Articolo_Desc', how='left')
        full_v['Fatturato'] = full_v['KG_Venduti'] * full_v['Prezzo_Unitario']
        full_v['Costo_Venduto'] = full_v['KG_Venduti'] * full_v['Costo_Unitario'].fillna(0)
        full_v['Margine'] = full_v['Fatturato'] - full_v['Costo_Venduto']
    
    return full_v

# --- NAVBAR ---
page = st.sidebar.radio("NAVIGAZIONE", ["DATA INGESTION", "REPORT SINOTTICO", "ARCHIVIO SERVER", "ANALYTICS"])

# --- PAGINA 1: UPLOAD ---
if page == "DATA INGESTION":
    st.markdown('<div class="main-header">TATA-REPORTAPP - Caricamento Dati</div>', unsafe_allow_html=True)
    
    comps = ["TA.TA Srl", "GIARDINO DELL’AGLIO SRL", "ANGELO TATA SRL"]
    files = {}
    
    col1, col2, col3 = st.columns(3)
    for i, c in enumerate(comps):
        with [col1, col2, col3][i]:
            st.subheader(c)
            v = st.file_uploader(f"File Vendite (.xlsx)", key=f"v{i}")
            m = st.file_uploader(f"File Magazzino (.xlsx)", key=f"m{i}")
            files[c] = {'v': v, 'm': m}
            
    st.divider()
    st.subheader("Parametri di Controllo")
    c1, c2 = st.columns(2)
    with c1:
        date_mode = st.toggle("Usa periodo definito (INIZIO/FINE)", value=False)
        d_in = st.date_input("Inizio", datetime.date(2025, 12, 1))
        d_fi = st.date_input("Fine", datetime.date(2025, 12, 31))
    with c2:
        cumulativo = st.toggle("Report Cumulativo (Tutte)", value=True)
        aziende_sel = st.multiselect("Seleziona Aziende", comps, default=comps)

    if st.button("ELABORA E GENERA REPORT", use_container_width=True):
        res = process_data(files, aziende_sel, d_in, d_fi)
        if res is not None:
            st.session_state['report_data'] = res
            st.success("Elaborazione completata. Vai alla pagina REPORT.")

# --- PAGINA 2: REPORT ---
elif page == "REPORT SINOTTICO":
    st.markdown('<div class="main-header">Quadro Sinottico Mensile</div>', unsafe_allow_html=True)
    if 'report_data' in st.session_state:
        df = st.session_state['report_data']
        
        # Replica dello screenshot richiesto
        st.write("### Riepilogo per Origine e Tipologia")
        sinottico = df.groupby(['Azienda', 'Articolo_Desc']).agg({
            'KG_Venduti': 'sum',
            'Fatturato': 'sum',
            'Margine': 'sum'
        }).reset_index()
        
        st.dataframe(sinottico.style.format(subset=['Fatturato', 'Margine'], formatter="{:.2f} €"), use_container_width=True)
        
        st.divider()
        col_btns = st.columns(3)
        with col_btns[0]: st.button("💾 SALVA SU SERVER ARUBA")
        with col_btns[1]: st.button("🖨️ STAMPA REPORT (LANDSCAPE)")
    else:
        st.warning("Carica i dati grezzi nella prima pagina.")

# --- PAGINA 3: ARCHIVIO ---
elif page == "ARCHIVIO SERVER":
    st.markdown('<div class="main-header">Archivio Storico Elaborazioni</div>', unsafe_allow_html=True)
    st.info("Qui verranno elencati i report salvati sul server Aruba.")

# --- PAGINA 4: ANALYTICS ---
elif page == "ANALYTICS":
    st.markdown('<div class="main-header">Graphic Intelligence</div>', unsafe_allow_html=True)
    if 'report_data' in st.session_state:
        df = st.session_state['report_data']
        st.bar_chart(df, x="Azienda", y="Fatturato")
    else:
        st.warning("Carica dati per visualizzare i grafici.")

# --- FOOTER ---
st.markdown("""
    <div class="footer">
        Documento ad utilizzo esclusivo interno - Divieto di riproduzione o cessione dati se non autorizzati. 
        <br><b>TATA-REPORTAPP</b> | Tribute to R-ADVISOR – M. Ribezzo.
    </div>
    """, unsafe_allow_html=True)
