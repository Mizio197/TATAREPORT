import streamlit as st
import pandas as pd
import plotly.express as px
import io
import os

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="TATA-REPORTAPP", layout="wide")

# --- CSS PER STAMPA E LAYOUT ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@400;600&display=swap');
    * { font-family: 'Quicksand', sans-serif; }
    .header-style { font-size: 24px; font-weight: bold; color: #1E3A8A; border-bottom: 2px solid #1E3A8A; padding-bottom: 10px; margin-bottom: 20px; }
    .sub-header { font-size: 18px; font-weight: bold; color: #4B5563; margin-top: 15px; }
    /* Forza sfondo bianco per le tabelle */
    [data-testid="stDataFrame"] { background-color: white; }
    </style>
""", unsafe_allow_html=True)

# --- MOTORE DI RICONOSCIMENTO DATI (ETICHETTATURA AUTOMATICA) ---
def normalize_row(row):
    """
    Analizza la riga per capire Famiglia e Origine anche se mancano le colonne specifiche,
    leggendo la descrizione dell'articolo.
    """
    desc = str(row.get('DESCRIZIONE', '')).upper()
    fam = str(row.get('FAMIGLIA', '')).upper()
    orig = str(row.get('ORIGINE', '')).upper()

    # 1. RICONOSCIMENTO FAMIGLIA (Se vuota o codice, cerca nella descrizione)
    if fam in ['NAN', 'NONE', '', 'ND'] or len(fam) < 2:
        if 'AGLIO' in desc or 'AGL' in desc: fam = 'AGLIO'
        elif 'ZENZERO' in desc or 'ZEN' in desc: fam = 'ZENZERO'
        elif 'SCALOGNO' in desc or 'SCA' in desc: fam = 'SCALOGNO'
        elif 'CIPOLLA' in desc: fam = 'CIPOLLA'
        else: fam = 'ALTRO'
    else:
        # Decodifica codici brevi comuni
        if 'AGL' in fam: fam = 'AGLIO'
        if 'SCA' in fam: fam = 'SCALOGNO'
        if 'ZEN' in fam: fam = 'ZENZERO'

    # 2. RICONOSCIMENTO ORIGINE
    if orig in ['NAN', 'NONE', '', 'ND'] or len(orig) < 2:
        if 'CINA' in desc or 'CN' in desc: orig = 'CINA'
        elif 'SPAGNA' in desc or 'ES' in desc: orig = 'SPAGNA'
        elif 'ITALIA' in desc or 'IT' in desc: orig = 'ITALIA'
        elif 'FRANCIA' in desc or 'FR' in desc: orig = 'FRANCIA'
        elif 'EGITTO' in desc: orig = 'EGITTO'
        elif 'PERU' in desc: orig = 'PERU'
        else: orig = 'MISTO/UE'
    else:
        # Normalizzazione nomi
        if 'IT' in orig: orig = 'ITALIA'
        if 'CN' in orig: orig = 'CINA'
        if 'ES' in orig: orig = 'SPAGNA'
        if 'FR' in orig: orig = 'FRANCIA'

    return pd.Series([fam, orig], index=['FAMIGLIA_NORM', 'ORIGINE_NORM'])

def load_data(uploaded_file):
    try:
        # Legge provando diversi formati
        try:
            df = pd.read_excel(uploaded_file, header=1)
        except:
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, header=1, sep=None, engine='python')

        # Normalizzazione Nomi Colonne (Rimuove spazi e maiuscolo)
        df.columns = [str(c).strip().upper() for c in df.columns]

        # Mappatura Colonne del Gestionale -> Nomi Standard
        rename_map = {}
        # Cerca colonne chiave
        for c in df.columns:
            if 'QTAMOV' in c or 'KG' in c or 'COLLI' in c: rename_map[c] = 'KG'
            elif 'PREZZO' in c or 'VALORIZZAZIONE' in c: rename_map[c] = 'PREZZO'
            elif 'DESCRI' in c or 'ARTICOLO' in c: rename_map[c] = 'DESCRIZIONE'
            elif 'FAMIGLIA' in c: rename_map[c] = 'FAMIGLIA'
            elif 'ORIGINE' in c: rename_map[c] = 'ORIGINE'
            elif 'DATDOC' in c or 'DATA' in c: rename_map[c] = 'DATA'
        
        df = df.rename(columns=rename_map)

        # Pulizia Numeri
        for col in ['KG', 'PREZZO']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            else:
                df[col] = 0.0 # Se manca mette 0

        # Calcolo Fatturato Riga
        df['FATTURATO'] = df['KG'] * df['PREZZO']

        # *** APPLICAZIONE INTELLIGENZA PER CATEGORIE ***
        # Applica la funzione normalize_row riga per riga
        norm_data = df.apply(normalize_row, axis=1)
        df['FAMIGLIA'] = norm_data['FAMIGLIA_NORM']
        df['ORIGINE'] = norm_data['ORIGINE_NORM']

        return df
    except Exception as e:
        st.error(f"Errore lettura file: {e}")
        return pd.DataFrame()

# --- LOGICA PIVOT (Replica Excel) ---
def generate_pivot(df, costi_std):
    if df.empty: return pd.DataFrame()

    # Raggruppa per Famiglia e Origine
    pivot = df.groupby(['FAMIGLIA', 'ORIGINE']).agg(
        KG_VENDUTI=('KG', 'sum'),
        FATTURATO_VENDITE=('FATTURATO', 'sum')
    ).reset_index()

    # Calcolo Prezzo Medio Vendita
    pivot['PREZZO_MEDIO_VENDITA'] = pivot['FATTURATO_VENDITE'] / pivot['KG_VENDUTI']
    
    # --- CALCOLO MARGINI E COSTI ---
    # Qui inseriamo la logica: Margine = (Prezzo Vendita - Costo Acquisto) * KG
    # Cerchiamo il costo nel dizionario, se non c'è usiamo un default
    
    def get_cost(row):
        key = (row['FAMIGLIA'], row['ORIGINE'])
        # Cerca costo specifico (es. Aglio Cina), altrimenti costo generico Famiglia, altrimenti default
        return costi_std.get(key, costi_std.get(row['FAMIGLIA'], 1.0)) # Default 1€ se non trovato

    pivot['COSTO_MEDIO_ACQUISTO'] = pivot.apply(get_cost, axis=1)
    
    # Calcolo valori finali
    pivot['COSTO_TOTALE_VENDUTO'] = pivot['KG_VENDUTI'] * pivot['COSTO_MEDIO_ACQUISTO']
    pivot['MARGINE_UNITARIO'] = pivot['PREZZO_MEDIO_VENDITA'] - pivot['COSTO_MEDIO_ACQUISTO']
    pivot['MARGINE_TOTALE'] = pivot['MARGINE_UNITARIO'] * pivot['KG_VENDUTI']
    pivot['% MARGINE'] = (pivot['MARGINE_TOTALE'] / pivot['FATTURATO_VENDITE']) * 100

    return pivot

# --- INTERFACCIA ---
st.sidebar.title("TATA REPORT APP")
page = st.sidebar.radio("Navigazione", ["Caricamento & Setup", "Report Pivot", "Grafici"])

# Costi di Riferimento (Modificabili dall'utente in sidebar per simulare il magazzino)
st.sidebar.markdown("---")
st.sidebar.header("🛠️ Configurazione Costi Acquisto")
st.sidebar.info("Inserisci qui i costi medi di acquisto per calcolare il margine reale, dato che il file contiene solo le vendite.")

costi_input = {}
famiglie_std = ['AGLIO', 'ZENZERO', 'SCALOGNO', 'CIPOLLA']
origini_std = ['CINA', 'SPAGNA', 'ITALIA', 'FRANCIA']

# Input rapido costi
with st.sidebar.expander("Modifica Listino Costi", expanded=True):
    costi_input[('AGLIO', 'CINA')] = st.number_input("Costo Aglio CINA", value=1.44)
    costi_input[('AGLIO', 'SPAGNA')] = st.number_input("Costo Aglio SPAGNA", value=2.20)
    costi_input[('AGLIO', 'ITALIA')] = st.number_input("Costo Aglio ITALIA", value=2.50)
    costi_input[('ZENZERO', 'CINA')] = st.number_input("Costo Zenzero CINA", value=1.60)
    costi_input[('SCALOGNO', 'FRANCIA')] = st.number_input("Costo Scalogno FRANCIA", value=1.30)
    costi_input[('SCALOGNO', 'ITALIA')] = st.number_input("Costo Scalogno ITALIA", value=3.00)

if 'data_main' not in st.session_state: st.session_state['data_main'] = pd.DataFrame()

if page == "Caricamento & Setup":
    st.markdown('<div class="header-style">Importazione Dati Grezzi</div>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    f1 = col1.file_uploader("TA.TA Srl", key="f1")
    f2 = col2.file_uploader("GIARDINO DELL'AGLIO", key="f2")
    f3 = col3.file_uploader("ANGELO TATA SRL", key="f3")

    if st.button("ELABORA REPORT COMPLETO", type="primary"):
        dfs = []
        if f1: dfs.append(load_data(f1))
        if f2: dfs.append(load_data(f2))
        if f3: dfs.append(load_data(f3))
        
        if dfs:
            full_df = pd.concat(dfs, ignore_index=True)
            st.session_state['data_main'] = full_df
            st.success(f"Caricamento completato: {len(full_df)} righe analizzate.")
        else:
            st.error("Carica almeno un file.")

elif page == "Report Pivot":
    st.markdown('<div class="header-style">Report Analitico (Simil-Excel)</div>', unsafe_allow_html=True)
    
    if not st.session_state['data_main'].empty:
        df = st.session_state['data_main']
        
        # Filtri Data
        if 'DATA' in df.columns:
            min_d = pd.to_datetime(df['DATA']).min().date()
            max_d = pd.to_datetime(df['DATA']).max().date()
            c1, c2 = st.columns(2)
            d1 = c1.date_input("Dal:", min_d)
            d2 = c2.date_input("Al:", max_d)
            # Applica filtro
            df['DATA'] = pd.to_datetime(df['DATA'])
            mask = (df['DATA'].dt.date >= d1) & (df['DATA'].dt.date <= d2)
            df = df.loc[mask]

        # Generazione Pivot
        pivot_data = generate_pivot(df, costi_input)

        # Formattazione per visualizzazione (pulita)
        view_df = pivot_data.copy()
        
        # Colonne da mostrare
        cols_order = ['FAMIGLIA', 'ORIGINE', 'KG_VENDUTI', 'FATTURATO_VENDITE', 'PREZZO_MEDIO_VENDITA', 'COSTO_MEDIO_ACQUISTO', 'MARGINE_TOTALE', '% MARGINE']
        view_df = view_df[cols_order]

        # Formattazione Numerica
        view_df['KG_VENDUTI'] = view_df['KG_VENDUTI'].map('{:,.0f}'.format)
        view_df['FATTURATO_VENDITE'] = view_df['FATTURATO_VENDITE'].map('€ {:,.2f}'.format)
        view_df['PREZZO_MEDIO_VENDITA'] = view_df['PREZZO_MEDIO_VENDITA'].map('€ {:,.3f}'.format)
        view_df['COSTO_MEDIO_ACQUISTO'] = view_df['COSTO_MEDIO_ACQUISTO'].map('€ {:,.3f}'.format)
        view_df['MARGINE_TOTALE'] = view_df['MARGINE_TOTALE'].map('€ {:,.2f}'.format)
        view_df['% MARGINE'] = view_df['% MARGINE'].map('{:.1f}%'.format)

        # Visualizzazione Tabella
        st.dataframe(view_df, use_container_width=True, height=600)

        # Export
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            view_df.to_excel(writer, sheet_name='REPORT_PIVOT')
        
        st.download_button("📥 Scarica Report Excel", buffer, "Report_Pivot_Tata.xlsx")
        
    else:
        st.warning("Torna a 'Caricamento & Setup' e carica i file.")

elif page == "Grafici":
    st.markdown('<div class="header-style">Dashboard Grafica</div>', unsafe_allow_html=True)
    if not st.session_state['data_main'].empty:
        pivot_data = generate_pivot(st.session_state['data_main'], costi_input)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown('<p class="sub-header">Fatturato per Famiglia/Origine</p>', unsafe_allow_html=True)
            fig = px.bar(pivot_data, x="FAMIGLIA", y="FATTURATO_VENDITE", color="ORIGINE", barmode="group", text_auto='.2s')
            st.plotly_chart(fig, use_container_width=True)
            
        with col2:
            st.markdown('<p class="sub-header">Margine Totale Generato</p>', unsafe_allow_html=True)
            fig2 = px.bar(pivot_data, x="FAMIGLIA", y="MARGINE_TOTALE", color="ORIGINE", text_auto='.2s')
            st.plotly_chart(fig2, use_container_width=True)
