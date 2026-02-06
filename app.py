import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import os

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(
    page_title="Gestionale Fatture (Cloud)", 
    page_icon="☁️", 
    layout="wide"
)

# --- CONFIGURAZIONE GOOGLE SHEETS ---
SHEET_NAME = "gestionale_db" 
SCOPE = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']

# --- COLONNE ---
COLONNE = [
    "Cliente", "N. Fattura", "Data Fatt.", 
    "Importo Fatt. (€)", "Importo Pagato (€)", 
    "Saldo (€)", "Stato", "Data Saldo"
]

# --- FUNZIONE INTELLIGENTE PER I NUMERI (FIX VIRGOLE/PUNTI) ---
def pulisci_numero(valore):
    """
    Converte stringhe in numeri gestendo sia il formato 1.000,00 che 1000.00
    """
    if pd.isna(valore) or str(valore).strip() == "":
        return 0.0
    
    s = str(valore).replace("€", "").strip()
    
    try:
        # CASO 1: Formato Italiano complesso (1.000,50) -> Punto=Migliaia, Virgola=Decimali
        if "." in s and "," in s and s.find(".") < s.find(","):
            s = s.replace(".", "") # Via i punti delle migliaia
            s = s.replace(",", ".") # La virgola diventa punto per Python
            
        # CASO 2: Formato Americano complesso (1,000.50) -> Virgola=Migliaia, Punto=Decimali
        elif "." in s and "," in s and s.find(",") < s.find("."):
            s = s.replace(",", "") # Via le virgole delle migliaia
            
        # CASO 3: Solo virgola (400,50) -> Diventa 400.50
        elif "," in s:
            s = s.replace(",", ".")
            
        # CASO 4: Solo punto (400.50) -> Resta così com'è (NON LO RIMUOVIAMO PIÙ)
        
        return float(s)
    except:
        return 0.0

# --- CONNESSIONE GOOGLE ---
def connect_google():
    try:
        if "gcp_service_account" not in st.secrets:
            st.error("Mancano le chiavi segrete (Secrets)!")
            st.stop()
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
        client = gspread.authorize(creds)
        sheet = client.open(SHEET_NAME).sheet1
        return sheet
    except Exception as e:
        st.error(f"Errore connessione Google: {e}")
        st.stop()

# --- CARICAMENTO DATI ---
def load_data():
    sheet = connect_google()
    try:
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        if df.empty: return pd.DataFrame(columns=COLONNE)

        for col in COLONNE:
            if col not in df.columns: df[col] = ""

        # Usa la nuova funzione pulisci_numero
        cols_num = ["Importo Fatt. (€)", "Importo Pagato (€)", "Saldo (€)"]
        for col in cols_num:
            df[col] = df[col].apply(pulisci_numero)
            
        return df[COLONNE]
    except Exception as e:
        return pd.DataFrame(columns=COLONNE)

# --- SALVATAGGIO DATI ---
def save_data(df):
    sheet = connect_google()
    try:
        sheet.clear() 
        # Convertiamo tutto in stringa per Google Sheets
        dati_lista = [df.columns.values.tolist()] + df.astype(str).values.tolist()
        sheet.update(dati_lista)
    except Exception as e:
        st.error(f"Errore salvataggio Cloud: {e}")

# --- CALCOLI ---
def calcola_stato_saldo(row):
    # Usa la funzione pulisci_numero anche qui per sicurezza
    importo = pulisci_numero(row["Importo Fatt. (€)"])
    pagato = pulisci_numero(row["Importo Pagato (€)"])
    saldo = importo - pagato
    
    stato = "Non Pagata"
    data_saldo = row["Data Saldo"]
    
    if saldo <= 0.01:
        saldo = 0
        stato = "Pagata"
        if pd.isna(data_saldo) or str(data_saldo).strip() in ["", "nan", "None"]:
            data_saldo = datetime.today().strftime("%d/%m/%Y")
    elif pagato > 0:
        stato = "Parziale"
        
    return saldo, stato, data_saldo

# --- FUNZIONI CSV ---
def clean_column_names_csv(df):
    new_columns = []
    for col in df.columns:
        col = col.replace('ï»¿', '').replace('ïbb¿', '')
        col = col.replace('â\x82¬', '€').replace('â¬', '€').replace('ð', '€')
        new_columns.append(col.strip())
    df.columns = new_columns
    return df

def try_read_csv_upload(file_source):
    separators = [';', ',']
    encodings = ['ISO-8859-1', 'utf-8-sig', 'cp1252']
    for sep in separators:
        for enc in encodings:
            try:
                if hasattr(file_source, 'seek'): file_source.seek(0)
                df = pd.read_csv(file_source, sep=sep, encoding=enc)
                df = clean_column_names_csv(df)
                if len(df.columns) > 1 and "Cliente" in df.columns: return df
            except: continue
    return pd.DataFrame()

