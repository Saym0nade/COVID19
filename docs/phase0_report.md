# Phase 0: отчёт о выполнении

Дата: 2026-11-15.

## 1. Статус

Phase 0 завершена.

- [x] Создан репозиторий и структура каталогов.
- [x] Сохранены legacy GitHub-датасеты OWID.
- [x] Загружены актуальные ETL-каталоги OWID.
- [x] Проверен объём данных.
- [x] Реализовано объединение каталога и legacy с fallback.
- [x] Созданы sample-выборки для каталога и legacy.
- [x] Создан манифест данных с двумя источниками.
- [x] Зафиксирован контракт данных и модулей.
- [x] Создан каркас Dash-приложения.
- [x] Созданы SQL-схема и шаблоны запросов.
- [x] Подготовлены README и `requirements.txt`.

## 2. Данные

GitHub-данные OWID не обновлялись с 2024 года. Поэтому добавлен актуальный источник из ETL-каталога:

https://docs.owid.io/projects/etl/api/covid/#download-data

### 2.1. Основной источник: ETL catalog

- каталог: `data/raw/catalog/`;
- основной файл: `data/raw/catalog/compact.csv`;
- строк: 629 868;
- колонок: 61;
- размер: 176.74 МБ;
- стран/территорий: 262;
- период: 2020-01-01 — 2026-10-18.

Дополнительные файлы каталога:

| Файл | Строк | МБ |
|---|---:|---:|
| `cases_deaths.csv` | 617 520 | 180.21 |
| `vaccinations_global.csv` | 203 057 | 62.69 |
| `vaccinations_age.csv` | 74 142 | 2.91 |
| `vaccinations_manufacturer.csv` | 888 360 | 29.44 |
| `vaccinations_us.csv` | 54 628 | 4.36 |
| `excess_mortality.csv` | 15 143 | 4.35 |
| `excess_mortality_economist.csv` | 55 458 | 12.79 |
| `hospital.csv` | 46 777 | 2.41 |
| `testing.csv` | 106 788 | 5.29 |
| `tracking_r.csv` | 185 683 | 9.97 |
| `google_mobility.csv` | 784 944 | 31.19 |
| `oxcgrt_policy.csv` | 202 760 | 20.81 |
| `yougov_composite.csv` | 172 | 0.01 |
| `covax.csv` | 29 | 0.01 |

Итого каталог: **15 файлов**, **3 865 329 строк**, **543.18 МБ**. Для каждого CSV загружен `.meta.json`.

### 2.2. Fallback: legacy GitHub

- каталог: `data/raw/`;
- основной файл: `data/raw/owid-covid-data.csv`;
- строк: 429 435;
- колонок: 67;
- размер: 93.83 МБ;
- стран/территорий: 255;
- период: 2020-01-01 — 2024-08-14.

Legacy-файлы сохранены без удаления. Они используются как fallback, если в каталоге отсутствует поле или наблюдение.

Итого legacy: **8 файлов**, **1 536 794 строки**, **217.93 МБ**.

### 2.3. Общий объём

| Набор | Файлов | Строк | МБ |
|---|---:|---:|---:|
| ETL catalog | 15 | 3 865 329 | 543.18 |
| Legacy GitHub | 8 | 1 536 794 | 217.93 |
| **Всего данных** | **23** | **5 402 123** | **761.11** |
| Метаданные каталога | 15 | — | 2.98 |

Требование «не менее 500 тыс. строк или 200 МБ» выполнено: основной файл каталога содержит более 500 тыс. строк, а совокупный набор — более 200 МБ.

### 2.4. Правило объединения

- Primary: ETL catalog.
- Fallback: legacy GitHub.
- Ключ: `iso_code` + `date`.
- Тип: outer merge.
- Значения каталога приоритетны.
- Если значение каталога отсутствует, используется legacy.
- Old-only колонки сохраняются.
- New-only колонки добавляются.
- Нормализация каталога: `code` → `iso_code`, `country` → `location`.

Реализация: `src/data_pipeline.py::merge_new_and_legacy`.

## 3. Sample

| Параметр | Catalog sample | Legacy sample |
|---|---|---|
| Файл | `data/sample/owid-catalog-sample.csv` | `data/sample/owid-covid-sample.csv` |
| Источник | `data/raw/catalog/compact.csv` | `data/raw/owid-covid-data.csv` |
| Строк | 78 734 | 53 680 |
| Колонок | 61 | 67 |
| Стран/территорий | 261 | 255 |
| Период | 2020-01-01 — 2026-10-18 | 2020-01-03 — 2024-08-13 |
| Правило | Каждый 8-й ряд | Каждый 8-й ряд |

Catalog sample использует нормализованные имена `iso_code` и `location`. Дашборд по умолчанию читает catalog sample, legacy sample используется как fallback.

## 4. Принятые решения

