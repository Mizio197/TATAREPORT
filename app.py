import streamlit as st
import pandas as pd
import datetime

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="TATA-REPORTAPP", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@300;400;500;600&display=swap');
    html, body, [class*="css"] { font-family: 'Quicksand', sans-serif; }
    .main-header { font-size: 30px; font-weight: 600; color: #1e3a8a; text-align: center; margin-bottom: 20px; }
    .footer { position: fixed; bottom: 0; left: 0; width: 100%; background: white; text-align: center; padding: 10px; font-size: 11px; border-top: 1px solid #eee; }
    </style>
    """, unsafe_allow_html=True)

# Mappatura dei codici grezzi estratti dal tuo applicativo
MAPPING_VENDITE = {
    'andescri': 'Cliente', 
    'ardesart': 'Articolo_Desc', 
    'mmdatdoc': 'Data', 
    'mmqtamov': 'Qta_Movimento', 
    'mmprezzo': 'Prezzo_Vendita',
    'arcodfam': 'Categoria',
    'qtano': 'KG_Venduti',
    'mmcolli': 'Colli'
}

def load_data(file):
    if file is None: return None
    try:
        # Tenta Excel (.xlsx o .xls)
        df = pd.read_excel(file)
    except:
        # Se fallisce, tenta CSV (molti .xls sono in realtà CSV)
        file.seek(0)
        df = pd.read_csv(file, sep=None, engine='python')
    
    # Pulizia nomi colonne: toglie spazi e rende minuscolo per il confronto
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df

# --- LOGICA DI ELABORAZIONE SICURA ---
def process_data(dict_files, companies, d_in, d_fi):
    v_list = []
    for c in companies:
        raw_v = load_data(dict_files[c]['v'])
        if raw_v is not None:
            # Rinomina usando il mapping (anche se i nomi sono minuscoli)
            df = raw_v.rename(columns={k: v for k, v in MAPPING_VENDITE.items()})
            df['Azienda'] = c
            
            # --- CORREZIONE KEYERROR: Fallback dinamico ---
            if 'KG_Venduti' not in df.columns:
                if 'qtano' in df.columns: df['KG_Venduti'] = df['qtano']
                elif 'mmqtamov' in df.columns: df['KG_Venduti'] = df['mmqtamov']
                else: df['KG_Venduti'] = 0  # Evita il crash se la colonna manca
            
            if 'Prezzo_Vendita' not in df.columns:
                if 'mmprezzo' in df.columns: df['Prezzo_Vendita'] = df['mmprezzo']
                else: df['Prezzo_Vendita'] = 0

            # Conversione Numerica
            df['KG_Venduti'] = pd.to_numeric(df['KG_Venduti'], errors='coerce').fillna(0)
            df['Prezzo_Vendita'] = pd.to_numeric(df['Prezzo_Vendita'], errors='coerce').fillna(0)
            
            # Calcolo Fatturato riga per riga
            df['Fatturato'] = df['KG_Venduti'] * df['Prezzo_Vendita']
            
            v_list.append(df)
    
    if not v_list: return None
    return pd.concat(v_list, ignore_index=True)

# --- INTERFACCIA ---
if 'data' not in st.session_state: st.session_state.data = None

menu = st.sidebar.radio("MENU", ["UPLOAD", "REPORT"])

if menu == "UPLOAD":
    st.markdown('<div class="main-header">TATA-REPORTAPP - Upload</div>', unsafe_allow_html=True)
    comps = ["TA.TA Srl", "GIARDINO DELL’AGLIO SRL", "ANGELO TATA SRL"]
    files = {}
    
    col1, col2, col3 = st.columns(3)
    for i, c in enumerate(comps):
        with [col1, col2, col3][i]:
            st.subheader(c)
            v = st.file_uploader(f"Vendite", key=f"v{i}")
            m = st.file_uploader(f"Magazzino", key=f"m{i}")
            files[c] = {'v': v, 'm': m}
            
    st.divider()
    d1 = st.date_input("Inizio", datetime.date(2025, 12, 1))
    d2 = st.date_input("Fine", datetime.date(2025, 12, 31))
    
    if st.button("ELABORA REPORT", use_container_width=True):
        res = process_data(files, comps, d1, d2)
        if res is not None:
            st.session_state.data = res
            st.success("Dati pronti! Vai alla pagina REPORT.")
        else:
            st.error("Nessun file caricato o formato non riconosciuto.")

elif menu == "REPORT":
    st.markdown('<div class="main-header">Quadro Sinottico Elaborato</div>', unsafe_allow_html=True)
    if st.session_state.data is not None:
        df = st.session_state.data
        
        # Raggruppamento per il report sinottico
        st.write("### Analisi Vendite per Azienda e Prodotto")
        
        # Cerchiamo la colonna articolo mappata o originale
        art_col = 'Articolo_Desc' if 'Articolo_Desc' in df.columns else (
                  'ardesart' if 'ardesart' in df.columns else df.columns[0])
        
        pivot = df.groupby(['Azienda', art_col]).agg({
            'KG_Venduti': 'sum',
            'Fatturato': 'sum'
        }).reset_index()
        
        st.dataframe(pivot.style.format({'Fatturato': '{:.2f} €', 'KG_Venduti': '{:.2f}'}), use_container_width=True)
    else:
        st.warning("Carica i file nella pagina UPLOAD.")

st.markdown('<div class="footer">TATA-REPORTAPP | R-ADVISOR – M. Ribezzo</div>', unsafe_allow_html=True)
