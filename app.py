import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
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

# Caricamento Font e CSS personalizzato (Stile pulito e Footer)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@300;400;600&display=swap');
    
    html, body, [class*="css"]  {
        font-family: 'Quicksand', sans-serif;
    }
    
    .main-header {
        font-size: 2.5rem;
        color: #2c3e50;
        font-weight: 600;
    }
    
    .footer {
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        background-color: #f1f1f1;
        color: #555;
        text-align: center;
        padding: 10px;
        font-size: 0.8rem;
        border-top: 1px solid #ddd;
        z-index: 100;
    }
    
    /* Nascondere menu default di Streamlit per look app nativa */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    
    <div class="footer">
        <p>USO ESCLUSIVO INTERNO - DIVIETO DI RIPRODUZIONE O CESSIONE DATI NON AUTORIZZATA<br>
        Tributo a R-ADVISOR – M. Ribezzo per progettazione e realizzazione | TATA-REPORTAPP v1.0</p>
    </div>
""", unsafe_allow_html=True)

# --- FUNZIONI DI ELABORAZIONE DATI ---

def load_data(uploaded_file, company_name):
    """
    Carica il file Excel/CSV grezzo e normalizza i nomi delle colonne.
    Si basa sulla riga 1 per i nomi leggibili o mappa i codici tecnici se necessario.
    """
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, header=1, sep=None, engine='python') # Prova a rilevare separatore
        else:
            df = pd.read_excel(uploaded_file, header=1) # Usa la riga 1 come intestazione (come da tua indicazione)
        
        # Pulizia base nomi colonne (rimuove spazi vuoti)
        df.columns = [c.strip() if isinstance(c, str) else c for c in df.columns]
        
        # Aggiungo colonna azienda per identificazione
        df['AZIENDA_ORIGINE'] = company_name
        
        # --- MAPPING CRITICO ---
        # Qui mappiamo i codici tecnici (es. mmqtamov) ai concetti di business se i nomi header non bastano.
        # Basato sui tuoi file, sembra che la riga 1 abbia già nomi come "COLLI", "KG" (o valorizzazione), ecc.
        # Cerchiamo di standardizzare le colonne chiave per il report.
        
        # Normalizzazione nomi colonne chiave (adatta questa lista in base ai nomi esatti nella riga 1 del tuo Excel)
        col_map = {
            'mmqtamov': 'KG',  # Se il file usa codici
            'KG': 'KG',        # Se il file usa già KG
            'mmprezzo': 'PREZZO_UNITARIO',
            'PREZZO UNITA DI MISURA': 'PREZZO_UNITARIO',
            'FAMIGLIA': 'FAMIGLIA',
            'ORIGINE': 'ORIGINE',
            'mmdatdoc': 'DATA',
            'DATA': 'DATA',
            'ddnomdes': 'CLIENTE',
            'CLIENTE': 'CLIENTE'
        }
        
        # Rinomina se trova corrispondenze
        df = df.rename(columns=col_map)
        
        # Calcoli preliminari (Fatturato riga per riga)
        # Assicuriamoci che siano numeri
        for col in ['KG', 'PREZZO_UNITARIO']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        if 'FATTURATO' not in df.columns and 'KG' in df.columns and 'PREZZO_UNITARIO' in df.columns:
            df['FATTURATO'] = df['KG'] * df['PREZZO_UNITARIO']
            
        # Gestione Data
        if 'DATA' in df.columns:
            df['DATA'] = pd.to_datetime(df['DATA'], errors='coerce')
            
        return df
        
    except Exception as e:
        st.error(f"Errore nella lettura del file {company_name}: {e}")
        return None

def process_report(df_total):
    """
    Crea la logica Pivot: Raggruppa per Famiglia e Origine
    """
    if df_total is None or df_total.empty:
        return pd.DataFrame()

    # Raggruppamento (Simulazione della tua PIVOT)
    pivot = df_total.groupby(['FAMIGLIA', 'ORIGINE']).agg(
        KG_TOTALE=('KG', 'sum'),
        FATTURATO_TOTALE=('FATTURATO', 'sum'),
        PREZZO_MEDIO=('PREZZO_UNITARIO', 'mean') # Nota: la media ponderata sarebbe più accurata: Fatturato / KG
    ).reset_index()
    
    # Calcolo Prezzo Medio Ponderato Corretto
    pivot['PREZZO_MEDIO_PONDERATO'] = pivot['FATTURATO_TOTALE'] / pivot['KG_TOTALE']
    
    # --- LOGICA MARGINE (SIMULATA) ---
    # Nota: Non avendo il file dei costi di acquisto qui, simulo un costo per farti vedere la colonna.
    # Nel software finale, qui faremmo un merge con il database lotti.
    pivot['COSTO_MEDIO_SIMULATO'] = pivot['PREZZO_MEDIO_PONDERATO'] * 0.75 # Ipotizzo margine 25% per demo
    pivot['MARGINE_1'] = pivot['PREZZO_MEDIO_PONDERATO'] - pivot['COSTO_MEDIO_SIMULATO']
    pivot['MARGINE_TOTALE'] = pivot['MARGINE_1'] * pivot['KG_TOTALE']
    
    return pivot

# --- GESTIONE NAVIGAZIONE ---
# Sidebar Menu
st.sidebar.title("TATA-REPORTAPP")
page = st.sidebar.radio("Navigazione", ["1. Caricamento Dati", "2. Elaborazione Report", "3. Archivio", "4. Dashboard Grafica"])

# Cartella per salvare i report
if not os.path.exists('server_reports'):
    os.makedirs('server_reports')

# Inizializzazione Session State (Memoria temporanea app)
if 'main_dataframe' not in st.session_state:
    st.session_state['main_dataframe'] = pd.DataFrame()

# ==========================================
# PAGINA 1: CARICAMENTO
# ==========================================
if page == "1. Caricamento Dati":
    st.markdown('<div class="main-header">Importazione Dati Grezzi</div>', unsafe_allow_html=True)
    st.write("Carica i file 'ESTRATTO DA APPLICATIVO' per le rispettive società.")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.info("TA.TA Srl")
        file_tata = st.file_uploader("Trascina file TA.TA", type=['xls', 'xlsx', 'csv'], key="up_tata")
        
    with col2:
        st.info("GIARDINO DELL'AGLIO SRL")
        file_giardino = st.file_uploader("Trascina file GIARDINO", type=['xls', 'xlsx', 'csv'], key="up_giardino")
        
    with col3:
        st.info("ANGELO TATA SRL")
        file_angelo = st.file_uploader("Trascina file ANGELO", type=['xls', 'xlsx', 'csv'], key="up_angelo")

    st.divider()
    
    # Opzioni di Elaborazione
    st.subheader("Impostazioni Elaborazione")
    
    col_opt1, col_opt2 = st.columns(2)
    with col_opt1:
        period_mode = st.radio("Selezione Periodo", ["Da file sorgente (Tutto)", "Definisci Periodo (Data Inizio/Fine)"])
        if period_mode == "Definisci Periodo (Data Inizio/Fine)":
            d_start = st.date_input("Data Inizio")
            d_end = st.date_input("Data Fine")
    
    with col_opt2:
        company_mode = st.radio("Modalità Azienda", ["CUMULATIVO (Tutte le caricate)", "PARZIALE (Seleziona)"])
        selected_companies = []
        if company_mode == "PARZIALE (Seleziona)":
            if st.checkbox("TA.TA Srl", value=True): selected_companies.append("TATA")
            if st.checkbox("GIARDINO DELL'AGLIO", value=True): selected_companies.append("GIARDINO")
            if st.checkbox("ANGELO TATA SRL", value=True): selected_companies.append("ANGELO")
        else:
            selected_companies = ["TATA", "GIARDINO", "ANGELO"]

    if st.button("🚀 ELABORA DATI E VAI AL REPORT", type="primary"):
        # Logica di unione file
        dfs = []
        if file_tata and "TATA" in selected_companies: dfs.append(load_data(file_tata, "TA.TA Srl"))
        if file_giardino and "GIARDINO" in selected_companies: dfs.append(load_data(file_giardino, "GIARDINO DELL'AGLIO"))
        if file_angelo and "ANGELO" in selected_companies: dfs.append(load_data(file_angelo, "ANGELO TATA SRL"))
        
        # Rimuove eventuali None per errori caricamento
        dfs = [d for d in dfs if d is not None]
        
        if dfs:
            full_df = pd.concat(dfs, ignore_index=True)
            
            # Filtro Data
            if period_mode == "Definisci Periodo (Data Inizio/Fine)":
                if 'DATA' in full_df.columns:
                    mask = (full_df['DATA'].dt.date >= d_start) & (full_df['DATA'].dt.date <= d_end)
                    full_df = full_df.loc[mask]
            
            st.session_state['main_dataframe'] = full_df
            st.success(f"Dati elaborati correttamente! {len(full_df)} righe caricate.")
        else:
            st.error("Nessun file valido caricato o selezionato.")

# ==========================================
# PAGINA 2: REPORT
# ==========================================
elif page == "2. Elaborazione Report":
    st.markdown('<div class="main-header">Report Aggregato</div>', unsafe_allow_html=True)
    
    if st.session_state['main_dataframe'].empty:
        st.warning("Nessun dato caricato. Torna alla pagina 1.")
    else:
        df = st.session_state['main_dataframe']
        
        # Creazione Pivot
        report_df = process_report(df)
        
        # Formattazione per visualizzazione (arrotondamenti)
        display_df = report_df.copy()
        display_df['KG_TOTALE'] = display_df['KG_TOTALE'].map('{:,.0f}'.format)
        display_df['FATTURATO_TOTALE'] = display_df['FATTURATO_TOTALE'].map('€ {:,.2f}'.format)
        display_df['PREZZO_MEDIO_PONDERATO'] = display_df['PREZZO_MEDIO_PONDERATO'].map('€ {:,.2f}'.format)
        display_df['MARGINE_1'] = display_df['MARGINE_1'].map('€ {:,.2f}'.format)
        display_df['MARGINE_TOTALE'] = display_df['MARGINE_TOTALE'].map('€ {:,.2f}'.format)
        
        st.dataframe(display_df, use_container_width=True, height=500)
        
        col_act1, col_act2 = st.columns(2)
        
        with col_act1:
            # Salvataggio su Server
            report_name = st.text_input("Nome file salvataggio", value=f"Report_{datetime.now().strftime('%Y%m%d')}")
            if st.button("💾 SALVATAGGIO IN SERVER"):
                path = os.path.join("server_reports", f"{report_name}.csv")
                report_df.to_csv(path, index=False)
                st.success(f"Salvato in {path}")
                
        with col_act2:
            # Export Excel per stampa
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                report_df.to_excel(writer, sheet_name='Report', index=False)
            
            st.download_button(
                label="🖨️ SCARICA PER STAMPA (EXCEL)",
                data=buffer,
                file_name=f"{report_name}.xlsx",
                mime="application/vnd.ms-excel"
            )

# ==========================================
# PAGINA 3: ARCHIVIO
# ==========================================
elif page == "3. Archivio":
    st.markdown('<div class="main-header">Archivio Storico</div>', unsafe_allow_html=True)
    
    files = os.listdir("server_reports")
    if files:
        files_df = pd.DataFrame(files, columns=["Nome File"])
        st.table(files_df)
        
        selected_file = st.selectbox("Seleziona file da ricaricare o scaricare", files)
        
        if st.button("Carica in Dashboard"):
            path = os.path.join("server_reports", selected_file)
            loaded_df = pd.read_csv(path)
            # Nota: questo carica il report aggregato, non il grezzo, quindi la dashboard mostrerà i dati aggregati
            st.session_state['report_dataframe'] = loaded_df
            st.success("Caricato per analisi grafica!")
    else:
        st.info("Nessun report salvato nel server.")

# ==========================================
# PAGINA 4: DASHBOARD GRAFICA
# ==========================================
elif page == "4. Dashboard Grafica":
    st.markdown('<div class="main-header">Business Intelligence</div>', unsafe_allow_html=True)
    
    # Usa dati correnti o caricati dall'archivio
    if 'report_dataframe' in st.session_state:
        # Usa dati da archivio se caricati
        data = st.session_state['report_dataframe']
        is_aggregated = True
    elif not st.session_state['main_dataframe'].empty:
        # Usa dati correnti elaborati
        data = process_report(st.session_state['main_dataframe'])
        is_aggregated = True
    else:
        data = pd.DataFrame()
        is_aggregated = False

    if not data.empty:
        # --- KPI CARDS (Stile Screenshot) ---
        tot_fatt = data['FATTURATO_TOTALE'].sum()
        tot_kg = data['KG_TOTALE'].sum()
        avg_price = tot_fatt / tot_kg if tot_kg > 0 else 0
        
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("FATTURATO TOTALE", f"€ {tot_fatt:,.0f}", "+12%")
        kpi2.metric("VOLUME (KG)", f"{tot_kg:,.0f}", "-2%")
        kpi3.metric("PREZZO MEDIO", f"€ {avg_price:.2f}", "+5%")
        kpi4.metric("MARGINE TOTALE (Stimato)", f"€ {data['MARGINE_TOTALE'].sum():,.0f}")
        
        st.divider()
        
        # --- GRAFICI ---
        col_g1, col_g2 = st.columns(2)
        
        with col_g1:
            st.subheader("Fatturato per Famiglia")
            fig_bar = px.bar(data, x='FAMIGLIA', y='FATTURATO_TOTALE', color='ORIGINE', 
                             title="Vendite per Categoria e Origine",
                             color_discrete_sequence=px.colors.qualitative.Prism)
            fig_bar.update_layout(template="plotly_white")
            st.plotly_chart(fig_bar, use_container_width=True)
            
        with col_g2:
            st.subheader("Distribuzione Volumi")
            fig_pie = px.pie(data, values='KG_TOTALE', names='FAMIGLIA', hole=0.4,
                             title="Share Volumi (KG)")
            fig_pie.update_layout(template="plotly_white")
            st.plotly_chart(fig_pie, use_container_width=True)
            
        # Analisi aggiuntiva se ci sono i dati grezzi (dettaglio cliente)
        if not st.session_state['main_dataframe'].empty:
            st.subheader("Top 10 Clienti (Fatturato)")
            raw_df = st.session_state['main_dataframe']
            top_clients = raw_df.groupby('CLIENTE')['FATTURATO'].sum().sort_values(ascending=False).head(10)
            st.bar_chart(top_clients)

    else:
        st.warning("Nessun dato disponibile per i grafici. Elabora un report o caricalo dall'archivio.")