1. Основной аналитический источник — ETL catalog OWID, `compact.csv`.
2. Legacy GitHub сохранён как fallback и не удаляется.
3. Объединение выполняется через outer merge по `iso_code` + `date`; каталог приоритетен, legacy заполняет пропуски, old-only колонки сохраняются.
4. Сырые данные не коммитятся; в Git хранятся sample, манифест и скрипты загрузки.
5. `region` = `continent`; пустые значения → `Unknown`.
6. `category` = группа по `people_vaccinated_per_hundred`: `None`, `Low`, `Medium`, `High`.
7. Для странового анализа исключаются агрегаты `OWID_*`, `World`, континенты и группы доходов.
8. Дашборд реализуется на Dash + Plotly.
9. Для SQL используется SQLite.
10. Прогноз сравнивается с baseline: naive и seasonal naive; подходы — moving average и Linear Regression; основная метрика — MAE.
11. Обнаружение волн: сглаженные новые случаи, 7-дневное скользящее среднее, порог и определение начала/конца волны; точный алгоритм реализует B в Phase 1.
12. Для прогноза используется time-based split без утечки данных.

## 5. Созданные артефакты

| Артефакт | Назначение |
|---|---|
| `README.md` | Описание проекта, данные, запуск, структура, роли |
| `PROJECT_PLAN.md` | Полный план и разбор требований |
| `requirements.txt` | Зависимости Python |
| `data/manifest.json` | Размеры, строки, источники, приоритет и правило объединения |
| `data/sample/owid-catalog-sample.csv` | Основной sample из актуального каталога |
| `data/sample/owid-covid-sample.csv` | Legacy sample |
| `scripts/download_data.py` | Загрузка legacy и catalog данных |
| `scripts/prepare_data.py` | Sample-выборки и манифест |
| `scripts/build_merged_dataset.py` | Сборка объединённого Parquet с fallback |
| `data/processed/covid_merged.parquet` | Объединённый набор: 632 788 строк, 67 колонок |
| `docs/data_contract.md` | Контракт данных, БД, выходных файлов и модулей |
| `src/config.py` | Пути, колонки, фильтры, catalog/legacy источники |
| `src/data_pipeline.py` | Пайплайн, нормализация каталога и merge с fallback |
| `src/db.py` | Каркас SQLite |
| `src/analytics.py` | Производные поля и каркас EDA |
| `src/timeseries.py` | Каркас временных рядов и волн |
| `src/forecasting.py` | Каркас прогноза |
| `src/visuals.py` | Базовые Plotly-графики |
| `src/app.py` | Каркас Dash-дашборда с фильтрами |
| `src/main.py` | Консольное меню статуса |
| `sql/schema.sql` | Нормализованная схема SQLite |
| `sql/queries.sql` | 9 SQL-запросов с JOIN, CTE и оконными функциями |
| `report/report.md` | Каркас отчёта |
| `figures/`, `outputs/`, `presentation/` | Каталоги для результатов |

## 6. Проверки Phase 0

- `python scripts/prepare_data.py` — успешно, манифест создан.
- Объём данных — подтверждён: 23 файла, 5 402 123 строки, 761.11 МБ.
- Catalog sample — создан: 78 734 строки, 261 территория, период до 2026-10-18.
- Legacy sample — сохранён: 53 680 строк, 255 территорий.
- `python -m py_compile src/*.py scripts/*.py` — успешно.
- `python src/main.py` — консольное меню работает.
- SQL-схема — подготовлена; 9 запросов проверены на in-memory SQLite.
- Дашборд — HTTP-проверка вернула 200, используются данные каталога.
- Merge — проверен: new-only колонки добавляются, old-only сохраняются, значения каталога приоритетны, пустые значения каталога заполняются legacy.
- Полный merge — собран `data/processed/covid_merged.parquet`: 632 788 строк, 67 колонок, период до 2026-10-18, 163 344 строки после 2024 года.
- Пайплайн — проверен на sample: Parquet сохранён, SQLite создана, запрос выполнен.
- Зависимости из `requirements.txt` установлены в `.venv`.

## 7. Следующие шаги

### A: Data/DB

- реализовать `clean_data` с обоснованными правилами;
- реализовать `optimize_dtypes` с замерами;
- собрать объединённый датасет через `load_merged_data`;
- сохранить `data/processed/covid_merged.parquet`;
- загрузить данные в SQLite;
- построить ER-диаграмму;
- проверить и адаптировать 8+ SQL-запросов;
- выгрузить результаты запросов в Pandas;
- замерить CSV vs Parquet по времени и памяти.

### B: EDA/Time Series

- описательная статистика и пропуски;
- выбросы IQR/boxplot;
- корреляционная матрица и heatmap;
- resample, rolling average, сезонная декомпозиция;
- обнаружение волн и `outputs/waves.csv`;
- 4–5 визуализаций, минимум одна интерактивная.

### C: Forecast/Dashboard

- реализовать baseline naive/seasonal naive;
- реализовать moving average и Linear Regression;
- MAE, время, память;
- time-based split без утечки;
- подключить объединённые данные к дашборду;
- добавить интерактивные Plotly-графики;
- финализировать README и `requirements.txt`.

## 8. Открытые вопросы

- Утверждена ли тема 3 и совокупный набор OWID у преподавателя.
- Нужно ли фиксировать версию/дату среза каталога в отчёте.
- Достаточно ли `statsmodels` и `scikit-learn` или нужны только стандартные библиотеки.
- Язык отчёта и презентации.
- Тайминг защиты.
