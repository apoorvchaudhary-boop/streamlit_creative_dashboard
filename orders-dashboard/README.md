# Daily Orders Dashboard (Streamlit + Snowflake)

Live day-over-day bar chart of orders placed in the last 4 days.
Data is queried straight from Snowflake (no CSV) and cached for 30 minutes.

## Files
| File | Purpose |
|---|---|
| `streamlit_app.py` | App: Snowflake query → daily aggregate → bar chart |
| `requirements.txt` | Python deps installed by Streamlit Cloud |
| `.streamlit/secrets.toml.example` | Template for Snowflake credentials (not real values) |
| `.gitignore` | Keeps real secrets out of git |

## 1. Configure
Edit the config block at the top of `streamlit_app.py`:
`ORDERS_TABLE`, `ORDER_ID_COL`, `ORDER_TS_COL`, `SOURCE_TZ`.

## 2. Push to GitHub
```bash
git init
git add .
git commit -m "Daily orders Streamlit dashboard"
git branch -M main
git remote add origin https://github.com/<your-user>/orders-dashboard.git
git push -u origin main
```
Before pushing: `git status` should NOT list `.streamlit/secrets.toml`.

## 3. Deploy on Streamlit Community Cloud
1. Go to https://share.streamlit.io → sign in with GitHub → **Create app**.
2. Repo: `<your-user>/orders-dashboard`, branch `main`, file `streamlit_app.py`.
3. **Advanced settings → Secrets**: paste the filled-in contents of `secrets.toml.example`.
4. Deploy. Any later `git push` redeploys automatically.

## 4. Run locally (optional)
```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # fill in, never commit
streamlit run streamlit_app.py
```

## Snowflake read-only user (run once, by an admin)
```sql
CREATE ROLE STREAMLIT_READONLY_ROLE;
GRANT USAGE ON WAREHOUSE XS_WH TO ROLE STREAMLIT_READONLY_ROLE;
GRANT USAGE ON DATABASE ANALYTICS TO ROLE STREAMLIT_READONLY_ROLE;
GRANT USAGE ON SCHEMA ANALYTICS.PUBLIC TO ROLE STREAMLIT_READONLY_ROLE;
GRANT SELECT ON TABLE ANALYTICS.PUBLIC.ORDER_DETAILS TO ROLE STREAMLIT_READONLY_ROLE;
CREATE USER STREAMLIT_READONLY DEFAULT_ROLE = STREAMLIT_READONLY_ROLE
  RSA_PUBLIC_KEY = '<public key>';
GRANT ROLE STREAMLIT_READONLY_ROLE TO USER STREAMLIT_READONLY;
```
