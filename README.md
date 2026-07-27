# Mercado Libre ETL Challenge

📄 Full documentation available in:

- 🇬🇧 [English](docs/en/README.md)
- 🇪🇸 [Español](docs/es/README.md)
- 🇧🇷 [Português](docs/pt/README.md)

---

Quick start:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # fill in your credentials
psql -U <user> -d mercadolibre_etl -f ddl/create_tables.sql
python src/main.py
```