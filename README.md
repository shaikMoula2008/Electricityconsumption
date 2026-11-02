# Electricity Consumption Analysis System

A Flask + MySQL REST API that stores meter readings, calculates consumption with Pandas and NumPy, summarizes usage by month and year, flags unusually high usage, validates readings, and draws usage charts and graphs with Matplotlib.

## Setup

Requirements: Python 3.10+, MySQL 8.0.16+, Git.

1. Clone the repository and open the folder.
2. Create and activate a virtual environment:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   ```
3. Install the packages:
   ```
   pip install -r requirements.txt
   ```
4. Create a file named `.env` in the project folder with your MySQL details and the settings below. Never commit this file.
   ```
   NAME_1=your_value
   NAME_2=your_value
   HIGH_USAGE_FACTOR=1.5
   MAX_GAP_DAYS=45
   METER_MAX_KWH=100000
   ```
5. Create the empty database:
   ```
   python init_db.py
   ```
6. Start the server:
   ```
   python app.py
   ```
   The API runs at http://127.0.0.1:5000. Check http://127.0.0.1:5000/health.

The database starts empty. To try the project with example data, run `sql/sample_data.sql` in MySQL Workbench (3 consumers, 3 meters, 6 readings each).

## Units and assumptions

- All readings and consumption are in kilowatt-hours (kWh). A reading is a cumulative meter total on a date.
- Consumption of a period = later reading minus earlier reading.
- A reading lower than the previous one is accepted but flagged as a possible meter reset or rollover. The affected period is excluded from totals and listed in the validation report. A drop from within 10% of the meter's maximum (`METER_MAX_KWH`) is labelled a rollover.
- A period counts toward the month or year in which it starts.
- High usage means a period above the meter's average valid consumption multiplied by a factor (default 1.5, set by `HIGH_USAGE_FACTOR`).
- The project uses sample readings. All figures are analytical estimates and do not replace official billing calculations.

## Configuration (.env)

| Variable | Default | Meaning |
|---|---|---|
| `HIGH_USAGE_FACTOR` | 1.5 | High-usage threshold factor |
| `MAX_GAP_DAYS` | 45 | Longest normal gap between readings |
| `METER_MAX_KWH` | 100000 | Meter dial maximum, used to tell rollovers from resets |

## Endpoints

| Method | URL | Purpose |
|---|---|---|
| POST, GET | `/consumers` | Create, list consumers |
| GET, PUT, DELETE | `/consumers/<id>` | Read, update, delete one consumer |
| POST, GET | `/meters` | Create, list meters |
| GET, PUT, DELETE | `/meters/<id>` | Read, update, delete one meter |
| POST, GET | `/readings` | Record readings, list them (`?meter_id=` filter) |
| GET, PUT, DELETE | `/readings/<id>` | Read, update, delete one reading |
| GET | `/analysis/consumption/<meter_id>` | Consumption per period |
| GET | `/analysis/summary/<meter_id>?level=monthly\|yearly` | Monthly or yearly totals |
| GET | `/analysis/high-usage/<meter_id>?factor=1.5` | Periods above average × factor |
| GET | `/analysis/change/<meter_id>` | Change vs previous period (kWh and %) |
| GET | `/validation` | Reading-validation report for all meters |
| GET | `/validation/<meter_id>` | Reading-validation report for one meter (`?max_gap_days=`) |
| GET | `/charts/trend/<meter_id>.png` | Bar chart of monthly usage with high-usage marks |
| GET | `/charts/compare.png` | Bar chart comparing total consumption across consumers |
| GET | `/charts/readings/<meter_id>.png` | Line graph of cumulative readings, with resets marked |
| GET | `/charts/line/<meter_id>.png` | Line graph of monthly consumption with the high-usage limit |
| GET | `/charts/compare-lines.png` | Line graph comparing monthly consumption across meters |

## Expected outputs

| Output | Where it comes from |
|---|---|
| Monthly consumption report | `/analysis/summary/<meter_id>` |
| High-usage list | `/analysis/high-usage/<meter_id>` |
| Usage charts and graphs | `/charts/trend/<meter_id>.png`, `/charts/compare.png`, `/charts/readings/<meter_id>.png`, `/charts/line/<meter_id>.png`, `/charts/compare-lines.png` |
| Reading-validation report | `/validation/<meter_id>` |

## Example

```
Invoke-RestMethod -Uri http://127.0.0.1:5000/readings -Method Post -ContentType "application/json" -Body '{"meter_id":1,"reading_date":"2026-07-01","cumulative_kwh":1900}'
```

## Project layout

```
app.py            Flask app and blueprint registration
db.py             Database connection
utils.py          Shared error helper
init_db.py        Creates the empty database from sql/schema.sql
requirements.txt  Python packages
routes/           consumers.py, meters.py, readings.py, analysis.py,
                  validation.py, charts.py
sql/              schema.sql, sample_data.sql
docs/             er_diagram.png, data_dictionary.md, synopsis.md, test_report.md
```

## Documentation

- [Data dictionary](docs/data_dictionary.md)
- [Synopsis](docs/synopsis.md)
- [Test report](docs/test_report.md)
- ER diagram: `docs/er_diagram.png`