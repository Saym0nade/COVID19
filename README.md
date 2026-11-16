# COVID-19 Global Dynamics

Итоговый мини-проект по дисциплине Programming for Data Analysis and Database.

| Параметр | Значение |
|---|---|
| Кластер | Cluster 1: Exploratory Analytics, Time Series & Dashboards |
| Тема | 3. COVID-19 Global Dynamics |
| Данные | Our World in Data: ETL catalog (основной источник) + legacy GitHub (fallback) |
| Стек | Python 3.x, Pandas, Plotly, Dash |
| SQL | SQLite |
| Команда | Alen Smailov, Yermukhamet Akbet, Sayan Aukatov |
| Статус | Phase 0 завершена: репозиторий, данные, sample, контракты и каркас приложения |

## Описание проекта

Проект анализирует динамику COVID-19 по странам: волны заболеваемости, вакцинацию, смертность, корреляции и краткосрочный прогноз. Результаты оформляются в виде аналитических выводов, SQL-выборок, визуализаций и интерактивного дашборда.

План работ и разбор требований находятся в [PROJECT_PLAN.md](PROJECT_PLAN.md).

## Данные

GitHub-датасеты OWID не обновлялись с 2024 года. Поэтому основным источником теперь является актуальный ETL-каталог OWID:

- документация: https://docs.owid.io/projects/etl/api/covid/#download-data;
- каталог: `data/raw/catalog/`;
- основной файл: `data/raw/catalog/compact.csv`;
- 629 868 строк, 61 колонка, 176.74 МБ;
- 262 страны/территории;
- период: 2020-01-01 — 2026-10-18.

Legacy GitHub-данные сохранены как fallback:

- каталог: `data/raw/`;
- основной файл: `data/raw/owid-covid-data.csv`;
- 429 435 строк, 67 колонок, 93.83 МБ;
- 255 стран/территорий;
- период: 2020-01-01 — 2024-08-14.

Правило объединения:

- внешнее объединение по `iso_code` + `date`;
- значения из каталога имеют приоритет;
- значения из legacy GitHub заполняют пропуски;
- колонки, которые есть только в legacy, сохраняются;
- колонки, которые есть только в каталоге, добавляются.

Объём данных:

| Набор | Файлов | Строк | МБ |
|---|---:|---:|---:|
| Legacy GitHub | 8 | 1 536 794 | 217.93 |
| ETL catalog | 15 | 3 865 329 | 543.18 |
| **Всего данных** | **23** | **5 402 123** | **761.11** |
| Метаданные каталога | 15 | — | 2.98 |

Требование по объёму выполнено: основной файл каталога содержит более 500 тыс. строк, а совокупный набор — более 200 МБ.

Сырые данные не коммитятся в Git. Инструкция по загрузке: [data/raw/README.md](data/raw/README.md).

Sample-выборки для параллельной разработки:

| Sample | Строк | Колонок | Период | Назначение |
|---|---:|---:|---|---|
| `data/sample/owid-catalog-sample.csv` | 78 734 | 61 | 2020-01-01 — 2026-10-18 | Основной sample из каталога |
| `data/sample/owid-covid-sample.csv` | 53 680 | 67 | 2020-01-03 — 2024-08-13 | Legacy sample |

В sample каталога колонки `code` и `country` переименованы в `iso_code` и `location` для совместимости с legacy-контрактом. Шаг выборки — каждый 8-й ряд.

Манифест с размерами, числом строк и источниками: `data/manifest.json`.

## Быстрый старт

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/download_data.py        # каталог OWID + legacy fallback
python scripts/prepare_data.py         # sample и manifest
python scripts/build_merged_dataset.py # covid_merged.parquet
python scripts/run_analysis.py         # EDA, волны и графики
python scripts/build_sqlite.py         # data/covid.db (включая waves.csv, если есть)
python scripts/run_sql.py              # outputs/sql/*.csv
python scripts/run_forecast.py         # прогноз: global + top-5 стран
python -m src.app                      # интерактивный дашборд
```

`download_data.py` использует актуальный ETL-каталог OWID как основной источник и legacy GitHub-датасеты как fallback. `build_merged_dataset.py` создаёт `data/processed/covid_merged.parquet` — объединённый набор из каталога и legacy с приоритетом каталога.

Дашборд открывается по адресу, который выведет Dash, обычно `http://127.0.0.1:8050`. Если объединённый parquet ещё не собран, приложение автоматически использует `data/sample/owid-catalog-sample.csv`, затем legacy sample.

## Ожидаемые результаты

Основные артефакты:

| Путь | Содержимое |
|---|---|
| `data/processed/covid_merged.parquet` | Объединённые данные каталога и legacy |
| `data/covid.db` | SQLite-база с таблицами `countries`, `covid_metrics`, `vaccinations`, `excess_mortality`, `waves` |
| `outputs/forecast_metrics.csv` | MAE, RMSE, время и память по 6 моделям для `global` и `country:<ISO>` |
| `outputs/forecast_predictions.csv` | Факт и прогноз на тестовом окне (`split=test`) и после конца датасета (`split=future`) |
| `outputs/forecast_future.csv` | Только будущие прогнозы после последней даты датасета |
| `outputs/waves.csv` | Найденные волны (если создан анализом) |
| `outputs/sql/*.csv` | Результаты SQL-запросов (если созданы `run_sql.py`) |
| `outputs/eda_summary.json`, `outputs/outliers.csv`, `outputs/correlation.csv`, `outputs/timeseries.csv` | Результаты EDA и анализа временных рядов |
| `figures/*.png` | Статические графики анализа |

