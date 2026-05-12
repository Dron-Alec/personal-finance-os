import streamlit as st
import pandas as pd
import json
import os
import io
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go

# ── SUPABASE (optional — enables cloud persistence) ───────────────────────────
def _secret(k):
    try:
        return st.secrets.get(k) or ""
    except Exception:
        return ""

_SB_URL = os.environ.get("SUPABASE_URL", "") or _secret("SUPABASE_URL")
_SB_KEY = os.environ.get("SUPABASE_KEY", "") or _secret("SUPABASE_KEY")
USE_SUPABASE = bool(_SB_URL and _SB_KEY)

@st.cache_resource
def _sb():
    from supabase import create_client
    return create_client(_SB_URL, _SB_KEY)

# ── CONFIG ────────────────────────────────────────────────────────────────────
DATA_DIR = "data"
TARGET_FILE = "targets.csv"
MAPPING_FILE = "category_map.json"
os.makedirs(DATA_DIR, exist_ok=True)

PEOPLE = {
    "alec":  {"name": "Alec",  "file": f"{DATA_DIR}/alec.json",  "color": "#2196F3"},
    "haley": {"name": "Haley", "file": f"{DATA_DIR}/haley.json", "color": "#E91E63"},
}

BANK_FORMATS = [
    "Citi Checking",
    "Citi Credit",
    "Discover",
    "Axos Checking",
    "Axos Savings",
    "Wells Fargo Checking",
    "Wells Fargo Credit",
    "Chase Checking",
    "Chase Credit",
    "Bank of America Checking",
    "Bank of America Credit",
]

ACCOUNT_TYPES = [
    "Checking", "Savings", "Credit Card",
    "Brokerage / Stocks", "401k", "Roth IRA", "Traditional IRA",
    "Crypto", "Real Estate", "Other",
]

DEFAULT_CATEGORY_MAP = {
    "Groceries": [
        "TRADER JOE", "WHOLE FOOD", "WHOLEFDS", "STOP & SHOP", "ALDI",
        "PUBLIX", "WALMART", "WAL-MART", "WM SUPERCENTER", "JERSEY CITY BUY RITE",
        "GROCERY", "KROGER", "COSTCO", "SAFEWAY", "WEGMANS", "SHOPRITE",
        "GIANT", "HARRIS TEETER",
    ],
    "Dining": [
        "RESTAURANT", "CAFE", "COFFEE", "STARBUCKS", "DUNKIN", "PIZZA",
        "SUSHI", " BAR ", "TAVERN", "GRILL", "DINER", "CHIPOTLE", "CHICK-FIL",
        "MCDONALD", "BURGER", "SUBWAY", "PANERA", "PHO", "TACO", "TST*",
        "DOORDASH", "GRUBHUB", "UBEREATS", "SEAMLESS", "HYPPO",
        "IRREGARDLESS", "BREADS BAKERY",
    ],
    "Transportation": [
        "MTA*", "MTA ", "PATH TAPP", "UBER", "LYFT", "SUNOCO", "SHELL",
        "EXXON", "PILOT ", "SHEETZ", " GAS ", "AMTRAK", "GREYHOUND",
        "DELTA", "AMERICAN AIR", "UNITED AIR", "SOUTHWEST", "PARKERS",
    ],
    "Utilities": [
        "PSEG", "PUBLIC SERVICE", "COMCAST", "XFINITY", "CON ED",
        "NATIONAL GRID", "VERIZON", "AT&T", "T-MOBILE", "SPECTRUM",
    ],
    "Rent / Housing": [
        "BALD COLLECTION", "RENT", "HOUSING", "APARTMENT", "MORTGAGE",
    ],
    "Subscriptions": [
        "SPOTIFY", "NETFLIX", "HULU", "DISNEY", "AMAZON PRIME", "HBO",
        "APPLE.COM/BILL", "GOOGLE*", "YOUTUBE", "PATREON", "AUDIBLE",
        "PERPLEXITY", "CHATGPT", "OPENAI", "OURARING", "MEMBERSHIP FEE",
    ],
    "Shopping": [
        "AMAZON", "TARGET 000", "CRATE AND BARREL", "NORDSTROM", "MACY",
        "H&M", "ZARA", "WALGREENS", "CVS", "RITE AID", "THE ATTIC",
        "SCHROPP", "KALSHI", "WALMART STORE", "PAPERSOURCE",
    ],
    "Health & Fitness": [
        "PHARMACY", "OURA", "GYM", "PELOTON", "FITNESS", "HEALTH",
        "MEDICAL", "DENTAL", "VISION", "DOCTOR", "HOSPITAL",
    ],
    "Investments": [
        "COINBASE", "FID BKG SVC", "FIDELITY", "VANGUARD", "SCHWAB",
        "ROBINHOOD", "E*TRADE", "TD AMERITRADE",
    ],
    "Income": [
        "PAYROLL", "DIRECT DEPOSIT", "CROWE LLP", "JEWISHFEDERATION", "MESORAH",
    ],
    "Transfers": [
        "VENMO", "ZELLE", "PAYPAL", "CASHAPP", "TRANSFER FROM",
        "HALEY GRINER", "PAYMENT - THANK YOU", "PAYMENT THANK YOU",
        "ONLINE PAYMENT", "BILL PAYMENT",
    ],
}

