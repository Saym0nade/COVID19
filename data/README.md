# Данные

| Каталог/файл | Назначение | Коммитится |
|---|---|---|
| `raw/` | Legacy GitHub OWID, fallback | Нет, кроме `raw/README.md` |
| `raw/catalog/` | Актуальный ETL catalog OWID, основной источник | Нет |
| `sample/` | Sample для параллельной разработки | Да |
| `processed/` | Очищенные и объединённые Parquet/CSV | Нет |
| `manifest.json` | Метаданные, размеры, число строк, источники | Да |
| `covid.db` | SQLite с очищенными данными | Нет |

Основной датасет: `raw/catalog/compact.csv`.

Fallback: `raw/owid-covid-data.csv`.

Правило объединения: outer merge по `iso_code` + `date`; значения каталога приоритетны, legacy заполняет пропуски, old-only колонки сохраняются.

Sample:

- `sample/owid-catalog-sample.csv` — актуальный каталог, каждый 8-й ряд;
- `sample/owid-covid-sample.csv` — legacy GitHub, каждый 8-й ряд.

Полный контракт данных: `docs/data_contract.md`.
