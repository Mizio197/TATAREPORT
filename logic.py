import pandas as pd

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
    
    try:
        if tipo == "VENDITE":
            # I tuoi file vendite hanno una riga descrittiva in alto aggiunta da te.
            # I codici tecnici (mmcodcon) sono nella riga 2 (index 1).
            df = pd.read_csv(file, header=1, sep=None, engine='python')
            
            # Rinomina
            df = df.rename(columns=MAPPA_VENDITE)
            
            # Pulizia colonne numeriche
            cols_num = ['KG', 'FATTURATO']
            for c in cols_num:
                if c in df.columns:
                    df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
            
            # Aggiunge colonna fittizia per esempio se manca
            if 'DATA' not in df.columns and 'mmdatdoc' not in df.columns:
                 df['DATA'] = pd.to_datetime('today') # Fallback se non trova data
                 
            return df
            
        elif tipo == "MAGAZZINO":
            # Il file magazzino sembra avere l'header alla riga 1 (index 0)
            if file.name.endswith('.csv'):
                df = pd.read_csv(file, sep=None, engine='python')
            else:
                df = pd.read_excel(file)
                
            df = df.rename(columns=MAPPA_MAGAZZINO)
            
            # Calcolo costo medio rapido
            if 'KG_ACQ' in df.columns and 'COSTO_TOT' in df.columns:
                df['KG_ACQ'] = pd.to_numeric(df['KG_ACQ'], errors='coerce').fillna(0)
                df['COSTO_TOT'] = pd.to_numeric(df['COSTO_TOT'], errors='coerce').fillna(0)
                # Evita divisione per zero
                df = df[df['KG_ACQ'] > 0]
                df['COSTO_MEDIO'] = df['COSTO_TOT'] / df['KG_ACQ']
            
            return df
            
    except Exception as e:
        return str(e) # Ritorna l'errore se c'è