# ── DATA HELPERS ──────────────────────────────────────────────────────────────
def load_json(path, default):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def empty_person():
    return {"transactions": [], "nw_snapshots": [], "accounts": {}}

# ── Supabase read/write helpers ───────────────────────────────────────────────
def _sb_load_person(key):
    sb = _sb()
    data = empty_person()

    rows = sb.table("transactions").select("*").eq("person", key).execute().data or []
    data["transactions"] = [
        {"Date": r["date"], "Description": r["description"],
         "Amount": r["amount"], "Bank": r["bank"], "Category": r["category"]}
        for r in rows
    ]

    rows = sb.table("nw_snapshots").select("*").eq("person", key).execute().data or []
    data["nw_snapshots"] = [
        {"Date": r["date"], "Net Worth": r["net_worth"], "Note": r.get("note", "")}
        for r in rows
    ]

    rows = sb.table("accounts").select("*").eq("person", key).execute().data or []
    data["accounts"] = {
        r["name"]: {"type": r["type"], "balance": r["balance"], "updated": r.get("updated", "")}
        for r in rows
    }
    return data

def _sb_save_person(key, data):
    sb = _sb()

    sb.table("transactions").delete().eq("person", key).execute()
    if data["transactions"]:
        sb.table("transactions").insert([
            {"person": key, "date": t["Date"], "description": t["Description"],
             "amount": t["Amount"], "bank": t["Bank"], "category": t["Category"]}
            for t in data["transactions"]
        ]).execute()

    sb.table("nw_snapshots").delete().eq("person", key).execute()
    if data["nw_snapshots"]:
        sb.table("nw_snapshots").insert([
            {"person": key, "date": s["Date"], "net_worth": s["Net Worth"], "note": s.get("Note", "")}
            for s in data["nw_snapshots"]
        ]).execute()

    sb.table("accounts").delete().eq("person", key).execute()
    if data["accounts"]:
        sb.table("accounts").insert([
            {"person": key, "name": name, "type": v["type"],
             "balance": v["balance"], "updated": v.get("updated", "")}
            for name, v in data["accounts"].items()
        ]).execute()

    st.cache_data.clear()

def _sb_load_mapping():
    sb = _sb()
    row = sb.table("settings").select("value").eq("key", "category_map").execute().data
    if row:
        stored = row[0]["value"]
        merged = dict(DEFAULT_CATEGORY_MAP)
        merged.update(stored)
        return merged
    return dict(DEFAULT_CATEGORY_MAP)

def _sb_save_mapping(m):
    sb = _sb()
    sb.table("settings").upsert({"key": "category_map", "value": m}).execute()
    st.cache_data.clear()

# ── Public data API (dispatches to Supabase or local files) ───────────────────
def load_person(key):
    if USE_SUPABASE:
        return _sb_load_person(key)
    return load_json(PEOPLE[key]["file"], empty_person())

def save_person(key, data):
    if USE_SUPABASE:
        _sb_save_person(key, data)
    else:
        save_json(PEOPLE[key]["file"], data)

def load_mapping():
    if USE_SUPABASE:
        return _sb_load_mapping()
    stored = load_json(MAPPING_FILE, {})
    merged = dict(DEFAULT_CATEGORY_MAP)
    merged.update(stored)
    return merged

def save_mapping(m):
    if USE_SUPABASE:
        _sb_save_mapping(m)
    else:
        save_json(MAPPING_FILE, m)

def categorize(description, mapping):
    desc_upper = str(description).upper()
    for cat, keywords in mapping.items():
        if any(kw.upper() in desc_upper for kw in keywords):
            return cat
    return "Other"

def load_targets():
    if os.path.exists(TARGET_FILE):
        return pd.read_csv(TARGET_FILE)
    return pd.DataFrame(columns=["quarter", "target_net_worth"])

def quarter_to_date(q_str):
    yr, q = q_str.split("-Q")
    return pd.Timestamp(f"{yr}-{int(q)*3:02d}-01")

def current_quarter():
    now = datetime.now()
    return f"{now.year}-Q{(now.month-1)//3+1}"

def fill_color(hex_color, alpha=0.12):
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    return f"rgba({r},{g},{b},{alpha})"

