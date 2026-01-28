import streamlit as st
import pandas as pd
import plotly.express as px
import os
from datetime import datetime
import io

# --- CONFIGURAZIONE PAGINA E STILE ---
st.set_page_config(
    page_title="TATA-REPORTAPP",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Stile CSS
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@300;400;600&display=swap');
    html, body, [class*="css"]  { font-family: 'Quicksand', sans-serif; }
    .main-header { font-size: 2.5rem; color: #2c3e50; font-weight: 600; }
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #f1f1f1; 
              color: #555; text-align: center; padding: 10px; font-size: 0.8rem; 
              border-top: 1px solid #ddd; z-index: 100; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    </style>
    <div class="footer">
        <p>USO ESCLUSIVO INTERNO - DIVIETO DI RIPRODUZIONE<br>
        Tributo a R-ADVISOR – M. Ribezzo per progettazione e realizzazione | TATA-REPORTAPP v1.1</p>
    </div>
""", unsafe_allow_html=True)

# --- FUNZIONE DI CARICAMENTO AVANZATA ---
def load_data(uploaded_file, company_name):
    """
    Legge file XLS/XLSX o CSV (anche se rinominati erroneamente).
    """
    df = None
    
    # 1. Tentativo come Excel
    try:
        # header=1 prende la riga 2 come intestazione (come da tua specifica)
        df = pd.read_excel(uploaded_file, header=1)
    except Exception:
        # Se fallisce (es. manca xlrd o è un CSV mascherato), proviamo come CSV
        try:
            uploaded_file.seek(0)
            # engine='python' e sep=None permettono di indovinare il separatore (virgola o punto e virgola)
            df = pd.read_csv(uploaded_file, header=1, sep=None, engine='python')
        except Exception as e:
            st.error(f"❌ Errore lettura file {company_name}: Il file non è né un Excel valido né un CSV leggibile.")
            return None

    if df is not None:
        # --- PULIZIA COLONNE ---
        # Rimuove spazi e mette tutto in maiuscolo per standardizzare
        df.columns = [str(c).strip().upper() for c in df.columns]
        
        # MAPPATURA NOMI COLONNE (Adatta alle intestazioni del tuo file)
        # Chiave: Nome trovato nel file (MAIUSCOLO) -> Valore: Nome standard per il report
        col_map = {
            'MMQTAMOV': 'KG',
            'KG': 'KG',
            'COLLI': 'KG',          # Fallback se KG manca
            'MMPREZZO': 'PREZZO_UNITARIO',
            'PREZZO UNITA DI MISURA': 'PREZZO_UNITARIO',
            'FAMIGLIA': 'FAMIGLIA',
            'ORIGINE': 'ORIGINE',
            'MMDATDOC': 'DATA',
            'DATA': 'DATA',
            'DDNOMDES': 'CLIENTE',
            'CLIENTE': 'CLIENTE',
            'ARTICOLO ESTESO': 'DESCRIZIONE',
            'ARDESART': 'DESCRIZIONE'
        }
        
        # Rinomina le colonne
        df = df.rename(columns=col_map)
        df['AZIENDA_ORIGINE'] = company_name

        # --- CONTROLLI DI SICUREZZA ---
        # Se dopo la rinomina non troviamo KG o PREZZO, proviamo a cercarli parzialmente
        if 'KG' not in df.columns:
            # Cerca colonne che contengono "QTA" o "KG"
            for c in df.columns:
                if 'QTA' in c or 'KG' in c:
                    df = df.rename(columns={c: 'KG'})
                    break
            else:
                st.warning(f"⚠️ Nel file {company_name} non trovo la colonna 'KG'. I volumi saranno 0.")
                df['KG'] = 0

        if 'PREZZO_UNITARIO' not in df.columns:
            for c in df.columns:
                if 'PREZZO' in c or 'VAL' in c:
                    df = df.rename(columns={c: 'PREZZO_UNITARIO'})
                    break
            else:
                df['PREZZO_UNITARIO'] = 0

        # Conversione numeri
        for col in ['KG', 'PREZZO_UNITARIO']:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        # Calcolo Fatturato Riga
        df['FATTURATO'] = df['KG'] * df['PREZZO_UNITARIO']
        
        # Conversione Data
        if 'DATA' in df.columns:
            df['DATA'] = pd.to_datetime(df['DATA'], errors='coerce')
            
        return df
    
    return None

def process_report(df_total):
    if df_total is None or df_total.empty:
        return pd.DataFrame()

    # Raggruppamento Pivot
    # Controlliamo se FAMIGLIA e ORIGINE esistono, altrimenti usiamo un valore default
    if 'FAMIGLIA' not in df_total.columns: df_total['FAMIGLIA'] = 'ND'
    if 'ORIGINE' not in df_total.columns: df_total['ORIGINE'] = 'ND'

    pivot = df_total.groupby(['FAMIGLIA', 'ORIGINE']).agg(
        KG_TOTALE=('KG', 'sum'),
        FATTURATO_TOTALE=('FATTURATO', 'sum')
    ).reset_index()
    
    # Calcoli KPI
    pivot['PREZZO_MEDIO'] = 0.0
    mask = pivot['KG_TOTALE'] > 0
    pivot.loc[mask, 'PREZZO_MEDIO'] = pivot.loc[mask, 'FATTURATO_TOTALE'] / pivot.loc[mask, 'KG_TOTALE']
    
    # Margine (Simulato come da richiesta precedente, personalizzabile)
    pivot['MARGINE_1'] = pivot['PREZZO_MEDIO'] * 0.25 
    pivot['MARGINE_TOTALE'] = pivot['MARGINE_1'] * pivot['KG_TOTALE']
    
    return pivot

# --- INTERFACCIA UTENTE ---
st.sidebar.title("MENU")
page = st.sidebar.radio("Vai a:", ["1. Caricamento", "2. Report", "3. Archivio", "4. Grafici"])

# Inizializzazione dati
if 'df_main' not in st.session_state: st.session_state['df_main'] = pd.DataFrame()

if page == "1. Caricamento":
    st.markdown('<div class="main-header">Importazione Dati</div>', unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns(3)
    f1 = c1.file_uploader("TA.TA Srl", key="f1")
    f2 = c2.file_uploader("GIARDINO DELL'AGLIO", key="f2")
    f3 = c3.file_uploader("ANGELO TATA SRL", key="f3")
    
    st.divider()
    
    # Opzioni
    col_opt1, col_opt2 = st.columns(2)
    with col_opt1:
        filtro_data = st.toggle("Filtra per Data")
        if filtro_data:
            d1 = st.date_input("Dal")
            d2 = st.date_input("Al")
    
    with col_opt2:
        modo_az = st.radio("Aziende:", ["Tutte (Cumulativo)", "Seleziona"])
        scelte = ["TATA", "GIARDINO", "ANGELO"]
        if modo_az == "Seleziona":
            scelte = []
            if st.checkbox("TA.TA"): scelte.append("TATA")
            if st.checkbox("GIARDINO"): scelte.append("GIARDINO")
            if st.checkbox("ANGELO"): scelte.append("ANGELO")

    if st.button("ELABORA REPORT 🚀", type="primary"):
        dfs = []
        # Caricamento condizionale
        if f1 and ("TATA" in scelte or modo_az.startswith("Tutte")): 
            dfs.append(load_data(f1, "TA.TA Srl"))
        if f2 and ("GIARDINO" in scelte or modo_az.startswith("Tutte")): 
            dfs.append(load_data(f2, "GIARDINO Srl"))
        if f3 and ("ANGELO" in scelte or modo_az.startswith("Tutte")): 
            dfs.append(load_data(f3, "ANGELO TATA Srl"))
            
        dfs = [d for d in dfs if d is not None]
        
        if dfs:
            full = pd.concat(dfs, ignore_index=True)
            if filtro_data and 'DATA' in full.columns:
                full = full[(full['DATA'].dt.date >= d1) & (full['DATA'].dt.date <= d2)]
            
            st.session_state['df_main'] = full
            st.success(f"Caricate {len(full)} righe totali! Vai alla pagina Report.")
        else:
            st.error("Nessun file valido caricato.")

elif page == "2. Report":
    st.markdown('<div class="main-header">Report Tabellare</div>', unsafe_allow_html=True)
    if not st.session_state['df_main'].empty:
        rep = process_report(st.session_state['df_main'])
        
        # Formattazione per visualizzazione
        show = rep.copy()
        for c in ['FATTURATO_TOTALE', 'PREZZO_MEDIO', 'MARGINE_TOTALE']:
            show[c] = show[c].map('€ {:,.2f}'.format)
        show['KG_TOTALE'] = show['KG_TOTALE'].map('{:,.0f}'.format)
        
        st.dataframe(show, use_container_width=True, height=600)
        
        # Export
        import io
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            rep.to_excel(writer, index=False)
        st.download_button("📥 Scarica Excel", buffer, "Report_TATA.xlsx")
    else:
        st.info("Carica prima i dati nella pagina 1.")

elif page == "4. Grafici":
    st.markdown('<div class="main-header">Dashboard</div>', unsafe_allow_html=True)
    if not st.session_state['df_main'].empty:
        df = st.session_state['df_main']
        rep = process_report(df)
        
        k1, k2, k3 = st.columns(3)
        k1.metric("Fatturato Totale", f"€ {rep['FATTURATO_TOTALE'].sum():,.2f}")
        k2.metric("Volume Totale (KG)", f"{rep['KG_TOTALE'].sum():,.0f}")
        k3.metric("Prezzo Medio", f"€ {rep['FATTURATO_TOTALE'].sum()/rep['KG_TOTALE'].sum():.2f}")
        
        st.divider()
        c1, c2 = st.columns(2)
        # Grafico Barre
        fig = px.bar(rep, x='FAMIGLIA', y='FATTURATO_TOTALE', color='ORIGINE', title="Fatturato per Famiglia")
        c1.plotly_chart(fig, use_container_width=True)
        # Grafico Torta
        fig2 = px.pie(rep, values='KG_TOTALE', names='ORIGINE', title="Distribuzione Volumi per Origine")
        c2.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Dati mancanti.")
