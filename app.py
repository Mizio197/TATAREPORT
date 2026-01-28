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

# Definizione dei Font e dello stile per la stampa e l'interfaccia
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@300;400;500;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Quicksand', sans-serif;
    }
    
    /* Stile per l'intestazione */
    .header-style {
        font-size: 24px;
        font-weight: bold;
        color: #2c3e50;
        border-bottom: 2px solid #2c3e50;
        padding-bottom: 10px;
        margin-bottom: 20px;
    }
    
    /* Nascondi elementi non necessari in stampa */
    @media print {
        div[data-testid="stSidebar"] {display: none;}
        .stButton {display: none;}
        div[data-testid="stDecoration"] {display: none;}
        footer {display: none;}
        #archivio-footer {display: block !important; position: fixed; bottom: 0; width: 100%; text-align: center; font-size: 10px; color: grey;}
    }
    
    /* Footer personalizzato */
    .footer {
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        background-color: white;
        color: grey;
        text-align: center;
        padding: 10px;
        border-top: 1px solid #eaeaea;
        font-size: 12px;
    }
    </style>
""", unsafe_allow_html=True)

# --- FUNZIONI DI ELABORAZIONE DATI (LOGICA BUSINESS) ---

def load_data(file):
    """Carica CSV o Excel e gestisce errori."""
    if file is None:
        return None
    try:
        if file.name.endswith('.csv'):
            # Prova diversi separatori comuni nei CSV italiani
            try:
                df = pd.read_csv(file, sep=';', encoding='latin1') # Tipico formato italiano
            except:
                file.seek(0)
                df = pd.read_csv(file, sep=',', encoding='utf-8')
        else:
            df = pd.read_excel(file)
        return df
    except Exception as e:
        st.error(f"Errore nel caricamento del file {file.name}: {e}")
        return None

def pulisci_e_standardizza(df, tipo):
    """
    Normalizza i nomi delle colonne basandosi sui file 'FOCUS' forniti.
    tipo: 'vendite' o 'acquisti'
    """
    if df is None:
        return None
    
    # Mappa colonne basata sui tuoi file CSV
    # Normalizziamo in maiuscolo per evitare errori di case-sensitivity
    df.columns = [c.strip().upper() for c in df.columns]
    
    # Converti colonne data
    cols_data = [c for c in df.columns if 'DATA' in c]
    for c in cols_data:
        df[c] = pd.to_datetime(df[c], errors='coerce')
        
    return df

def elabora_report(df_vendite, df_acquisti, data_inizio, data_fine, azienda):
    """
    Logica CORE: replica il foglio 'REPORT acq vend mese'.
    1. Filtra per data.
    2. Raggruppa Vendite per ORIGINE (o famiglia/articolo).
    3. Raggruppa Acquisti per ORIGINE per trovare il costo medio.
    4. Unisce i dati e calcola i margini.
    """
    
    # 1. Filtro Data
    if df_vendite is not None:
        col_data_v = next((c for c in df_vendite.columns if 'DATA' in c), None)
        if col_data_v:
            df_vendite = df_vendite[(df_vendite[col_data_v] >= pd.to_datetime(data_inizio)) & 
                                    (df_vendite[col_data_v] <= pd.to_datetime(data_fine))]

    if df_acquisti is not None:
        col_data_a = next((c for c in df_acquisti.columns if 'DATA' in c), None)
        if col_data_a:
            df_acquisti = df_acquisti[(df_acquisti[col_data_a] >= pd.to_datetime(data_inizio)) & 
                                      (df_acquisti[col_data_a] <= pd.to_datetime(data_fine))]

    # Se non abbiamo dati dopo il filtro
    if (df_vendite is None or df_vendite.empty) and (df_acquisti is None or df_acquisti.empty):
        return None

    risultati = []

    # --- LOGICA PIVOT: Raggruppamento per ORIGINE ---
    # Cerchiamo la colonna ORIGINE
    col_origine_v = 'ORIGINE' if 'ORIGINE' in df_vendite.columns else df_vendite.columns[0]
    
    # A. Aggregazione VENDITE
    if df_vendite is not None and not df_vendite.empty:
        # Cerchiamo colonne KG e FATTURATO
        col_kg_v = next((c for c in df_vendite.columns if 'KG' in c and 'PREZZO' not in c), 'KG')
        col_fatt_v = next((c for c in df_vendite.columns if 'FATTURATO' in c or 'IMPORTO' in c), 'FATTURATO')
        
        # Assicuriamoci che siano numerici
        df_vendite[col_kg_v] = pd.to_numeric(df_vendite[col_kg_v], errors='coerce').fillna(0)
        df_vendite[col_fatt_v] = pd.to_numeric(df_vendite[col_fatt_v], errors='coerce').fillna(0)
        
        pivot_vendite = df_vendite.groupby(col_origine_v).agg({
            col_kg_v: 'sum',
            col_fatt_v: 'sum'
        }).reset_index()
        pivot_vendite.rename(columns={col_kg_v: 'KG_VENDUTI', col_fatt_v: 'FATTURATO_VENDITA'}, inplace=True)
        pivot_vendite['PREZZO_MEDIO_VENDITA'] = pivot_vendite['FATTURATO_VENDITA'] / pivot_vendite['KG_VENDUTI']
    else:
        pivot_vendite = pd.DataFrame(columns=[col_origine_v, 'KG_VENDUTI', 'FATTURATO_VENDITA', 'PREZZO_MEDIO_VENDITA'])

    # B. Aggregazione ACQUISTI (per calcolare il Costo Medio)
    if df_acquisti is not None and not df_acquisti.empty:
        col_origine_a = 'ORIGINE' if 'ORIGINE' in df_acquisti.columns else df_acquisti.columns[0]
        col_kg_a = next((c for c in df_acquisti.columns if 'KG' in c and 'COSTO' not in c), 'KG ACQUISTATI')
        col_costo_a = next((c for c in df_acquisti.columns if 'COSTO' in c or 'TOTALE' in c), 'COSTO TOTALE')

        df_acquisti[col_kg_a] = pd.to_numeric(df_acquisti[col_kg_a], errors='coerce').fillna(0)
        df_acquisti[col_costo_a] = pd.to_numeric(df_acquisti[col_costo_a], errors='coerce').fillna(0)

        pivot_acquisti = df_acquisti.groupby(col_origine_a).agg({
            col_kg_a: 'sum',
            col_costo_a: 'sum'
        }).reset_index()
        # Calcolo Costo Medio Ponderato per origine
        pivot_acquisti['COSTO_MEDIO_ACQUISTO'] = pivot_acquisti[col_costo_a] / pivot_acquisti[col_kg_a]
        pivot_acquisti = pivot_acquisti[[col_origine_a, 'COSTO_MEDIO_ACQUISTO', col_kg_a, col_costo_a]]
    else:
        pivot_acquisti = pd.DataFrame(columns=['ORIGINE', 'COSTO_MEDIO_ACQUISTO', 'KG_ACQUISTATI', 'COSTO_TOTALE'])

    # C. MERGE (Unione Logica)
    # Uniamo Vendite e Costi basandoci sull'ORIGINE
    if not pivot_vendite.empty:
        report_finale = pd.merge(pivot_vendite, pivot_acquisti, left_on=col_origine_v, right_on='ORIGINE', how='left')
        
        # Gestione NaN (se vendiamo qualcosa che non abbiamo comprato nel periodo, o viceversa)
        report_finale['COSTO_MEDIO_ACQUISTO'] = report_finale['COSTO_MEDIO_ACQUISTO'].fillna(0)
        
        # D. Calcoli Finali (Margini come da file REPORT)
        # MARGINE 1 = (Prezzo Medio Vendita - Costo Medio Acquisto) * KG Venduti
        report_finale['COSTO_VENDUTO_TEORICO'] = report_finale['KG_VENDUTI'] * report_finale['COSTO_MEDIO_ACQUISTO']
        report_finale['MARGINE_1_VALORE'] = report_finale['FATTURATO_VENDITA'] - report_finale['COSTO_VENDUTO_TEORICO']
        report_finale['MARGINE_PERCENTUALE'] = (report_finale['MARGINE_1_VALORE'] / report_finale['FATTURATO_VENDITA']) * 100
        
        report_finale['AZIENDA'] = azienda
        return report_finale
    else:
        return None

# --- UI: SIDEBAR DI NAVIGAZIONE ---
st.sidebar.title("NAVIGAZIONE")
pagina = st.sidebar.radio("Vai a:", ["1. Input Dati", "2. Elaborazione Report", "3. Archivio", "4. Grafica & Analisi"])

# Cartella di salvataggio
SAVE_DIR = "archivio_report"
if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)

# Inizializzazione Session State per passare dati tra pagine
if 'data_storage' not in st.session_state:
    st.session_state['data_storage'] = {}

# --- PAGINA 1: INPUT DATI ---
if pagina == "1. Input Dati":
    st.markdown('<div class="header-style">INSERIMENTO DATI GREZZI</div>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    files_input = {}
    
    # Definizione delle 3 Aziende
    aziende = ["TA.TA Srl", "GIARDINO DELL'AGLIO SRL", "ANGELO TATA SRL"]
    cols = [col1, col2, col3]
    
    for i, azienda in enumerate(aziende):
        with cols[i]:
            st.subheader(azienda)
            st.info("Area Drag & Drop")
            f_vendite = st.file_uploader(f"Vendite {azienda}", type=['xlsx', 'csv'], key=f"v_{i}")
            f_magazzino = st.file_uploader(f"Magazzino {azienda}", type=['xlsx', 'csv'], key=f"m_{i}")
            
            if f_vendite:
                df = load_data(f_vendite)
                if df is not None:
                    st.session_state['data_storage'][f"{azienda}_VENDITE"] = pulisci_e_standardizza(df, 'vendite')
                    st.success(f"Vendite {azienda} caricato!")
            
            if f_magazzino:
                df = load_data(f_magazzino)
                if df is not None:
                    st.session_state['data_storage'][f"{azienda}_ACQUISTI"] = pulisci_e_standardizza(df, 'acquisti')
                    st.success(f"Magazzino {azienda} caricato!")

    st.markdown("---")
    st.subheader("Impostazioni di Elaborazione")
    
    # Controlli a Slitta (Toggle)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        usa_periodo_file = st.toggle("Periodo da File Sorgente", value=True)
    with c2:
        usa_periodo_custom = st.toggle("Periodo Personalizzato")
    with c3:
        report_cumulativo = st.toggle("Report Cumulativo (All)", value=True)
    with c4:
        aziende_sel = st.multiselect("Report Parziale per:", aziende, default=aziende)

    # Date Range Picker
    if usa_periodo_custom and not usa_periodo_file:
        col_date1, col_date2 = st.columns(2)
        start_date = col_date1.date_input("Data Inizio", datetime(2025, 1, 1))
        end_date = col_date2.date_input("Data Fine", datetime(2025, 12, 31))
        st.session_state['periodo'] = (start_date, end_date)
    else:
        # Default ampio se si usa il file sorgente (verrà filtrato implicitamente dai dati presenti)
        st.session_state['periodo'] = (datetime(2000, 1, 1), datetime(2100, 12, 31))

    st.session_state['config'] = {
        'cumulativo': report_cumulativo,
        'aziende_target': aziende_sel if not report_cumulativo else aziende
    }

# --- PAGINA 2: ELABORAZIONE REPORT ---
elif pagina == "2. Elaborazione Report":
    st.markdown('<div class="header-style">TATA-REPORTAPP - ELABORAZIONE</div>', unsafe_allow_html=True)
    
    if not st.session_state.get('data_storage'):
        st.warning("Nessun dato caricato. Torna alla Pagina 1.")
    else:
        start_date, end_date = st.session_state['periodo']
        target_aziende = st.session_state['config']['aziende_target']
        
        dfs_elaborati = []
        
        for azienda in target_aziende:
            df_v = st.session_state['data_storage'].get(f"{azienda}_VENDITE")
            df_a = st.session_state['data_storage'].get(f"{azienda}_ACQUISTI")
            
            if df_v is not None or df_a is not None:
                df_res = elabora_report(df_v, df_a, start_date, end_date, azienda)
                if df_res is not None:
                    dfs_elaborati.append(df_res)
        
        if dfs_elaborati:
            df_finale = pd.concat(dfs_elaborati, ignore_index=True)
            
            # Formattazione per visualizzazione
            st.dataframe(df_finale.style.format({
                'FATTURATO_VENDITA': "€ {:,.2f}",
                'PREZZO_MEDIO_VENDITA': "€ {:,.2f}",
                'COSTO_MEDIO_ACQUISTO': "€ {:,.2f}",
                'MARGINE_1_VALORE': "€ {:,.2f}",
                'MARGINE_PERCENTUALE': "{:.2f}%",
                'KG_VENDUTI': "{:,.1f}"
            }), use_container_width=True)
            
            # Totali Generali (Riga Somma)
            st.subheader("Totali Generali")
            totali = df_finale[['KG_VENDUTI', 'FATTURATO_VENDITA', 'MARGINE_1_VALORE']].sum()
            col_met1, col_met2, col_met3 = st.columns(3)
            col_met1.metric("Totale KG", f"{totali['KG_VENDUTI']:,.0f}")
            col_met2.metric("Totale Fatturato", f"€ {totali['FATTURATO_VENDITA']:,.2f}")
            col_met3.metric("Totale Margine", f"€ {totali['MARGINE_1_VALORE']:,.2f}")

            # Salvataggio
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df_finale.to_excel(writer, sheet_name='Report', index=False)
            
            file_name = f"Report_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
            
            c_save1, c_save2 = st.columns(2)
            with c_save1:
                st.download_button(
                    label="💾 SCARICA FILE EXCEL",
                    data=buffer.getvalue(),
                    file_name=file_name,
                    mime="application/vnd.ms-excel"
                )
            with c_save2:
                if st.button("SALVA IN ARCHIVIO SERVER"):
                    with open(os.path.join(SAVE_DIR, file_name), "wb") as f:
                        f.write(buffer.getvalue())
                    st.success(f"Salvato in {SAVE_DIR}/{file_name}")

        else:
            st.info("Nessun dato trovato per il periodo selezionato.")

# --- PAGINA 3: ARCHIVIO ---
elif pagina == "3. Archivio":
    st.markdown('<div class="header-style">ARCHIVIO STORICO REPORT</div>', unsafe_allow_html=True)
    
    files = sorted(os.listdir(SAVE_DIR), reverse=True)
    if not files:
        st.write("L'archivio è vuoto.")
    else:
        for f in files:
            col_f1, col_f2, col_f3 = st.columns([3, 1, 1])
            with col_f1:
                st.write(f"📄 {f}")
            with col_f2:
                file_path = os.path.join(SAVE_DIR, f)
                with open(file_path, "rb") as file:
                    st.download_button("Scarica", file, file_name=f)
            with col_f3:
                # Opzione per caricare questo file in Pagina 4 per analisi
                if st.button("Analizza", key=f"btn_{f}"):
                    st.session_state['file_analisi'] = file_path
                    st.success("Caricato per analisi in Pagina 4")

# --- PAGINA 4: GRAFICA E ANALISI ---
elif pagina == "4. Grafica & Analisi":
    st.markdown('<div class="header-style">ANALISI DATI COMPARATA</div>', unsafe_allow_html=True)
    
    # Caricamento Dati
    df_analysis = None
    if 'file_analisi' in st.session_state:
        st.info(f"Analizzando il file: {os.path.basename(st.session_state['file_analisi'])}")
        df_analysis = pd.read_excel(st.session_state['file_analisi'])
    else:
        st.info("Seleziona un file dall'Archivio (Pagina 3) oppure usa i dati elaborati correnti.")
    
    if df_analysis is not None:
        # Griglia di Scelta Analisi
        tipo_analisi = st.selectbox("Seleziona Tipo Analisi", 
                     ["Performance per Origine", "Performance per Azienda", "Analisi Margini"])
        
        col_chart1, col_chart2 = st.columns(2)
        
        if tipo_analisi == "Performance per Origine":
            fig1 = px.bar(df_analysis, x='ORIGINE', y='FATTURATO_VENDITA', color='AZIENDA', 
                          title="Fatturato per Origine", template="simple_white",
                          color_discrete_sequence=px.colors.qualitative.Pastel)
            col_chart1.plotly_chart(fig1, use_container_width=True)
            
            fig2 = px.pie(df_analysis, names='ORIGINE', values='KG_VENDUTI', 
                          title="Ripartizione Volumi (KG)", template="simple_white",
                          color_discrete_sequence=px.colors.qualitative.Pastel)
            col_chart2.plotly_chart(fig2, use_container_width=True)

        elif tipo_analisi == "Performance per Azienda":
            fig1 = px.bar(df_analysis, x='AZIENDA', y=['FATTURATO_VENDITA', 'MARGINE_1_VALORE'], 
                          barmode='group', title="Confronto Fatturato vs Margine",
                          template="simple_white", color_discrete_sequence=['#4a90e2', '#50e3c2'])
            st.plotly_chart(fig1, use_container_width=True)

        elif tipo_analisi == "Analisi Margini":
            fig1 = px.scatter(df_analysis, x='PREZZO_MEDIO_VENDITA', y='MARGINE_PERCENTUALE', 
                              size='KG_VENDUTI', color='ORIGINE', hover_name='ORIGINE',
                              title="Elasticità Prezzo / Margine (Dimensione bolla = Volumi)",
                              template="simple_white")
            st.plotly_chart(fig1, use_container_width=True)

# --- FOOTER ---
st.markdown("""
    <div class="footer">
        <p>TATA-REPORTAPP | Utilizzo esclusivo interno - Vietata la riproduzione.</p>
        <p>Project: R-ADVISOR – M. Ribezzo</p>
    </div>
""", unsafe_allow_html=True)