# ── ONE-TIME MIGRATION from data.json ────────────────────────────────────────
def maybe_migrate():
    if not os.path.exists("data.json") or os.path.exists(PEOPLE["alec"]["file"]):
        return
    old = load_json("data.json", {})
    mapping = load_mapping()
    txs = []
    for tx in old.get("transactions", []):
        t = dict(tx)
        if t.get("Bank") == "Discover":
            t["Amount"] = -t["Amount"]
        t["Category"] = categorize(t.get("Description", ""), mapping)
        txs.append(t)

    alec_data = empty_person()
    alec_data["transactions"] = txs

    starting_nw = old.get("starting_net_worth", 0)
    if starting_nw:
        alec_data["nw_snapshots"].append({
            "Date": "2025-01-01",
            "Net Worth": starting_nw,
            "Note": "Migrated from old data",
        })

    si = old.get("starting_investments", {})
    type_map = {
        "stocks": ("Stocks / Brokerage", "Brokerage / Stocks"),
        "rothIRA": ("Roth IRA", "Roth IRA"),
        "401k": ("401k", "401k"),
        "other": ("Other Investments", "Other"),
    }
    for k, (acct_name, acct_type) in type_map.items():
        if si.get(k):
            alec_data["accounts"][acct_name] = {
                "type": acct_type,
                "balance": si[k],
                "updated": "2025-01-01",
            }
    save_person("alec", alec_data)

maybe_migrate()

# ── CSV PROCESSING ────────────────────────────────────────────────────────────
def find_col(cols, keywords):
    for k in keywords:
        for c in cols:
            if k.lower() in c.lower():
                return c
    return None

def clean_val(val):
    s = str(val).replace(",", "").replace("$", "").strip()
    if s.lower() in ("nan", "", "--", "none"):
        return 0.0
    try:
        return float(s)
    except:
        return 0.0

def find_header_row(lines):
    for i, line in enumerate(lines[:25]):
        if any(k in line for k in ("Date", "Status", "Transaction", "Trans.")):
            return i
    return 0

def process_csv(uploaded_file, bank_type):
    raw = uploaded_file.getvalue().decode("utf-8", errors="ignore").splitlines()
    skip = find_header_row(raw)
    uploaded_file.seek(0)
    try:
        df = pd.read_csv(uploaded_file, skiprows=skip, index_col=False)
    except Exception:
        return []
    df = df.loc[:, ~df.columns.str.contains("^Unnamed")]
    df.columns = [str(c).strip() for c in df.columns]

    date_col = find_col(df.columns, ["Date", "Trans Date", "Transaction Date", "Post Date"])
    desc_col = find_col(df.columns, ["Description", "Memo", "Name", "Payee", "Merchant"])
    if not date_col or not desc_col:
        return []

    txs = []
    for _, row in df.iterrows():
        try:
            raw_date = str(row.get(date_col, ""))
            if not raw_date or raw_date.lower() in ("nan", "date"):
                continue
            valid_date = pd.to_datetime(raw_date, errors="coerce")
            if pd.isna(valid_date):
                continue
            desc = str(row.get(desc_col, ""))

            if bank_type in ("Citi Checking", "Citi Credit"):
                debit_col  = find_col(df.columns, ["Debit"])
                credit_col = find_col(df.columns, ["Credit"])
                amt_col    = find_col(df.columns, ["Amount"])
                if debit_col and credit_col:
                    amount = clean_val(row.get(credit_col, 0)) - clean_val(row.get(debit_col, 0))
                elif amt_col:
                    amount = clean_val(row.get(amt_col, 0))
                else:
                    continue

            elif bank_type == "Discover":
                # Discover CSV: positive = charge, negative = payment.
                # Negate so expenses are negative in our system.
                amt_col = find_col(df.columns, ["Amount"])
                amount = -clean_val(row.get(amt_col, 0)) if amt_col else 0.0

            else:
                # WF, Chase, BofA, Axos: negative = debit/expense, positive = credit/income
                amt_col = find_col(df.columns, ["Amount"])
                amount = clean_val(row.get(amt_col, 0)) if amt_col else 0.0

            txs.append({
                "Date": valid_date.strftime("%m/%d/%Y"),
                "Description": desc,
                "Amount": amount,
                "Bank": bank_type,
            })
        except Exception:
            continue
    return txs

# ── NET WORTH HELPER ─────────────────────────────────────────────────────────
def nw_df(person_data):
    snaps = person_data.get("nw_snapshots", [])
    if not snaps:
        return pd.DataFrame(columns=["Date", "Net Worth"])
    df = pd.DataFrame(snaps)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date")
    return df[["Date", "Net Worth"]]

# ─────────────────────────────────────────────────────────────────────────────
# TAB RENDERERS
# ─────────────────────────────────────────────────────────────────────────────

