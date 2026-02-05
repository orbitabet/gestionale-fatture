import streamlit as st
import pandas as pd
import os
from datetime import datetime

# --- CONFIGURAZIONE PAGINA (Deve essere la prima istruzione) ---
st.set_page_config(
    page_title="Gestionale Fatture & Pagamenti",
    page_icon="💼",
    layout="wide"
)

# --- FILE DATABASE ---
FILE_DATI = 'fatture_db.csv'

# --- COLONNE ---
COLONNE = [
    "Cliente", "N. Fattura", "Data Fatt.", 
    "Importo Fatt. (€)", "Importo Pagato (€)", 
    "Saldo (€)", "Stato", "Data Saldo"
]

# --- FUNZIONI UTILI ---
def clean_column_names(df):
    new_columns = []
    for col in df.columns:
        col_clean = col.replace('ï»¿', '').replace('ïbb¿', '') # Toglie BOM
        col_clean = col_clean.replace('â\x82¬', '€').replace('â¬', '€').replace('ð', '€') # Toglie errori Euro
        col_clean = col_clean.strip()
        new_columns.append(col_clean)
    df.columns = new_columns
    return df

def try_read_csv(file_source):
    separators = [';', ',']
    encodings = ['ISO-8859-1', 'utf-8-sig', 'cp1252']
    
    for sep in separators:
        for enc in encodings:
            try:
                if hasattr(file_source, 'seek'): file_source.seek(0)
                df = pd.read_csv(file_source, sep=sep, encoding=enc)
                df = clean_column_names(df)
                if len(df.columns) > 1 and "Cliente" in df.columns:
                    return df
            except Exception:
                continue
    if hasattr(file_source, 'seek'): file_source.seek(0)
    return pd.read_csv(file_source, sep=None, engine='python', encoding='ISO-8859-1')

def load_data():
    if os.path.exists(FILE_DATI):
        try:
            df = try_read_csv(FILE_DATI)
            cols_to_numeric = ["Importo Fatt. (€)", "Importo Pagato (€)", "Saldo (€)"]
            for col in cols_to_numeric:
                if col in df.columns:
                    df[col] = pd.to_numeric(
                        df[col].astype(str).str.replace('€', '').str.replace(',', '.'), 
                        errors='coerce'
                    ).fillna(0)
            for col in COLONNE:
                if col not in df.columns: df[col] = ""
            return df[COLONNE]
        except Exception as e:
            st.error(f"Errore caricamento: {e}")
            return pd.DataFrame(columns=COLONNE)
    else:
        return pd.DataFrame(columns=COLONNE)

def save_data(df):
    try:
        # Salviamo con punto e virgola (Excel Friendly)
        df.to_csv(FILE_DATI, index=False, sep=';', encoding='utf-8-sig')
    except Exception as e:
        st.error(f"Errore salvataggio: {e}")

def calcola_stato_saldo(row):
    importo = float(row["Importo Fatt. (€)"])
    pagato = float(row["Importo Pagato (€)"])
    saldo = importo - pagato
    stato = "Non Pagata"
    data_saldo = row["Data Saldo"]

    if saldo <= 0.01: 
        saldo = 0
        stato = "Pagata"
        if pd.isna(data_saldo) or str(data_saldo).strip() == "":
            data_saldo = datetime.today().strftime("%d/%m/%Y")
    elif pagato > 0:
        stato = "Parziale"
    return saldo, stato, data_saldo

# --- INTERFACCIA ---
with st.sidebar:
    # --- LOGICA LOGO INTELLIGENTE (AGGIUNTA QUI) ---
    if os.path.exists("logo.png"):
        st.image("logo.png", width=250)
    elif os.path.exists("logo.jpg"):
        st.image("logo.jpg", width=250)
    elif os.path.exists("logo.jpeg"):
        st.image("logo.jpeg", width=250)
    else:
        # Se non trova nulla, lascia uno spazio vuoto ma non da errore
        st.write("") 
        
    st.title("Menu")
    scelta = st.radio("Vai a:", ["Dashboard & Analisi", "Inserisci Fattura", "Gestione Tabella", "Importa CSV"])
    st.markdown("---")
    st.caption("Gestionale V. 1.4")

df = load_data()

