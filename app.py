import streamlit as st
import pandas as pd
import plotly.express as px
from logic import load_data

# Configurazione Pagina
st.set_page_config(page_title="TATA REPORT", layout="wide")

# Stile CSS (Font Quicksand e pulizia)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@400;600&display=swap');
    html, body, [class*="css"] { font-family: 'Quicksand', sans-serif; }
    .stButton>button { width: 100%; border-radius: 5px; background-color: #2c3e50; color: white;}
    </style>
""", unsafe_allow_html=True)

st.title("📊 TATA-REPORTAPP")

# --- SIDEBAR (Opzioni) ---
with st.sidebar:
    st.header("Impostazioni")
    page = st.radio("Navigazione", ["Caricamento Dati", "Report", "Grafici"])

# --- SESSION STATE (Memoria temporanea) ---
if 'df_vendite' not in st.session_state: st.session_state['df_vendite'] = pd.DataFrame()
if 'df_mag' not in st.session_state: st.session_state['df_mag'] = pd.DataFrame()

# --- PAGINA 1: CARICAMENTO ---
if page == "Caricamento Dati":
    st.subheader("1. Importazione File Gestionali")
    
    col1, col2 = st.columns(2)
    with col1:
        st.info("📂 File VENDITE (Estratto da Applicativo)")
        f_vend = st.file_uploader("Trascina qui i file Vendite (CSV/XLS)", accept_multiple_files=True)
    
    with col2:
        st.warning("📦 File MAGAZZINO")
        f_mag = st.file_uploader("Trascina qui i file Magazzino", accept_multiple_files=True)

    if st.button("ELABORA DATI"):
        if f_vend:
            all_v = []
            for f in f_vend:
                # Qui potremmo identificare l'azienda dal nome file
                d = load_data(f, "VENDITE")
                if isinstance(d, pd.DataFrame):
                    d['FILENAME'] = f.name # Utile per capire l'azienda
                    all_v.append(d)
                else:
                    st.error(f"Errore su file {f.name}: {d}")
            
            if all_v:
                st.session_state['df_vendite'] = pd.concat(all_v, ignore_index=True)
                st.success(f"Caricate {len(st.session_state['df_vendite'])} righe vendite!")

        if f_mag:
            all_m = []
            for f in f_mag:
                d = load_data(f, "MAGAZZINO")
                if isinstance(d, pd.DataFrame):
                    all_m.append(d)
            if all_m:
                st.session_state['df_mag'] = pd.concat(all_m, ignore_index=True)
                st.success(f"Caricate {len(st.session_state['df_mag'])} righe magazzino!")

# --- PAGINA 2: REPORT ---
elif page == "Report":
    st.subheader("2. Report Aggregato")
    
    df = st.session_state['df_vendite']
    if df.empty:
        st.error("Carica prima i dati nella sezione 'Caricamento Dati'")
    else:
        # Filtri
        col1, col2, col3 = st.columns(3)
        with col1:
            clienti = st.multiselect("Filtra Cliente", df['CLIENTE'].unique())
        
        # Filtra DF
        if clienti: df = df[df['CLIENTE'].isin(clienti)]
        
        # PIVOT TABLE
        st.write("### Pivot Vendite per Famiglia")
        pivot = df.pivot_table(
            index=["CLIENTE", "FAMIGLIA"], 
            values=["KG", "FATTURATO"], 
            aggfunc="sum"
        ).reset_index()
        
        # Calcolo Prezzo Medio
        pivot['PREZZO_MEDIO'] = pivot['FATTURATO'] / pivot['KG']
        
        st.dataframe(pivot, use_container_width=True)
        
        # Esempio Export
        buffer = pd.ExcelWriter("Report_TATA.xlsx", engine='xlsxwriter')
        pivot.to_excel(buffer, index=False, sheet_name='Report')
        # ... qui mancherebbe il save effettivo, ma streamlite lo fa col pulsante sotto:
        
        # st.download_button non supporta direttamente l'oggetto writer complesso in modo semplice
        # ma per CSV è immediato:
        csv = pivot.to_csv(index=False).encode('utf-8')
        st.download_button("SCARICA CSV", csv, "report.csv", "text/csv")

# --- PAGINA 3: GRAFICI ---
elif page == "Grafici":
    st.subheader("3. Analisi Visiva")
    df = st.session_state['df_vendite']
    if not df.empty:
        # Grafico a torta Famiglie
        fig = px.pie(df, values='KG', names='FAMIGLIA', title='Distribuzione Vendite (KG) per Famiglia')
        st.plotly_chart(fig, use_container_width=True)
        
        # Istogramma Clienti
        fig2 = px.bar(df.groupby('CLIENTE')['FATTURATO'].sum().reset_index(), 
                      x='CLIENTE', y='FATTURATO', title='Top Clienti per Fatturato')
        st.plotly_chart(fig2, use_container_width=True)