def render_import(person_key):
    data = load_person(person_key)
    mapping = load_mapping()

    st.subheader("Upload Bank / Credit Card Statements")
    c1, c2 = st.columns([1, 2])
    bank_type = c1.selectbox("Statement Format", BANK_FORMATS, key=f"fmt_{person_key}")
    files = c2.file_uploader(
        "CSV files (multiple OK)", type="csv",
        accept_multiple_files=True, key=f"up_{person_key}"
    )

    if files and st.button("Import Transactions", key=f"imp_{person_key}"):
        new_txs = []
        for f in files:
            parsed = process_csv(f, bank_type)
            for tx in parsed:
                tx["Category"] = categorize(tx["Description"], mapping)
            new_txs.extend(parsed)

        existing_keys = {(t["Date"], t["Description"], t["Amount"]) for t in data["transactions"]}
        added = [t for t in new_txs if (t["Date"], t["Description"], t["Amount"]) not in existing_keys]
        data["transactions"].extend(added)
        save_person(person_key, data)

        st.success(f"Imported **{len(added)}** transactions ({len(new_txs)-len(added)} duplicates skipped).")
        st.rerun()

    txs = data.get("transactions", [])
    if txs:
        st.caption(f"{len(txs)} transactions on file")
        df_p = pd.DataFrame(txs)
        df_p["Date"] = pd.to_datetime(df_p["Date"], errors="coerce")

        # Download button
        csv_bytes = df_p.sort_values("Date", ascending=False).to_csv(index=False).encode()
        st.download_button(
            "⬇️ Download all transactions as CSV",
            data=csv_bytes,
            file_name=f"{person_key}_transactions.csv",
            mime="text/csv",
        )
        st.dataframe(df_p.sort_values("Date", ascending=False), use_container_width=True, height=340)
    else:
        st.info("No transactions yet. Upload a CSV above.")


def render_networth(person_key):
    data    = load_person(person_key)
    name    = PEOPLE[person_key]["name"]
    color   = PEOPLE[person_key]["color"]
    df_tgt  = load_targets()

    st.subheader(f"{name}'s Net Worth")

    with st.expander("➕ Add / Update Snapshot", expanded=not data.get("nw_snapshots")):
        c1, c2, c3 = st.columns([1, 1, 2])
        snap_date = c1.date_input("Date", value=datetime.today(), key=f"sd_{person_key}")
        snap_nw   = c2.number_input("Net Worth ($)", value=0.0, step=100.0, key=f"snw_{person_key}")
        snap_note = c3.text_input("Note (optional)", key=f"sn_{person_key}")
        if st.button("Save Snapshot", key=f"ssave_{person_key}"):
            data["nw_snapshots"].append({
                "Date": snap_date.strftime("%Y-%m-%d"),
                "Net Worth": snap_nw,
                "Note": snap_note,
            })
            save_person(person_key, data)
            st.success("Saved!")
            st.rerun()

    df_nw = nw_df(data)
    if df_nw.empty:
        st.info("No snapshots yet — add your first net worth entry above.")
        return

    latest = float(df_nw.iloc[-1]["Net Worth"])
    cq = current_quarter()
    target_row = df_tgt[df_tgt["quarter"] == cq] if not df_tgt.empty else pd.DataFrame()

    m1, m2, m3 = st.columns(3)
    m1.metric("Current Net Worth", f"${latest:,.0f}")
    if not target_row.empty:
        tval = float(target_row.iloc[0]["target_net_worth"])
        m2.metric(f"{cq} Target", f"${tval:,.0f}", delta=f"${latest - tval:+,.0f}")
    if len(df_nw) >= 2:
        prev = float(df_nw.iloc[-2]["Net Worth"])
        m3.metric("Δ Since Last Entry", f"${latest - prev:+,.0f}")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_nw["Date"], y=df_nw["Net Worth"],
        mode="lines+markers", name=name,
        line=dict(color=color, width=2.5),
        fill="tozeroy", fillcolor=fill_color(color),
    ))
    if not df_tgt.empty:
        df_tgt = df_tgt.copy()
        df_tgt["Date"] = df_tgt["quarter"].apply(quarter_to_date)
        fig.add_trace(go.Scatter(
            x=df_tgt["Date"], y=df_tgt["target_net_worth"],
            mode="lines", name="Target",
            line=dict(color="#FFC107", width=2, dash="dash"),
        ))
    fig.update_layout(
        xaxis_title="Date", yaxis_title="USD",
        hovermode="x unified", height=420,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(t=30),
    )
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Snapshot History"):
        snaps_df = pd.DataFrame(data.get("nw_snapshots", []))
        st.dataframe(snaps_df, use_container_width=True)
        if st.button("🗑️ Clear All Snapshots", key=f"clrsnap_{person_key}"):
            data["nw_snapshots"] = []
            save_person(person_key, data)
            st.rerun()


