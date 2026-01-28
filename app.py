import streamlit as st
import pandas as pd
import plotly.express as px
import os
from datetime import datetime
import io

# --- CONFIGURAZIONE PAGINA E STILI ---
st.set_page_config(
    page_title="TATA-REPORTAPP",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@300;400;500;700&display=swap');
    html, body, [class*="css"] { font-family: 'Quicksand', sans-serif; }
    .header-style { font-size: 24px; font-weight: bold; color: #2c3e50; border-bottom: 2px solid #2c3e50; padding-bottom: 10px; margin-bottom: 20px; }
    @media print {
        div[data-testid="stSidebar"] {display: none;}
        .stButton {display: none;}
        div[data-testid="stDecoration"] {display: none;}
        footer {display: none;}
    }
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: white; color: grey; text-align: center; padding: 10px; border-top: 1px solid #eaeaea; font-size: 12px; }
    </style>
""", unsafe_allow_html=True)

# --- FUNZIONI DI ELABORAZIONE DATI ---

def load_data(file):
    """Carica CSV, XLS o XLSX."""
    if file is None: return None
    try:
        if file.name.endswith('.csv'):
            try: df = pd.read_csv(file, sep=';', encoding='latin1')
            except: 
                file.seek(0)
                df = pd.read_csv(file, sep=',', encoding='utf-8')
        elif file.name.endswith('.xls'):
            df = pd.read_excel(file, engine='xlrd')
        else:
            df = pd.read_excel(file)
        return df
    except Exception as e:
        st.error(f"Errore caricamento {file.name}: {e}")
        return None

def pulisci_e_standardizza(df, tipo):
    """Pulisce i nomi delle colonne rimuovendo spazi e convertendo in maiuscolo."""
    if df is None: return None
    # Rimuove spazi vuoti e converte in stringa e maiuscolo
    df.columns = [str(c).strip().upper() for c in df.columns]
    
    # Conversione date
    cols_data = [c for c in df.columns if 'DATA' in c]
    for c in cols_data:
        df[c] = pd.to_datetime(df[c], errors='coerce')
    return df

def trova_colonna(df, keywords):
    """Cerca una colonna che contenga una delle parole chiave."""
    for col in df.columns:
        for kw in keywords:
            if kw in col:
                return col
    return None

def elabora_report(df_vendite, df_acquisti, data_inizio, data_fine, azienda):
    # --- FILTRI DATA ---
    if df_vendite is not None:
        col_data_v = trova_colonna(df_vendite, ['DATA', 'GIORNO'])
        if col_data_v:
            df_vendite = df_vendite[(df_vendite[col_data_v] >= pd.to_datetime(data_inizio)) & 
                                    (df_vendite[col_data_v] <= pd.to_datetime(data_fine))]

    if df_acquisti is not None:
        col_data_a = trova_colonna(df_acquisti, ['DATA', 'GIORNO', 'ARRIVO'])
        if col_data_a:
            df_acquisti = df_acquisti[(df_acquisti[col_data_a] >= pd.to_datetime(data_inizio)) & 
                                      (df_acquisti[col_data_a] <= pd.to_datetime(data_fine))]

    if (df_vendite is None or df_vendite.empty) and (df_acquisti is None or df_acquisti.empty):
        return None

    pivot_vendite = pd.DataFrame()
    pivot_acquisti = pd.DataFrame()

    # --- ELABORAZIONE VENDITE ---
    if df_vendite is not None and not df_vendite.empty:
        # Cerca colonne flessibili
        col_origine_v = trova_colonna(df_vendite, ['ORIGINE', 'FAMIGLIA'])
        col_kg_v = trova_colonna(df_vendite, ['KG', 'QTA', 'QUANTITA', 'PESO'])
        col_fatt_v = trova_colonna(df_vendite, ['FATTURATO', 'IMPORTO', 'VALORE', 'TOTALE'])

        # Se non trova le colonne fondamentali, avvisa l'utente
        if not col_origine_v or not col_kg_v or not col_fatt_v:
            st.error(f"⚠️ Errore file VENDITE {azienda}: Colonne mancanti. Trovate: {list(df_vendite.columns)}")
            return None

        # Standardizza colonne origine
        if col_origine_v != 'ORIGINE':
            df_vendite.rename(columns={col_origine_v: 'ORIGINE'}, inplace=True)
            col_origine_v = 'ORIGINE'

        # Pulisci numeri
        df_vendite[col_kg_v] = pd.to_numeric(df_vendite[col_kg_v], errors='coerce').fillna(0)
        df_vendite[col_fatt_v] = pd.to_numeric(df_vendite[col_fatt_v], errors='coerce').fillna(0)
        
        pivot_vendite = df_vendite.groupby(col_origine_v).agg({
            col_kg_v: 'sum',
            col_fatt_v: 'sum'
        }).reset_index()
        pivot_vendite.rename(columns={col_kg_v: 'KG_VENDUTI', col_fatt_v: 'FATTURATO_VENDITA'}, inplace=True)
        pivot_vendite['PREZZO_MEDIO_VENDITA'] = pivot_vendite['FATTURATO_VENDITA'] / pivot_vendite['KG_VENDUTI']

    # --- ELABORAZIONE ACQUISTI ---
    if df_acquisti is not None and not df_acquisti.empty:
        col_origine_a = trova_colonna(df_acquisti, ['ORIGINE', 'FAMIGLIA'])
        col_kg_a = trova_colonna(df_acquisti, ['KG', 'QTA', 'ACQUISTATI'])
        col_costo_a = trova_colonna(df_acquisti, ['COSTO', 'TOTALE ACQUISTO', 'IMPORTO'])

        if not col_origine_a or not col_kg_a or not col_costo_a:
            st.error(f"⚠️ Errore file ACQUISTI {azienda}: Colonne mancanti. Trovate: {list(df_acquisti.columns)}")
            return None

        if col_origine_a != 'ORIGINE':
            df_acquisti.rename(columns={col_origine_a: 'ORIGINE'}, inplace=True)
            col_origine_a = 'ORIGINE'

        df_acquisti[col_kg_a] = pd.to_numeric(df_acquisti[col_kg_a], errors='coerce').fillna(0)
        df_acquisti[col_costo_a] = pd.to_numeric(df_acquisti[col_costo_a], errors='coerce').fillna(0)

        pivot_acquisti = df_acquisti.groupby(col_origine_a).agg({
            col_kg_a: 'sum',
            col_costo_a: 'sum'
        }).reset_index()
        pivot_acquisti['COSTO_MEDIO_ACQUISTO'] = pivot_acquisti[col_costo_a] / pivot_acquisti[col_kg_a]
        pivot_acquisti = pivot_acquisti[['ORIGINE', 'COSTO_MEDIO_ACQUISTO', col_kg_a, col_costo_a]]
    else:
        pivot_acquisti = pd.DataFrame(columns=['ORIGINE', 'COSTO_MEDIO_ACQUISTO'])

    # --- UNIONE E CALCOLI ---
    if not pivot_vendite.empty:
        report_finale = pd.merge(pivot_vendite, pivot_acquisti, on='ORIGINE', how='left')
    elif not pivot_acquisti.empty:
        report_finale = pivot_acquisti.copy()
        report_finale['KG_VENDUTI'] = 0
        report_finale['FATTURATO_VENDITA'] = 0
        report_finale['PREZZO_MEDIO_VENDITA'] = 0
    else:
        return None
        
    report_finale['COSTO_MEDIO_ACQUISTO'] = report_finale['COSTO_MEDIO_ACQUISTO'].fillna(0)
    report_finale['KG_VENDUTI'] = report_finale['KG_VENDUTI'].fillna(0)
    report_finale['FATTURATO_VENDITA'] = report_finale['FATTURATO_VENDITA'].fillna(0)

    report_finale['COSTO_VENDUTO_TEORICO'] = report_finale['KG_VENDUTI'] * report_finale['COSTO_MEDIO_ACQUISTO']
    report_finale['MARGINE_1_VALORE'] = report_finale['FATTURATO_VENDITA'] - report_finale['COSTO_VENDUTO_TEORICO']
    
    report_finale['MARGINE_PERCENTUALE'] = report_finale.apply(
        lambda x: (x['MARGINE_1_VALORE'] / x['FATTURATO_VENDITA'] * 100) if x['FATTURATO_VENDITA'] != 0 else 0, axis=1
    )
    
    report_finale['AZIENDA'] = azienda
    return report_finale


# --- UI: SIDEBAR ---
st.sidebar.title("NAVIGAZIONE")
pagina = st.sidebar.radio("Vai a:", ["1. Input Dati", "2. Elaborazione Report", "3. Archivio", "4. Grafica & Analisi"])

SAVE_DIR = "archivio_report"
if not os.path.exists(SAVE_DIR): os.makedirs(SAVE_DIR)
if 'data_storage' not in st.session_state: st.session_state['data_storage'] = {}

# --- PAGINA 1: INPUT ---
if pagina == "1. Input Dati":
    st.markdown('<div class="header-style">INSERIMENTO DATI GREZZI</div>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    aziende = ["TA.TA Srl", "GIARDINO DELL'AGLIO SRL", "ANGELO TATA SRL"]
    
    for i, azienda in enumerate(aziende):
        with [col1, col2, col3][i]:
            st.subheader(azienda)
            f_vendite = st.file_uploader(f"Vendite {azienda}", type=['xlsx', 'xls', 'csv'], key=f"v_{i}")
            f_magazzino = st.file_uploader(f"Magazzino {azienda}", type=['xlsx', 'xls', 'csv'], key=f"m_{i}")
            
            if f_vendite:
                df = load_data(f_vendite)
                if df is not None:
                    st.session_state['data_storage'][f"{azienda}_VENDITE"] = pulisci_e_standardizza(df, 'vendite')
                    st.success(f"Vendite OK")
            
            if f_magazzino:
                df = load_data(f_magazzino)
                if df is not None:
                    st.session_state['data_storage'][f"{azienda}_ACQUISTI"] = pulisci_e_standardizza(df, 'acquisti')
                    st.success(f"Magazzino OK")

    st.markdown("---")
    c1, c2, c3, c4 = st.columns(4)
    with c1: usa_periodo_file = st.toggle("Periodo da File Sorgente", value=True)
    with c2: usa_periodo_custom = st.toggle("Periodo Personalizzato")
    with c3: report_cumulativo = st.toggle("Report Cumulativo (All)", value=True)
    with c4: aziende_sel = st.multiselect("Report Parziale:", aziende, default=aziende)

    if usa_periodo_custom and not usa_periodo_file:
        col_date1, col_date2 = st.columns(2)
        start_date = col_date1.date_input("Inizio", datetime(2025, 1, 1))
        end_date = col_date2.date_input("Fine", datetime(2025, 12, 31))
        st.session_state['periodo'] = (start_date, end_date)
    else:
        st.session_state['periodo'] = (datetime(2000, 1, 1), datetime(2100, 12, 31))

    st.session_state['config'] = {'cumulativo': report_cumulativo, 'aziende_target': aziende_sel if not report_cumulativo else aziende}

# --- PAGINA 2: REPORT ---
elif pagina == "2. Elaborazione Report":
    st.markdown('<div class="header-style">ELABORAZIONE REPORT</div>', unsafe_allow_html=True)
    if not st.session_state.get('data_storage'):
        st.warning("Nessun dato caricato.")
    else:
        start_date, end_date = st.session_state['periodo']
        target = st.session_state['config']['aziende_target']
        dfs_elaborati = []
        
        for az in target:
            df_v = st.session_state['data_storage'].get(f"{az}_VENDITE")
            df_a = st.session_state['data_storage'].get(f"{az}_ACQUISTI")
            if df_v is not None or df_a is not None:
                # Blocca try/except per mostrare l'errore pulito all'utente
                try:
                    df_res = elabora_report(df_v, df_a, start_date, end_date, az)
                    if df_res is not None: dfs_elaborati.append(df_res)
                except Exception as e:
                    st.error(f"Errore elaborazione {az}: {e}")

        if dfs_elaborati:
            df_finale = pd.concat(dfs_elaborati, ignore_index=True)
            st.dataframe(df_finale.style.format({
                'FATTURATO_VENDITA': "€ {:,.2f}", 'PREZZO_MEDIO_VENDITA': "€ {:,.2f}",
                'COSTO_MEDIO_ACQUISTO': "€ {:,.2f}", 'MARGINE_1_VALORE': "€ {:,.2f}",
                'MARGINE_PERCENTUALE': "{:.2f}%", 'KG_VENDUTI': "{:,.1f}"
            }), use_container_width=True)
            
            totali = df_finale[['KG_VENDUTI', 'FATTURATO_VENDITA', 'MARGINE_1_VALORE']].sum()
            c1, c2, c3 = st.columns(3)
            c1.metric("Tot KG", f"{totali['KG_VENDUTI']:,.0f}")
            c2.metric("Tot Fatturato", f"€ {totali['FATTURATO_VENDITA']:,.2f}")
            c3.metric("Tot Margine", f"€ {totali['MARGINE_1_VALORE']:,.2f}")

            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df_finale.to_excel(writer, sheet_name='Report', index=False)
            file_name = f"Report_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
            
            st.download_button("💾 SCARICA EXCEL", buffer.getvalue(), file_name, "application/vnd.ms-excel")
            if st.button("SALVA IN ARCHIVIO"):
                with open(os.path.join(SAVE_DIR, file_name), "wb") as f: f.write(buffer.getvalue())
                st.success("Salvato!")
        else:
            st.warning("Impossibile generare il report. Controlla gli errori sopra.")

# --- PAGINE 3 E 4 (INVARIATE, MA INCLUSE PER COMPLETEZZA) ---
elif pagina == "3. Archivio":
    st.markdown('<div class="header-style">ARCHIVIO</div>', unsafe_allow_html=True)
    files = sorted(os.listdir(SAVE_DIR), reverse=True)
    if not files: st.write("Vuoto.")
    for f in files:
        c1, c2, c3 = st.columns([3, 1, 1])
        with c1: st.write(f"📄 {f}")
        with c2:
            with open(os.path.join(SAVE_DIR, f), "rb") as file: st.download_button("Scarica", file, file_name=f)
        with c3:
            if st.button("Analizza", key=f"btn_{f}"):
                st.session_state['file_analisi'] = os.path.join(SAVE_DIR, f)
                st.success("Caricato!")

elif pagina == "4. Grafica & Analisi":
    st.markdown('<div class="header-style">ANALISI</div>', unsafe_allow_html=True)
    if 'file_analisi' in st.session_state:
        df_analysis = pd.read_excel(st.session_state['file_analisi'])
        tipo = st.selectbox("Analisi", ["Performance Origine", "Margini"])
        if tipo == "Performance Origine":
            st.plotly_chart(px.bar(df_analysis, x='ORIGINE', y='FATTURATO_VENDITA', color='AZIENDA', title="Fatturato per Origine", template="simple_white"), use_container_width=True)
        else:
            st.plotly_chart(px.scatter(df_analysis, x='PREZZO_MEDIO_VENDITA', y='MARGINE_PERCENTUALE', size='KG_VENDUTI', color='ORIGINE', title="Margini", template="simple_white"), use_container_width=True)
    else:
        st.info("Seleziona un file dall'Archivio.")

st.markdown("""<div class="footer"><p>TATA-REPORTAPP | Project: R-ADVISOR – M. Ribezzo</p></div>""", unsafe_allow_html=True)