# --- INTERFACCIA ---
with st.sidebar:
    if os.path.exists("logo.png"): st.image("logo.png", width=250)
    elif os.path.exists("logo.jpg"): st.image("logo.jpg", width=250)
    
    st.title("Menu")
    scelta = st.radio("Vai a:", ["Dashboard & Analisi", "Inserisci Fattura", "Gestione Tabella", "Importa CSV"])
    st.markdown("---")
    st.success("🟢 Connesso a Google Sheets")

df = load_data()

# 1. DASHBOARD
if scelta == "Dashboard & Analisi":
    st.title("📊 Dashboard Cloud")
    if not df.empty:
        c1, c2, c3 = st.columns(3)
        tot_fatt = df["Importo Fatt. (€)"].sum()
        tot_pag = df["Importo Pagato (€)"].sum()
        tot_saldo = df["Saldo (€)"].sum()
        
        c1.metric("Totale Fatturato", f"€ {tot_fatt:,.2f}")
        c2.metric("Incassato", f"€ {tot_pag:,.2f}")
        c3.metric("DA INCASSARE", f"€ {tot_saldo:,.2f}", delta_color="inverse")
        
        st.markdown("---")
        st.header("👤 Analisi Cliente")
        clienti = sorted(df["Cliente"].astype(str).unique().tolist())
        sel_cli = st.selectbox("Seleziona Cliente:", ["-- Riepilogo --"] + clienti)
        
        if sel_cli != "-- Riepilogo --":
            sub = df[df["Cliente"] == sel_cli]
            c_fatt = sub["Importo Fatt. (€)"].sum()
            c_pag = sub["Importo Pagato (€)"].sum()
            c_sal = sub["Saldo (€)"].sum()
            
            kc1, kc2, kc3 = st.columns(3)
            kc1.metric("Fatturato", f"€ {c_fatt:,.2f}")
            kc2.metric("Pagato", f"€ {c_pag:,.2f}")
            kc3.metric("Debito", f"€ {c_sal:,.2f}", delta_color="inverse")
            st.dataframe(sub, use_container_width=True)
        else:
            # Raggruppa e somma
            grp = df.groupby("Cliente")[["Saldo (€)"]].sum().reset_index()
            # Ordina dal debito più alto
            grp = grp.sort_values("Saldo (€)", ascending=False)
            st.bar_chart(grp.set_index("Cliente"))
    else:
        st.info("Database vuoto. Inserisci fatture o importa CSV.")

# 2. INSERIMENTO
elif scelta == "Inserisci Fattura":
    st.header("➕ Nuova Fattura (Cloud)")
    with st.form("form"):
        c1, c2 = st.columns(2)
        cl = c1.text_input("Cliente")
        nf = c2.text_input("N. Fattura")
        dfat = c1.date_input("Data", datetime.today())
        imp = c2.number_input("Importo (€)", step=0.01)
        
        if st.form_submit_button("Salva su Google"):
            new_row = {
                "Cliente": cl, "N. Fattura": nf, 
                "Data Fatt.": dfat.strftime("%d/%m/%Y"),
                "Importo Fatt. (€)": imp, "Importo Pagato (€)": 0.0,
                "Saldo (€)": imp, "Stato": "Non Pagata", "Data Saldo": ""
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            save_data(df)
            st.success("Fattura salvata online!")
            st.rerun()

# 3. GESTIONE
elif scelta == "Gestione Tabella":
    st.header("📝 Modifica Live")
    edited = st.data_editor(df, num_rows="dynamic", use_container_width=True)
    if st.button("💾 Sincronizza Google Sheets"):
        for i, row in edited.iterrows():
            s, st_val, d_s = calcola_stato_saldo(row)
            edited.at[i, "Saldo (€)"] = s
            edited.at[i, "Stato"] = st_val
            edited.at[i, "Data Saldo"] = d_s
        save_data(edited)
        st.success("Foglio Google Aggiornato!")
        st.rerun()

# 4. IMPORTA CSV
elif scelta == "Importa CSV":
    st.header("📂 Carica CSV su Google Sheets")
    uploaded = st.file_uploader("File CSV", type=["csv"])
    
    if uploaded:
        df_new = try_read_csv_upload(uploaded)
        if not df_new.empty:
            valid_cols = [c for c in COLONNE if c in df_new.columns]
            if len(valid_cols) == len(COLONNE):
                st.success(f"File valido! {len(df_new)} righe trovate.")
                st.dataframe(df_new.head(3))
                
                if st.button("Aggiungi questi dati al Cloud"):
                    # Applica la pulizia numeri anche qui
                    for col in ["Importo Fatt. (€)", "Importo Pagato (€)", "Saldo (€)"]:
                        df_new[col] = df_new[col].apply(pulisci_numero)
                    
                    df_comb = pd.concat([df, df_new[COLONNE]], ignore_index=True)
                    save_data(df_comb)
                    st.balloons()
                    st.success("Dati caricati su Google Sheets con successo!")
            else:
                st.error("Il file non ha le colonne giuste.")