def render_spending(person_key):
    data = load_person(person_key)
    txs  = data.get("transactions", [])
    if not txs:
        st.info("No transactions yet — import CSV statements first.")
        return

    df_all = pd.DataFrame(txs)
    df_all["Date"] = pd.to_datetime(df_all["Date"], errors="coerce")
    df_all = df_all.dropna(subset=["Date"])

    c1, c2, c3 = st.columns(3)
    months   = sorted(df_all["Date"].dt.to_period("M").unique(), reverse=True)
    sel_mo   = c1.selectbox("Month",    ["All"] + [str(m) for m in months],           key=f"mo_{person_key}")
    sel_cat  = c2.selectbox("Category", ["All"] + sorted(df_all["Category"].unique()), key=f"ca_{person_key}")
    sel_bank = c3.selectbox("Account",  ["All"] + sorted(df_all["Bank"].unique()),     key=f"bk_{person_key}")

    df = df_all.copy()
    if sel_mo   != "All": df = df[df["Date"].dt.to_period("M").astype(str) == sel_mo]
    if sel_cat  != "All": df = df[df["Category"] == sel_cat]
    if sel_bank != "All": df = df[df["Bank"] == sel_bank]

    expenses = df[df["Amount"] < 0].copy()
    expenses["Amount"] = expenses["Amount"].abs()
    income   = df[df["Amount"] > 0].copy()

    m1, m2, m3 = st.columns(3)
    m1.metric("Total Spending",        f"${expenses['Amount'].sum():,.2f}")
    m2.metric("Total Income / Credits",f"${income['Amount'].sum():,.2f}")
    m3.metric("Net Cash Flow",         f"${income['Amount'].sum() - expenses['Amount'].sum():+,.2f}")

    if not expenses.empty:
        col_pie, col_bar = st.columns(2)
        with col_pie:
            cat_totals = expenses.groupby("Category")["Amount"].sum().reset_index()
            fig_pie = px.pie(cat_totals, values="Amount", names="Category",
                             hole=0.42, title="Spending by Category",
                             color_discrete_sequence=px.colors.qualitative.Set3)
            fig_pie.update_traces(textinfo="percent+label")
            st.plotly_chart(fig_pie, use_container_width=True)

        with col_bar:
            monthly = expenses.copy()
            monthly["Month"] = monthly["Date"].dt.to_period("M").astype(str)
            fig_bar = px.bar(
                monthly.groupby(["Month","Category"])["Amount"].sum().reset_index(),
                x="Month", y="Amount", color="Category",
                title="Monthly by Category",
                color_discrete_sequence=px.colors.qualitative.Set3,
            )
            st.plotly_chart(fig_bar, use_container_width=True)

    st.subheader("Transactions")
    st.dataframe(df.sort_values("Date", ascending=False), use_container_width=True, height=350)

    with st.expander("✏️ Re-categorize Transactions"):
        mapping  = load_mapping()
        sel_desc = st.selectbox("Description", sorted(df_all["Description"].unique()), key=f"rcd_{person_key}")
        new_cat  = st.selectbox("New Category", sorted(mapping.keys()) + ["Other"],    key=f"rcc_{person_key}")
        if st.button("Apply", key=f"rca_{person_key}"):
            for tx in data["transactions"]:
                if tx["Description"] == sel_desc:
                    tx["Category"] = new_cat
            save_person(person_key, data)
            st.success("Updated!")
            st.rerun()


STANDARD_BACKFILL_ACCOUNTS = [
    ("Citi Checking",      "Checking"),
    ("Axos Checking",      "Checking"),
    ("Axos Savings",       "Savings"),
    ("Coinbase",           "Crypto"),
    ("Roth 401k",          "401k"),
    ("Roth IRA",           "Roth IRA"),
    ("Taxable Brokerage",  "Brokerage / Stocks"),
    ("Other Investments",  "Other"),
]


