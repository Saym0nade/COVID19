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

Полный end-to-end запуск одной командой:

```bash
python scripts/run_all.py
```

Тесты:

```bash
pip install -r requirements-dev.txt
python -m pytest -q tests
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
| `outputs/forecast_future.csv` | Только будущие прогнозы после последней даты датасета до 2027-01-01 |
| `outputs/forecast_recent_metrics.csv` | MAE/RMSE на недавнем holdout (последние 90 дней) |
| `outputs/forecast_recent_predictions.csv` | Предсказания моделей на недавнем holdout |
| `outputs/waves.csv` | Найденные волны (если создан анализом) |
| `outputs/sql/*.csv` | Результаты SQL-запросов (если созданы `run_sql.py`) |
| `outputs/eda_summary.json`, `outputs/outliers.csv`, `outputs/correlation.csv`, `outputs/timeseries.csv` | Результаты EDA и анализа временных рядов |
| `figures/*.png` | Статические графики анализа |

Дашборд содержит вкладки **Overview**, **World Map**, **Waves**, **Vaccination vs Mortality**, **Forecast** и **Data/SQL**. Фильтры `year`, `region`, `category` применяются к обзорным графикам, scatter-графику вакцинации и предпросмотру данных. **World Map** имеет собственный выбор метрики и недельный слайдер с Play/Pause: карта показывает per-million случаи/смерти, накопленные per-million показатели, вакцинацию и stringency по неделям. Необязательные файлы (`waves.csv`, `forecast_*.csv`, `outputs/sql/*.csv`) подхватываются автоматически, а при их отсутствии соответствующая вкладка показывает подсказку вместо ошибки.

Сравнение прогнозов включает 6 моделей: naive, seasonal naive, moving average, Linear Regression, библиотечный Holt-Winters/ETS и обучаемый PyTorch LSTM. Обучение заканчивается **2023-12-31**, оценка строится на полном ряду с **2024-01-01 до конца датасета** (2026-10-18), затем модели сравниваются с недавними реальными данными (последние 90 дней), и лучшая recent-модель строит future-прогноз **до 2027-01-01**. Top-5 стран выбираются среди стран с достаточным ненулевым target после 2023 года. Для графиков выбирается видимая модель с ненулевым прогнозом, а серии без видимого прогноза не отображаются, чтобы панели не были пустыми. Для CPU-only установки PyTorch можно использовать `pip install torch --index-url https://download.pytorch.org/whl/cpu`.

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
├── requirements-dev.txt
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
│   ├── run_forecast.py
│   ├── benchmark_storage.py
│   ├── smoke_test.py
│   └── run_all.py
├── tests/
│   ├── test_data_pipeline.py
│   ├── test_forecasting.py
│   ├── test_analytics_timeseries.py
│   └── test_app_map.py
├── docs/
│   ├── data_contract.md
│   ├── phase0_report.md
│   ├── integration_report.md
│   ├── review_checklist.md
│   ├── analysis_notes.md
│   ├── forecast_notes.md
│   ├── map_notes.md
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
- Интеграция дней 6: [docs/integration_report.md](docs/integration_report.md).
- Review checklist дня 7: [docs/review_checklist.md](docs/review_checklist.md).
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

Phase 1: завершена.

Day 6 (integration):

- [x] end-to-end runner `scripts/run_all.py`;
- [x] полный pipeline прогнан: данные → EDA → SQLite → SQL → forecast → benchmark → smoke test;
- [x] исправлены интерфейсы карты, SQLite waves и forecast recent/future;
- [x] dashboard HTTP 200;
- [x] отчёт об интеграции: `docs/integration_report.md`.

Day 7 (tests/review):

- [x] автоматические тесты в `tests/`;
- [x] `requirements-dev.txt` с pytest;
- [x] обработка ошибок в runners;
- [x] review checklist: `docs/review_checklist.md`;
- [x] черновик отчёта обновлён.

Текущее состояние forecast:

- обучение до 2023-12-31;
- полный backtest 2024-01-01 — 2026-10-18;
- recent holdout 90 дней;
- future-прогноз до 2027-01-01;
- 6 моделей, включая Holt-Winters и LSTM.

Следующие дни: финальный отчёт, презентация, freeze и защита.
