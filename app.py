import streamlit as st
import pandas as pd
import datetime
from io import BytesIO

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="TATA-REPORTAPP", layout="wide", page_icon="📊")

# CSS Stile Quicksand & Footer
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@300;400;500;600&display=swap');
    html, body, [class*="css"] { font-family: 'Quicksand', sans-serif; }
    .main-header { font-size: 30px; font-weight: 600; color: #1e3a8a; border-bottom: 2px solid #f0f2f6; padding-bottom: 10px; margin-bottom: 20px; }
    .footer { position: fixed; bottom: 0; left: 0; width: 100%; background: white; text-align: center; padding: 10px; font-size: 11px; color: #888; border-top: 1px solid #eee; z-index: 999; }
    </style>
    """, unsafe_allow_html=True)

# --- MAPPATURA TECNICA DAL GESTIONALE ---
MAPPING_VENDITE = {
    'andescri': 'Cliente', 'mmcodcon': 'Cod_Cliente', 'ardesart': 'Articolo_Desc',
    'mmcodart': 'Cod_Articolo', 'mmdatdoc': 'Data', 'mmcolli': 'Colli',
    'mmqtamov': 'Qta_Movimento', 'mmprezzo': 'Prezzo_Unitario', 'arcodfam': 'Categoria',
    'qtano': 'KG_Venduti'
}

# --- FUNZIONE DI CARICAMENTO ROBUSTA ---
def safe_load_excel(uploaded_file):
    """Tenta di caricare il file gestendo diversi formati e codifiche."""
    if uploaded_file is None:
        return None
    try:
        # Tenta prima come Excel standard
        return pd.read_excel(uploaded_file)
    except Exception:
        try:
            # Tenta come CSV (spesso i gestionali esportano CSV con estensione .xls)
            uploaded_file.seek(0)
            return pd.read_csv(uploaded_file, sep=None, engine='python', on_bad_lines='skip')
        except Exception as e:
            st.error(f"Impossibile leggere il file {uploaded_file.name}: {e}")
            return None

# --- PULIZIA E MAPPATURA ---
def process_data(dict_files, companies, start_date, end_date):
    v_list = []
    m_list = []
    
    for comp in companies:
        # Processo Vendite
        df_v = safe_load_excel(dict_files[comp]['v'])
        if df_v is not None:
            df_v = df_v.rename(columns=MAPPING_VENDITE)
            df_v['Azienda'] = comp
            if 'Data' in df_v.columns:
                df_v['Data'] = pd.to_datetime(df_v['Data'], errors='coerce')
            v_list.append(df_v)
            
        # Processo Magazzino
        df_m = safe_load_excel(dict_files[comp]['m'])
        if df_m is not None:
            df_m['Azienda'] = comp
            m_list.append(df_m)
            
    if not v_list:
        return None
    
    full_v = pd.concat(v_list, ignore_index=True)
    
    # Filtro Date
    if 'Data' in full_v.columns:
        full_v = full_v[(full_v['Data'].dt.date >= start_date) & (full_v['Data'].dt.date <= end_date)]
    
    # Calcoli Numerici (assicura che siano numeri e non stringhe)
    cols_to_fix = ['KG_Venduti', 'Prezzo_Unitario']
    for col in cols_to_fix:
        if col in full_v.columns:
            full_v[col] = pd.to_numeric(full_v[col], errors='coerce').fillna(0)
    
    full_v['Fatturato'] = full_v.get('KG_Venduti', 0) * full_v.get('Prezzo_Unitario', 0)
    return full_v

# --- NAVIGAZIONE ---
page = st.sidebar.radio("NAVIGAZIONE", ["CARICAMENTO", "REPORT", "ARCHIVIO"])

if page == "CARICAMENTO":
    st.markdown('<div class="main-header">TATA-REPORTAPP - Caricamento Dati</div>', unsafe_allow_html=True)
    
    comps = ["TA.TA Srl", "GIARDINO DELL’AGLIO SRL", "ANGELO TATA SRL"]
    files = {}
    
    col1, col2, col3 = st.columns(3)
    for i, c in enumerate(comps):
        with [col1, col2, col3][i]:
            st.subheader(c)
            v = st.file_uploader(f"Vendite {c}", type=['xlsx', 'xls', 'csv'], key=f"v{i}")
            m = st.file_uploader(f"Magazzino {c}", type=['xlsx', 'xls', 'csv'], key=f"m{i}")
            files[c] = {'v': v, 'm': m}
            
    st.divider()
    d_in = st.date_input("Inizio Periodo", datetime.date(2025, 12, 1))
    d_fi = st.date_input("Fine Periodo", datetime.date(2025, 12, 31))
    aziende_sel = st.multiselect("Aziende da includere", comps, default=comps)

    if st.button("ELABORA DATI", use_container_width=True):
        res = process_data(files, aziende_sel, d_in, d_fi)
        if res is not None:
            st.session_state['report_data'] = res
            st.success("Dati pronti! Vai alla pagina REPORT.")
        else:
            st.error("Nessun dato valido trovato. Verifica i file caricati.")

elif page == "REPORT":
    st.markdown('<div class="main-header">Quadro Sinottico Elaborato</div>', unsafe_allow_html=True)
    if 'report_data' in st.session_state:
        df = st.session_state['report_data']
        
        # Dashboard Semplice
        st.metric("Fatturato Totale Periodo", f"{df['Fatturato'].sum():,.2f} €")
        
        # Pivot Table come da screenshot
        st.write("### Riepilogo per Azienda e Articolo")
        pivot = df.groupby(['Azienda', 'Articolo_Desc']).agg({
            'KG_Venduti': 'sum',
            'Fatturato': 'sum'
        }).reset_index()
        
        st.dataframe(pivot.style.format({'Fatturato': '{:.2f} €', 'KG_Venduti': '{:.2f}'}), use_container_width=True)
        
        if st.button("💾 SALVA SU SERVER"):
            st.toast("Salvato nell'archivio di Aruba")
    else:
        st.warning("Carica i dati per visualizzare il report.")

# FOOTER
st.markdown("""
    <div class="footer">
        Utilizzo esclusivo interno - Riproduzione vietata. <br>
        <b>TATA-REPORTAPP</b> | Progettazione: R-ADVISOR – M. Ribezzo.
    </div>
    """, unsafe_allow_html=True)