def render_accounts(person_key):
    data     = load_person(person_key)
    name     = PEOPLE[person_key]["name"]
    accounts = data.get("accounts", {})

    st.subheader(f"{name}'s Accounts & Holdings")

    # ── Bulk / Backfill Entry ─────────────────────────────────────────────────
    with st.expander("📅 Manual Balance Entry (backfill / bulk update)", expanded=not accounts):
        st.caption(
            "Enter balances for all accounts on a specific date — useful for backfilling "
            "missed months. A net worth snapshot is saved automatically from the totals."
        )

        entry_date = st.date_input(
            "As of Date", value=datetime.today(), key=f"bulk_date_{person_key}"
        )

        # Collect inputs for every existing named account
        existing_vals: dict[str, float] = {}
        new_vals: dict[str, tuple[str, float]] = {}  # name -> (type, balance)

        st.markdown("**Your accounts**")
        if accounts:
            cols = st.columns(2)
            for idx, (acct_name, acct_info) in enumerate(accounts.items()):
                col = cols[idx % 2]
                existing_vals[acct_name] = col.number_input(
                    f"{acct_name}",
                    value=float(acct_info.get("balance", 0.0)),
                    step=100.0,
                    format="%.2f",
                    key=f"bulk_ex_{person_key}_{acct_name}",
                )
        else:
            st.info("No accounts set up yet — fill in the standard types below.")

        # Show standard account types that aren't already named accounts
        missing_standards = [
            (n, t) for n, t in STANDARD_BACKFILL_ACCOUNTS if n not in accounts
        ]
        if missing_standards:
            st.markdown("**Standard account types** *(leave at 0 to skip)*")
            cols2 = st.columns(2)
            for idx, (std_name, std_type) in enumerate(missing_standards):
                col = cols2[idx % 2]
                val = col.number_input(
                    f"{std_name} ({std_type})",
                    value=0.0,
                    step=100.0,
                    format="%.2f",
                    key=f"bulk_std_{person_key}_{std_name}",
                )
                if val != 0.0:
                    new_vals[std_name] = (std_type, val)

        total_bulk = sum(existing_vals.values()) + sum(v for _, v in new_vals.values())
        st.metric("Total (this entry)", f"${total_bulk:,.2f}")

        update_acct_records = st.checkbox(
            "Also update each account's current balance record",
            value=True,
            key=f"bulk_upd_{person_key}",
        )

        if st.button("💾 Save Entry", key=f"bulk_save_{person_key}"):
            date_str = entry_date.strftime("%Y-%m-%d")

            # Update existing account balances
            if update_acct_records:
                for acct_name, bal in existing_vals.items():
                    accounts[acct_name]["balance"] = bal
                    accounts[acct_name]["updated"] = date_str
                # Create new accounts for non-zero standard entries
                for acct_name, (acct_type, bal) in new_vals.items():
                    accounts[acct_name] = {
                        "type": acct_type,
                        "balance": bal,
                        "updated": date_str,
                    }
                data["accounts"] = accounts

            # Save net worth snapshot
            data.setdefault("nw_snapshots", []).append({
                "Date": date_str,
                "Net Worth": total_bulk,
                "Note": "Manual entry",
            })
            save_person(person_key, data)
            st.success(
                f"Saved! Net worth snapshot of **${total_bulk:,.2f}** recorded for {date_str}."
            )
            st.rerun()

    # ── Single Account Add / Update ───────────────────────────────────────────
    with st.expander("➕ Add / Update Single Account", expanded=False):
        c1, c2, c3 = st.columns(3)
        acct_name = c1.text_input("Account Name", placeholder="e.g. Fidelity 401k", key=f"an_{person_key}")
        acct_type = c2.selectbox("Type", ACCOUNT_TYPES, key=f"at_{person_key}")
        acct_bal  = c3.number_input("Balance ($)", value=0.0, step=100.0, key=f"ab_{person_key}")
        if st.button("Save Account", key=f"as_{person_key}") and acct_name:
            accounts[acct_name] = {
                "type": acct_type,
                "balance": acct_bal,
                "updated": datetime.today().strftime("%Y-%m-%d"),
            }
            data["accounts"] = accounts
            save_person(person_key, data)
            st.success(f"Saved '{acct_name}'")
            st.rerun()

    if not accounts:
        st.info("Add your checking, savings, investment, and retirement accounts above.")
        return

    rows = [
        {"Account": k, "Type": v["type"], "Balance ($)": v["balance"], "As of": v.get("updated","")}
        for k, v in accounts.items()
    ]
    df_a  = pd.DataFrame(rows)
    total = df_a["Balance ($)"].sum()
    st.metric("Total Account Value", f"${total:,.0f}")

    c_table, c_chart = st.columns(2)
    with c_table:
        st.dataframe(df_a, use_container_width=True)
    with c_chart:
        fig = px.pie(df_a, values="Balance ($)", names="Account", hole=0.42,
                     title="Portfolio Breakdown",
                     color_discrete_sequence=px.colors.qualitative.Pastel)
        st.plotly_chart(fig, use_container_width=True)

    type_totals = df_a.groupby("Type")["Balance ($)"].sum().reset_index()
    fig_bar = px.bar(type_totals, x="Type", y="Balance ($)", title="By Account Type",
                     color="Type", color_discrete_sequence=px.colors.qualitative.Pastel)
    st.plotly_chart(fig_bar, use_container_width=True)

    del_acct = st.selectbox("Remove Account", ["—"] + list(accounts.keys()), key=f"da_{person_key}")
    if del_acct != "—" and st.button("Remove", key=f"dr_{person_key}"):
        del accounts[del_acct]
        data["accounts"] = accounts
        save_person(person_key, data)
        st.rerun()


