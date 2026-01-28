import streamlit as st
import pandas as pd
import datetime
from io import BytesIO

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="TATA-REPORTAPP", layout="wide", page_icon="📊")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@300;400;500;600&display=swap');
    html, body, [class*="css"] { font-family: 'Quicksand', sans-serif; }
    .main-header { font-size: 32px; font-weight: 600; color: #1e3a8a; border-bottom: 2px solid #f0f2f6; padding-bottom: 10px; margin-bottom: 25px; text-align: center;}
    .footer { position: fixed; bottom: 0; left: 0; width: 100%; background: white; text-align: center; padding: 15px; font-size: 11px; color: #888; border-top: 1px solid #eee; z-index: 999; }
    .stMetric { background-color: #f8f9fa; padding: 10px; border-radius: 5px; border: 1px solid #eee; }
    </style>
    """, unsafe_allow_html=True)

# --- MOTORE DI MAPPATURA (Basato sui tuoi dati grezzi) ---
MAPPING_REGOLE = {
    # Vendite
    'andescri': 'Cliente', 
    'ardesart': 'Articolo_Desc', 
    'mmdatdoc': 'Data', 
    'mmqtamov': 'KG_Venduti', 
    'mmprezzo': 'Prezzo_Vendita',
    'arcodfam': 'Categoria',
    # Magazzino
    'PREZZO': 'Costo_Unitario',
    'ARTICOLO DESCRIZIONE': 'Articolo_Desc',
    'ORIGINE': 'Origine',
    'CAT': 'Tipologia'
}

def load_and_map(file, mapping):
    if file is None: return None
    try:
        # Tenta Excel, se fallisce tenta CSV
        try:
            df = pd.read_excel(file)
        except:
            file.seek(0)
            df = pd.read_csv(file, sep=None, engine='python')
        
        # Rinomina colonne basandosi sul mapping tecnico
        df = df.rename(columns=mapping)
        
        # Pulizia numerica
        for col in ['KG_Venduti', 'Prezzo_Vendita', 'Costo_Unitario']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        return df
    except Exception as e:
        st.error(f"Errore nel caricamento di {file.name}: {e}")
        return None

# --- NAVIGAZIONE ---
if 'data_final' not in st.session_state: st.session_state.data_final = None

with st.sidebar:
    st.title("TATA-REPORTAPP")
    menu = st.radio("Scegli Pagina:", ["P1 - DATA INGESTION", "P2 - REPORT SINOTTICO", "P3 - ARCHIVIO", "P4 - ANALYTICS"])

# --- PAGINA 1: CARICAMENTO ---
if menu == "P1 - DATA INGESTION":
    st.markdown('<div class="main-header">TATA-REPORTAPP - Caricamento Dati</div>', unsafe_allow_html=True)
    
    comps = ["TA.TA Srl", "GIARDINO DELL’AGLIO SRL", "ANGELO TATA SRL"]
    files_v = {}
    files_m = {}

    col1, col2, col3 = st.columns(3)
    for i, c in enumerate(comps):
        with [col1, col2, col3][i]:
            st.subheader(c)
            files_v[c] = st.file_uploader(f"VENDITE {c}", type=['xlsx', 'xls', 'csv'], key=f"v{i}")
            files_m[c] = st.file_uploader(f"MAGAZZINO {c}", type=['xlsx', 'xls', 'csv'], key=f"m{i}")

    st.divider()
    st.subheader("Filtri ed Opzioni")
    c1, c2 = st.columns(2)
    with c1:
        d_in = st.date_input("Inizio Periodo", datetime.date(2025, 12, 1))
        d_fi = st.date_input("Fine Periodo", datetime.date(2025, 12, 31))
    with c2:
        aziende_sel = st.multiselect("Aziende da Elaborare", comps, default=comps)
        cumulativo = st.toggle("Elaborazione Cumulativa", value=True)

    if st.button("ELABORA REPORT", use_container_width=True):
        all_v = []
        all_m = []
        for c in aziende_sel:
            df_v = load_and_map(files_v[c], MAPPING_REGOLE)
            if df_v is not None:
                df_v['Azienda'] = c
                all_v.append(df_v)
            
            df_m = load_and_map(files_m[c], MAPPING_REGOLE)
            if df_m is not None:
                all_m.append(df_m)

        if all_v:
            combined_v = pd.concat(all_v, ignore_index=True)
            # Filtro date
            if 'Data' in combined_v.columns:
                combined_v['Data'] = pd.to_datetime(combined_v['Data'], errors='coerce')
                combined_v = combined_v[(combined_v['Data'].dt.date >= d_in) & (combined_v['Data'].dt.date <= d_fi)]
            
            # Calcolo Fatturato
            combined_v['Fatturato'] = combined_v['KG_Venduti'] * combined_v['Prezzo_Vendita']

            # Integrazione Magazzino (Margini)
            if all_m:
                combined_m = pd.concat(all_m, ignore_index=True)
                costs = combined_m.groupby('Articolo_Desc')['Costo_Unitario'].mean().reset_index()
                combined_v = pd.merge(combined_v, costs, on='Articolo_Desc', how='left')
                combined_v['Margine'] = combined_v['Fatturato'] - (combined_v['KG_Venduti'] * combined_v['Costo_Unitario'].fillna(0))
            
            st.session_state.data_final = combined_v
            st.success("Elaborazione completata! Vai alla pagina Report.")
        else:
            st.error("Nessun file di vendita caricato.")

# --- PAGINA 2: REPORT ---
elif menu == "P2 - REPORT SINOTTICO":
    st.markdown('<div class="main-header">TATA-REPORTAPP - Report Mensile</div>', unsafe_allow_html=True)
    if st.session_state.data_final is not None:
        df = st.session_state.data_final
        
        # Metriche
        m1, m2, m3 = st.columns(3)
        m1.metric("Totale KG", f"{df['KG_Venduti'].sum():,.2f}")
        m2.metric("Fatturato Totale", f"{df['Fatturato'].sum():,.2f} €")
        if 'Margine' in df.columns:
            m3.metric("Margine Stimato", f"{df['Margine'].sum():,.2f} €")

        # Tabella Pivot
        st.subheader("Dettaglio per Articolo")
        agg_cols = {'KG_Venduti': 'sum', 'Fatturato': 'sum'}
        if 'Margine' in df.columns: agg_cols['Margine'] = 'sum'
        
        pivot = df.groupby(['Azienda', 'Articolo_Desc']).agg(agg_cols).reset_index()
        st.dataframe(pivot.style.format(precision=2), use_container_width=True)
        
        st.divider()
        colb1, colb2 = st.columns(2)
        with colb1: st.button("💾 SALVA SU SERVER ARUBA")
        with colb2: st.button("🖨️ STAMPA PDF (ORIZZONTALE)")
    else:
        st.warning("Esegui l'elaborazione nella pagina Caricamento.")

# --- PAGINA 3: ARCHIVIO ---
elif menu == "P3 - ARCHIVIO":
    st.markdown('<div class="main-header">Archivio Storico Report</div>', unsafe_allow_html=True)
    st.info("Connessione al database Aruba... (Visualizzazione ultimi 10 salvataggi)")

# --- PAGINA 4: ANALYTICS ---
elif menu == "P4 - ANALYTICS":
    st.markdown('<div class="main-header">Confronti e Grafici</div>', unsafe_allow_html=True)
    if st.session_state.data_final is not None:
        df = st.session_state.data_final
        st.bar_chart(df.groupby('Azienda')['Fatturato'].sum())
    else:
        st.warning("Dati non disponibili.")

# --- FOOTER ---
st.markdown("""
    <div class="footer">
        Documento ad utilizzo esclusivo interno - Divieto di riproduzione o cessione dati se non esplicitamente autorizzati. <br>
        <b>TATA-REPORTAPP</b> | Progettazione e realizzazione: R-ADVISOR – M. Ribezzo.
    </div>
    """, unsafe_allow_html=True)