Дашборд содержит вкладки **Overview**, **Waves**, **Vaccination vs Mortality**, **Forecast** и **Data/SQL**. Фильтры `year`, `region`, `category` применяются к обзорным графикам, scatter-графику вакцинации и предпросмотру данных. Необязательные файлы (`waves.csv`, `forecast_*.csv`, `outputs/sql/*.csv`) подхватываются автоматически, а при их отсутствии соответствующая вкладка показывает подсказку вместо ошибки.

Сравнение прогнозов включает 6 моделей: naive, seasonal naive, moving average, Linear Regression, библиотечный Holt-Winters/ETS и обучаемый PyTorch LSTM. Обучение заканчивается **2023-12-31**, а оценка и прогноз строятся на полном ряду с **2024-01-01 до конца датасета** (2026-10-18); после этого добавляется future-прогноз на 30 дней. Top-5 стран выбираются среди стран с достаточным ненулевым target после 2023 года. Для графиков выбирается видимая модель с ненулевым прогнозом, а серии без видимого прогноза не отображаются, чтобы панели не были пустыми. Для CPU-only установки PyTorch можно использовать `pip install torch --index-url https://download.pytorch.org/whl/cpu`.

Если зависимости ещё не установлены, sample и манифест можно пересобрать отдельно:

```bash
python3 scripts/prepare_data.py
```

## Структура репозитория

```text
.
├── README.md
├── PROJECT_PLAN.md
├── requirements.txt
├── data/
│   ├── raw/                 # legacy GitHub, не коммитится
│   │   └── catalog/         # актуальный ETL catalog, не коммитится
│   ├── sample/              # sample для разработки, коммитится
│   ├── processed/           # очищенные и объединённые данные
│   ├── manifest.json
│   └── covid.db             # SQLite, создаётся локально
├── outputs/                 # результаты анализа
├── src/
│   ├── config.py
│   ├── data_pipeline.py
│   ├── db.py
│   ├── analytics.py
│   ├── timeseries.py
│   ├── forecasting.py
│   ├── visuals.py
│   ├── app.py
│   └── main.py
├── sql/
│   ├── schema.sql
│   └── queries.sql
├── scripts/
│   ├── download_data.py
│   ├── prepare_data.py
│   ├── build_merged_dataset.py
│   ├── build_sqlite.py
│   ├── run_sql.py
│   ├── run_analysis.py
│   └── run_forecast.py
├── docs/
│   ├── data_contract.md
│   ├── phase0_report.md
│   ├── analysis_notes.md
│   ├── forecast_notes.md
│   ├── sql_notes.md
│   └── er_diagram.md
├── figures/
├── report/
│   └── report.md
└── presentation/
```

## Роли команды

| Роль | Зона ответственности |
|---|---|
| A: Data/DB | Пайплайн данных, оптимизация типов, Parquet, SQLite, ER, 8+ SQL-запросов |
| B: EDA/Time Series | EDA, пропуски, выбросы, корреляции, resample, rolling, сезонная декомпозиция, волны |
| C: Forecast/Dashboard | Сравнение прогнозов, MAE, дашборд, интерактивные Plotly-графики, README, requirements |
| Все | Интеграция, ревью, отчёт, презентация, защита |

## Контракты

- Данные, поля, таблицы и выходные файлы: [docs/data_contract.md](docs/data_contract.md).
- Результаты фазы 0: [docs/phase0_report.md](docs/phase0_report.md).
- Полный план: [PROJECT_PLAN.md](PROJECT_PLAN.md).

## Текущий статус

Phase 0:

- [x] репозиторий и структура каталогов;
- [x] legacy GitHub-датасеты OWID сохранены;
- [x] актуальные ETL-каталоги OWID загружены;
- [x] подтверждён требуемый объём данных;
- [x] реализовано объединение каталога и legacy с fallback;
- [x] собран `data/processed/covid_merged.parquet` из 624 273 строк;
- [x] созданы sample-выборки для каталога и legacy;
- [x] создан манифест данных с двумя источниками;
- [x] зафиксирован контракт данных и модулей;
- [x] создан каркас Dash-приложения;
- [x] созданы SQL-схема и шаблоны запросов;
- [x] подготовлены README и requirements.

Sync-1: завершён (ветки участников сведены с main).

Phase 1 (в процессе):

- [x] пайплайн данных: merged parquet, SQLite, SQL-запросы, EDA и временные ряды;
- [x] прогноз `global` и top-5 стран по `total_cases` с time-based split и горизонтом 30 дней;
- [x] дашборд с фильтрами и вкладками Overview / Waves / Vaccination vs Mortality / Forecast / Data/SQL;
- [x] README, requirements и документация по прогнозу обновлены;
- [ ] финальная интеграция, отчёт и презентация.