def render_settings(person_key):
    data    = load_person(person_key)
    name    = PEOPLE[person_key]["name"]
    mapping = load_mapping()

    st.subheader("Category Rules")
    st.caption("Keywords match case-insensitively. Saving re-categorizes all your transactions.")

    cats = list(mapping.keys()) + ["＋ New Category"]
    sel  = st.selectbox("Category", cats, key=f"sc_{person_key}")
    if sel == "＋ New Category":
        sel = st.text_input("New category name", key=f"nc_{person_key}")

    if sel and sel in mapping:
        kws_str = ", ".join(mapping[sel])
        new_kws = st.text_area("Keywords (comma-separated)", value=kws_str, key=f"kw_{person_key}")
        if st.button("Save Rules", key=f"sr_{person_key}"):
            mapping[sel] = [k.strip() for k in new_kws.split(",") if k.strip()]
            save_mapping(mapping)
            for tx in data["transactions"]:
                tx["Category"] = categorize(tx["Description"], mapping)
            save_person(person_key, data)
            st.success("Saved and re-categorized!")

    st.divider()
    st.subheader("Net Worth Targets  (shared between Alec & Haley)")
    df_t = load_targets()
    new_targets = st.text_area(
        "Edit targets.csv (quarter,target_net_worth)",
        value=df_t.to_csv(index=False) if not df_t.empty else "quarter,target_net_worth\n",
        height=200, key=f"tgt_{person_key}",
    )
    if st.button("Save Targets", key=f"stgt_{person_key}"):
        try:
            df_new = pd.read_csv(io.StringIO(new_targets))
            df_new.to_csv(TARGET_FILE, index=False)
            st.success("Targets saved!")
        except Exception as e:
            st.error(f"Error: {e}")

    st.divider()
    st.subheader("Danger Zone")
    if st.button(f"🗑️ Clear All of {name}'s Transactions", key=f"clrt_{person_key}"):
        data["transactions"] = []
        save_person(person_key, data)
        st.rerun()
    if st.button(f"🗑️ Reset ALL of {name}'s Data", key=f"clra_{person_key}"):
        save_person(person_key, empty_person())
        st.rerun()


