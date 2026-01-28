import pandas as pd
import io

# Mappa basata sui tuoi file "ESTRATTO DA APPLICATIVO" e "MAGAZZINO"
MAPPA_VENDITE = {
    'mmcodcon': 'CLIENTE_COD',
    'andescri': 'CLIENTE',
    'mvcoddes': 'ARTICOLO_COD',
    'ardesart': 'ARTICOLO',
    'arcodfam': 'FAMIGLIA',
    'argrumer': 'PRODOTTO_TIPO', # Bio/Conv
    'mmtcamag': 'ORIGINE', 
    'mmdatdoc': 'DATA',
    'qtano': 'KG',            # Ho visto che usi qtano per i KG
    'vacaoval': 'FATTURATO'   # Valore riga
}

MAPPA_MAGAZZINO = {
    'ORIGINE': 'ORIGINE',
    'CAT': 'CATEGORIA',
    'TIP': 'TIPO',
    'KG ACQUISTATI': 'KG_ACQ',
    'COSTO TOTALE ACQUISTO': 'COSTO_TOT'
}

def load_data(file, tipo="VENDITE"):
    if file is None: return None
    
    df = None
    
    try:
        # --- LOGICA PER VENDITE ---
        if tipo == "VENDITE":
            # Strategia 1: Prova a leggere come EXCEL vero (risolve l'errore 0xd0)
            try:
                df = pd.read_excel(file, header=1)
            except:
                # Se fallisce, resetta il file e prova come CSV (testo)
                file.seek(0)
                # 'latin1' è più permissivo di 'utf-8' per i file gestionali vecchi
                df = pd.read_csv(file, header=1, sep=None, engine='python', encoding='latin1')
            
            # Rinomina colonne
            df = df.rename(columns=MAPPA_VENDITE)
            
            # Pulizia colonne numeriche
            cols_num = ['KG', 'FATTURATO']
            for c in cols_num:
                if c in df.columns:
                    df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
            
            # Gestione Data mancante
            if 'DATA' not in df.columns and 'mmdatdoc' not in df.columns:
                 df['DATA'] = pd.to_datetime('today')

        # --- LOGICA PER MAGAZZINO ---
        elif tipo == "MAGAZZINO":
            # Strategia: Prova Excel, poi CSV
            try:
                df = pd.read_excel(file)
            except:
                file.seek(0)
                df = pd.read_csv(file, sep=None, engine='python', encoding='latin1')
                
            df = df.rename(columns=MAPPA_MAGAZZINO)
            
            # Calcolo costo medio
            if 'KG_ACQ' in df.columns and 'COSTO_TOT' in df.columns:
                df['KG_ACQ'] = pd.to_numeric(df['KG_ACQ'], errors='coerce').fillna(0)
                df['COSTO_TOT'] = pd.to_numeric(df['COSTO_TOT'], errors='coerce').fillna(0)
                # Evita divisione per zero
                mask = df['KG_ACQ'] > 0
                df.loc[mask, 'COSTO_MEDIO'] = df.loc[mask, 'COSTO_TOT'] / df.loc[mask, 'KG_ACQ']
            
    except Exception as e:
        return f"Errore critico lettura file: {str(e)}"

    return df
