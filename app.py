import streamlit as st
import pandas as pd
import datetime

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="TATA-REPORTAPP", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@300;400;500;600&display=swap');
    html, body, [class*="css"] { font-family: 'Quicksand', sans-serif; }
    .footer { position: fixed; bottom: 0; left: 0; width: 100%; background: white; text-align: center; padding: 10px; font-size: 11px; border-top: 1px solid #eee; }
    </style>
    """, unsafe_allow_html=True)

# Mappatura basata sulla tua riga di istruzioni (Codice Gestionale -> Nome Report)
MAPPING_TECNICO = {
    'andescri': 'Cliente',
    'ardesart': 'Articolo_Desc',
    'mmdatdoc': 'Data',
    'mmqtamov': 'Qta_Movimento',
    'mmprezzo': 'Prezzo_Unitario',
    'qtano': 'KG_Venduti',
    'arcodfam': 'Categoria'
}

def safe_open(file):
    try:
        # Tenta Excel
        return pd.read_excel(file)
    except:
        # Tenta CSV se l'Excel fallisce (comune negli export gestionali)
        file.seek(0)
        return pd.read_csv(file, sep=None, engine='python')

# --- LOGICA DI ELABORAZIONE ---
def process_data(dict_files, companies, start_date, end_date):
    v_list = []
    for comp in companies:
        raw_df = safe_open(dict_files[comp]['v'])
        if raw_df is not None:
            # Applica mapping
            df = raw_df.rename(columns=MAPPING_TECNICO)
            df['Azienda'] = comp
            
            # Conversione Data
            if 'Data' in df.columns:
                df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
            
            # Assicura che le colonne numeriche esistano per evitare KeyError
            if 'KG_Venduti' not in df.columns and 'mmqtamov' not in df.columns:
                # Se non trova il mapping, prova a indovinare la colonna dei KG
                if 'qtano' in raw_df.columns: df['KG_Venduti'] = raw_df['qtano']
            
            v_list.append(df)
            
    if not v_list: return None
    
    full_v = pd.concat(v_list, ignore_index=True)
    
    # Pulizia Numerica e Calcolo Fatturato
    for c in ['KG_Venduti', 'Prezzo_Unitario']:
        if c in full_v.columns:
            full_v[c] = pd.to_numeric(full_v[c], errors='coerce').fillna(0)
    
    if 'KG_Venduti' in full_v.columns and 'Prezzo_Unitario' in full_v.columns:
        full_v['Fatturato'] = full_v['KG_Venduti'] * full_v['Prezzo_Unitario']
    else:
        full_v['Fatturato'] = 0
        
    return full_v

# --- INTERFACCIA ---
page = st.sidebar.radio("NAVIGAZIONE", ["CARICAMENTO", "REPORT"])

if page == "CARICAMENTO":
    st.title("TATA-REPORTAPP - Upload")
    comps = ["TA.TA Srl", "GIARDINO DELL’AGLIO SRL", "ANGELO TATA SRL"]
    uploaded = {}
    
    c1, c2, c3 = st.columns(3)
    for i, comp in enumerate(comps):
        with [c1, c2, c3][i]:
            v = st.file_uploader(f"Vendite {comp}", type=['xlsx', 'xls', 'csv'], key=f"u{i}")
            uploaded[comp] = {'v': v}
            
    d1 = st.date_input("Inizio", datetime.date(2025, 12, 1))
    d2 = st.date_input("Fine", datetime.date(2025, 12, 31))
    
    if st.button("ELABORA REPORT"):
        res = process_data(uploaded, comps, d1, d2)
        if res is not None:
            st.session_state['data'] = res
            st.success("Dati elaborati!")
        else:
            st.error("Nessun file caricato correttamente.")

elif page == "REPORT":
    st.title("Report Sinottico")
    if 'data' in st.session_state:
        df = st.session_state['data']
        
        # CONTROLLO DI SICUREZZA: Se le colonne mancano, le cerchiamo nei nomi originali
        group_col = 'Articolo_Desc' if 'Articolo_Desc' in df.columns else (
                    'ardesart' if 'ardesart' in df.columns else df.columns[0])
        
        st.write(f"### Analisi per {group_col}")
        
        # Pivot dinamica che non crasha se mancano colonne
        try:
            agg_dict = {}
            if 'KG_Venduti' in df.columns: agg_dict['KG_Venduti'] = 'sum'
            if 'Fatturato' in df.columns: agg_dict['Fatturato'] = 'sum'
            
            pivot = df.groupby(['Azienda', group_col]).agg(agg_dict).reset_index()
            st.dataframe(pivot, use_container_width=True)
        except Exception as e:
            st.error(f"Errore nella creazione della tabella: {e}")
            st.write("Colonne disponibili nel file:", df.columns.tolist())
            
    else:
        st.warning("Torna alla pagina CARICAMENTO.")

st.markdown('<div class="footer">TATA-REPORTAPP | R-ADVISOR – M. Ribezzo</div>', unsafe_allow_html=True)