def render_aggregated():
    alec_data  = load_person("alec")
    haley_data = load_person("haley")
    df_tgt     = load_targets()

    st.header("Combined Overview")

    # ── Net Worth ──────────────────────────────────────────────────────────────
    st.subheader("Net Worth")
    df_a = nw_df(alec_data)
    df_h = nw_df(haley_data)

    alec_latest  = float(df_a.iloc[-1]["Net Worth"]) if not df_a.empty else 0.0
    haley_latest = float(df_h.iloc[-1]["Net Worth"]) if not df_h.empty else 0.0
    combined     = alec_latest + haley_latest
    cq           = current_quarter()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Alec",     f"${alec_latest:,.0f}")
    m2.metric("Haley",    f"${haley_latest:,.0f}")
    m3.metric("Combined", f"${combined:,.0f}")
    if not df_tgt.empty:
        target_row = df_tgt[df_tgt["quarter"] == cq]
        if not target_row.empty:
            tval = float(target_row.iloc[0]["target_net_worth"])
            m4.metric(f"{cq} Target", f"${tval:,.0f}", delta=f"${combined - tval:+,.0f}")

    if not df_a.empty or not df_h.empty:
        fig_nw = go.Figure()
        if not df_a.empty:
            fig_nw.add_trace(go.Scatter(x=df_a["Date"], y=df_a["Net Worth"],
                                        mode="lines+markers", name="Alec",
                                        line=dict(color="#2196F3", width=2)))
        if not df_h.empty:
            fig_nw.add_trace(go.Scatter(x=df_h["Date"], y=df_h["Net Worth"],
                                        mode="lines+markers", name="Haley",
                                        line=dict(color="#E91E63", width=2)))
        if not df_a.empty and not df_h.empty:
            comb_df = pd.merge_asof(
                df_a.sort_values("Date").rename(columns={"Net Worth": "a"}),
                df_h.sort_values("Date").rename(columns={"Net Worth": "h"}),
                on="Date", direction="nearest",
            )
            comb_df["combined"] = comb_df["a"] + comb_df["h"]
            fig_nw.add_trace(go.Scatter(x=comb_df["Date"], y=comb_df["combined"],
                                        mode="lines+markers", name="Combined",
                                        line=dict(color="#4CAF50", width=3)))
        if not df_tgt.empty:
            df_tgt2 = df_tgt.copy()
            df_tgt2["Date"] = df_tgt2["quarter"].apply(quarter_to_date)
            fig_nw.add_trace(go.Scatter(x=df_tgt2["Date"], y=df_tgt2["target_net_worth"],
                                        mode="lines", name="Target",
                                        line=dict(color="#FFC107", width=2, dash="dash")))
        fig_nw.update_layout(
            hovermode="x unified", height=440,
            xaxis_title="Date", yaxis_title="USD",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            margin=dict(t=30),
        )
        st.plotly_chart(fig_nw, use_container_width=True)
    else:
        st.info("Add net worth snapshots for Alec and/or Haley to see the chart.")

    st.divider()

    # ── Combined Accounts ─────────────────────────────────────────────────────
    st.subheader("Combined Account Balances")
    all_accounts = []
    for key in ("alec", "haley"):
        d = load_person(key)
        for acct_name, v in d.get("accounts", {}).items():
            all_accounts.append({
                "Person": PEOPLE[key]["name"],
                "Account": acct_name,
                "Type": v["type"],
                "Balance ($)": v["balance"],
                "As of": v.get("updated", ""),
            })
    if all_accounts:
        df_accts = pd.DataFrame(all_accounts)
        total_accts = df_accts["Balance ($)"].sum()
        st.metric("Total Assets", f"${total_accts:,.0f}")
        c1, c2 = st.columns(2)
        with c1:
            st.dataframe(df_accts, use_container_width=True)
        with c2:
            fig_accts = px.pie(df_accts, values="Balance ($)", names="Account", hole=0.42,
                               title="All Accounts",
                               color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_accts, use_container_width=True)
    else:
        st.info("Add accounts in each person's Accounts tab.")

    st.divider()

    # ── Combined Spending ─────────────────────────────────────────────────────
    st.subheader("Combined Spending")
    dfs = []
    for key in ("alec", "haley"):
        d = load_person(key)
        if d.get("transactions"):
            df_p = pd.DataFrame(d["transactions"])
            df_p["Person"] = PEOPLE[key]["name"]
            dfs.append(df_p)

    if not dfs:
        st.info("Import transactions for Alec and/or Haley to see spending.")
        return

    df_all = pd.concat(dfs, ignore_index=True)
    df_all["Date"] = pd.to_datetime(df_all["Date"], errors="coerce")
    df_all = df_all.dropna(subset=["Date"])

    c1, c2 = st.columns(2)
    months     = sorted(df_all["Date"].dt.to_period("M").unique(), reverse=True)
    sel_month  = c1.selectbox("Month",  ["All"] + [str(m) for m in months], key="agg_mo")
    sel_person = c2.selectbox("Person", ["Both", "Alec", "Haley"],           key="agg_pr")

    df_f = df_all.copy()
    if sel_month  != "All":  df_f = df_f[df_f["Date"].dt.to_period("M").astype(str) == sel_month]
    if sel_person != "Both": df_f = df_f[df_f["Person"] == sel_person]

    expenses = df_f[df_f["Amount"] < 0].copy()
    expenses["Amount"] = expenses["Amount"].abs()

    alec_exp  = expenses[expenses["Person"] == "Alec"]["Amount"].sum()
    haley_exp = expenses[expenses["Person"] == "Haley"]["Amount"].sum()
    m1, m2, m3 = st.columns(3)
    m1.metric("Alec Spending",  f"${alec_exp:,.2f}")
    m2.metric("Haley Spending", f"${haley_exp:,.2f}")
    m3.metric("Total",          f"${alec_exp + haley_exp:,.2f}")

    if not expenses.empty:
        col1, col2 = st.columns(2)
        with col1:
            fig_cat = px.pie(
                expenses.groupby("Category")["Amount"].sum().reset_index(),
                values="Amount", names="Category", hole=0.42,
                title="Combined by Category",
                color_discrete_sequence=px.colors.qualitative.Set3,
            )
            st.plotly_chart(fig_cat, use_container_width=True)
        with col2:
            fig_p = px.pie(
                expenses.groupby("Person")["Amount"].sum().reset_index(),
                values="Amount", names="Person", hole=0.42,
                title="By Person",
                color_discrete_map={"Alec": "#2196F3", "Haley": "#E91E63"},
            )
            st.plotly_chart(fig_p, use_container_width=True)

        expenses["Month"] = expenses["Date"].dt.to_period("M").astype(str)
        fig_monthly = px.bar(
            expenses.groupby(["Month","Person"])["Amount"].sum().reset_index(),
            x="Month", y="Amount", color="Person", barmode="group",
            title="Monthly Spending by Person",
            color_discrete_map={"Alec": "#2196F3", "Haley": "#E91E63"},
        )
        st.plotly_chart(fig_monthly, use_container_width=True)

    st.subheader("All Transactions")
    st.dataframe(df_f.sort_values("Date", ascending=False), use_container_width=True, height=400)


# ── MAIN ──────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Personal Finance OS", layout="wide", page_icon="💰")

# ── LOGIN ─────────────────────────────────────────────────────────────────────
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("💰 Personal Finance OS")
    st.subheader("Please log in")
    col, _ = st.columns([1, 2])
    with col:
        pw = st.text_input("Password", type="password", key="login_pw")
        if st.button("Login"):
            if pw == "Kahlie":
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect password.")
    st.stop()

# ── AUTHENTICATED ─────────────────────────────────────────────────────────────
col_title, col_logout = st.columns([8, 1])
col_title.title("💰 Personal Finance OS")
if col_logout.button("Logout"):
    st.session_state.authenticated = False
    st.rerun()

top_tabs = st.tabs(["👤 Alec", "👤 Haley", "🏦 Aggregated"])

for tab, key in zip(top_tabs[:2], ("alec", "haley")):
    with tab:
        sub = st.tabs(["📥 Import", "📈 Net Worth", "💸 Spending", "🏦 Accounts", "⚙️ Settings"])
        with sub[0]: render_import(key)
        with sub[1]: render_networth(key)
        with sub[2]: render_spending(key)
        with sub[3]: render_accounts(key)
        with sub[4]: render_settings(key)

with top_tabs[2]:
    render_aggregated()
