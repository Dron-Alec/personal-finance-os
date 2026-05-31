# Personal Finance OS — Project Context

## What this is
A Streamlit app for Alec & Haley to track personal finances: net worth over time,
spending habits from bank/credit card statements, and account balances.
Deployed on Streamlit Cloud, backed by Supabase.

## Accounts (Alec)

| Account | Type |
|---|---|
| Taxable Brokerage | Brokerage / Stocks |
| Roth IRA | Roth IRA |
| Roth 401k | 401k |
| Axos Savings | Savings |
| Axos Checking | Checking |
| Citi Checking | Checking |
| Coinbase | Crypto |
| Other Investments | Other |

**Note:** "Stocks / Brokerage" is an old name — consolidated into "Taxable Brokerage".
Alec has a Roth 401k only (no traditional 401k).

### May 12, 2026 balances (baseline, partially estimated, total = $50,912.33)

| Account | Balance |
|---|---|
| Taxable Brokerage | $21,112.33 |
| Axos Checking | $8,300.00 |
| Roth 401k | $7,000.00 |
| Roth IRA | $4,700.00 |
| Axos Savings | $3,000.00 |
| Citi Checking | $2,500.00 |
| Other Investments | $3,100.00 |
| Coinbase | $1,200.00 |

## Data entry workflow
- **Month-end balances** → Data Entry tab → updates accounts + creates net worth snapshot
- **Spending** → Data Entry tab → upload CSV statements as they arrive

## Supabase
- Project: AlecHaleyFinances (`lfqezqcymxcdseqcsbfh`, us-east-2)
- Tables: `transactions`, `nw_snapshots`, `accounts`, `settings`
- `accounts` has a unique constraint on `(person, name)` — saves use upsert

## Statement formats supported
Citi Checking, Citi Credit, Discover, Axos Checking, Axos Savings,
Wells Fargo Checking, Wells Fargo Credit, Chase Checking, Chase Credit,
Bank of America Checking, Bank of America Credit
