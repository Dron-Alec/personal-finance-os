# Personal Finance OS

A personal finance dashboard built with Streamlit. Track net worth over time, import bank/credit card statements, monitor spending by category, and manage account balances — all in one place.

## Features

- **Transaction import** — upload CSV exports from Citi, Discover, Axos, Wells Fargo, Chase, Bank of America, and more
- **Spending analysis** — automatic categorization, pie/bar charts, monthly breakdowns, and re-categorization tools
- **Net worth tracking** — snapshot-based history with a chart and quarterly targets
- **Account balances** — track checking, savings, crypto, 401k, Roth IRA, taxable brokerage, and more
- **Manual balance entry** — backfill missed months by entering all account balances for a specific date in one form
- **Multi-person support** — separate views for Alec and Haley, plus a combined aggregated view
- **Password-protected** — simple login gate to keep data private

## Setup

```bash
pip install -r requirements.txt
streamlit run app.py
```

The app runs locally at `http://localhost:8501`.

## Data

All data is stored locally in the `data/` directory as JSON files (`alec.json`, `haley.json`). Nothing is sent to any external service.

## Importing Transactions

1. Export a CSV from your bank's website
2. Go to **Import** tab → select the matching statement format → upload the file
3. Duplicate transactions are automatically skipped on re-import

## Backfilling Missing Months

Go to **Accounts → 📅 Manual Balance Entry**, pick the date (e.g. end of a past month), enter balances for each account, and click **Save Entry**. This creates a net worth snapshot for that date and optionally updates current account records.