# 1. DASHBOARD AVANZATA
if scelta == "Dashboard & Analisi":
    st.title("📊 Dashboard Aziendale")
    
    if not df.empty:
        # --- TOTALI GENERALI ---
        st.markdown("### 🌍 Situazione Generale")
        col1, col2, col3 = st.columns(3)
        tot_fatt = df["Importo Fatt. (€)"].sum()
        tot_pag = df["Importo Pagato (€)"].sum()
        tot_saldo = df["Saldo (€)"].sum()
        
        col1.metric("Totale Fatturato", f"€ {tot_fatt:,.2f}")
        col2.metric("Totale Incassato", f"€ {tot_pag:,.2f}")
        col3.metric("TOTALE DA INCASSARE", f"€ {tot_saldo:,.2f}", delta_color="inverse")
        
        st.markdown("---")
        
        # --- ANALISI PER CLIENTE ---
        st.header("👤 Analisi Cliente")
        
        lista_clienti = sorted(df["Cliente"].astype(str).unique().tolist())
        cliente_selezionato = st.selectbox("Seleziona un Cliente:", ["-- Riepilogo Tutti i Clienti --"] + lista_clienti)

        if cliente_selezionato != "-- Riepilogo Tutti i Clienti --":
            # FILTRO DATI
            df_cliente = df[df["Cliente"] == cliente_selezionato]
            
            c_fatt = df_cliente["Importo Fatt. (€)"].sum()
            c_pag = df_cliente["Importo Pagato (€)"].sum()
            c_saldo = df_cliente["Saldo (€)"].sum()
            
            c1, c2, c3 = st.columns(3)
            c1.metric(f"Fatturato {cliente_selezionato}", f"€ {c_fatt:,.2f}")
            c2.metric("Pagato", f"€ {c_pag:,.2f}")
            c3.metric("Debito residuo", f"€ {c_saldo:,.2f}", delta_color="inverse")
            
            st.subheader(f"Storico Fatture: {cliente_selezionato}")
            st.dataframe(df_cliente, use_container_width=True)
            
        else:
            # RIEPILOGO TUTTI
            st.subheader("🏆 Classifica Clienti (Debitori)")
            riepilogo = df.groupby("Cliente")[["Importo Fatt. (€)", "Importo Pagato (€)", "Saldo (€)"]].sum().reset_index()
            riepilogo = riepilogo.sort_values(by="Saldo (€)", ascending=False)
            st.dataframe(riepilogo, use_container_width=True)

    else:
        st.info("Nessun dato presente. Importa un file CSV o inserisci fatture.")

# 2. INSERIMENTO
elif scelta == "Inserisci Fattura":
    st.header("➕ Nuova Fattura")
    with st.form("form_fattura"):
        c1, c2 = st.columns(2)
        cliente = c1.text_input("Ragione Sociale Cliente")
        n_fatt = c2.text_input("Numero Fattura")
        data_f = c1.date_input("Data", datetime.today())
        importo = c2.number_input("Importo (€)", min_value=0.0, step=0.01)
        
        if st.form_submit_button("Registra"):
            new_row = {
                "Cliente": cliente, "N. Fattura": n_fatt,
                "Data Fatt.": data_f.strftime("%d/%m/%Y"),
                "Importo Fatt. (€)": importo, "Importo Pagato (€)": 0.0,
                "Saldo (€)": importo, "Stato": "Non Pagata", "Data Saldo": ""
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            save_data(df)
            st.success("Registrato!")

# 3. GESTIONE
elif scelta == "Gestione Tabella":
    st.header("📝 Modifica Dati")
    st.info("Modifica i valori (es. Importo Pagato) e premi Salva.")
    df_edit = st.data_editor(df, num_rows="dynamic", use_container_width=True, key="edit")
    
    if st.button("💾 Salva Modifiche"):
        for i, row in df_edit.iterrows():
            s, st_val, d_s = calcola_stato_saldo(row)
            df_edit.at[i, "Saldo (€)"] = s
            df_edit.at[i, "Stato"] = st_val
            df_edit.at[i, "Data Saldo"] = d_s
        save_data(df_edit)
        st.success("Salvato!")
        st.rerun()

# 4. IMPORTA
elif scelta == "Importa CSV":
    st.header("📂 Importa CSV")
    uploaded = st.file_uploader("File CSV", type=["csv"])
    if uploaded:
        try:
            df_new = try_read_csv(uploaded)
            if not [c for c in COLONNE if c not in df_new.columns]:
                st.success(f"Letto correttamente! {len(df_new)} righe.")
                if st.button("Unisci Dati"):
                    df_new = df_new[COLONNE]
                    for col in ["Importo Fatt. (€)", "Importo Pagato (€)", "Saldo (€)"]:
                        df_new[col] = pd.to_numeric(
                            df_new[col].astype(str).str.replace('€','').str.replace(',','.'), 
                            errors='coerce').fillna(0)
                    df_comb = pd.concat([df, df_new], ignore_index=True)
                    save_data(df_comb)
                    st.success("Fatto!")
            else:
                st.error("Colonne errate.")
        except Exception as e:
            st.error(f"Errore: {e}")