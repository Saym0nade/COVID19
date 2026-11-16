# ER diagram v1

SQLite schema used by `data/covid.db`. A country (`countries.iso_code`) owns zero or
more daily metric rows, vaccination rows, excess-mortality rows and detected-wave rows.

```mermaid
erDiagram
    countries ||--o{ covid_metrics : "has daily metrics"
    countries ||--o{ vaccinations : "has daily vaccinations"
    countries ||--o{ excess_mortality : "has daily excess mortality"
    countries ||--o{ waves : "has detected waves"

    countries {
        TEXT iso_code PK
        TEXT location
        TEXT continent
        REAL population
        REAL gdp_per_capita
        REAL human_development_index
    }

    covid_metrics {
        TEXT iso_code PK, FK
        TEXT date PK
        REAL new_cases
        REAL total_cases
        REAL new_deaths
        REAL total_deaths
        REAL new_cases_smoothed
        REAL new_deaths_smoothed
    }

    vaccinations {
        TEXT iso_code PK, FK
        TEXT date PK
        REAL people_vaccinated
        REAL people_fully_vaccinated
        REAL total_boosters
        REAL people_vaccinated_per_hundred
        REAL people_fully_vaccinated_per_hundred
    }

    excess_mortality {
        TEXT iso_code PK, FK
        TEXT date PK
        REAL excess_mortality
        REAL excess_mortality_cumulative
    }

    waves {
        INTEGER id PK
        TEXT iso_code FK
        INTEGER wave_number
        TEXT start_date
        TEXT end_date
        TEXT peak_date
        REAL peak_value
    }
```

## Keys and indexes

| Table | Primary key | Foreign key |
|---|---|---|
| `countries` | `iso_code` | — |
| `covid_metrics` | `(iso_code, date)` | `iso_code` → `countries.iso_code` |
| `vaccinations` | `(iso_code, date)` | `iso_code` → `countries.iso_code` |
| `excess_mortality` | `(iso_code, date)` | `iso_code` → `countries.iso_code` |
| `waves` | `id` (autoincrement) | `iso_code` → `countries.iso_code` |

Additional non-unique indexes exist on `date` and `(iso_code, date)` for the time-series
tables, and on `waves.iso_code`. The `waves` table is created by `sql/schema.sql` and is
populated later by the wave-detection step.
