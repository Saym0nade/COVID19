# Контракт данных и модулей

Версия: Phase 0.

Документ фиксирует, какие данные, поля, таблицы, выходные файлы и функции используют участники. Изменения контракта согласуются командой и отражаются здесь.

## 1. Источники данных

Используются два набора OWID:

1. **ETL catalog OWID** — основной, актуальный источник.
2. **Legacy GitHub OWID** — fallback, сохранён без удаления.

Документация каталога: https://docs.owid.io/projects/etl/api/covid/#download-data

### 1.1. ETL catalog, основной источник

| Файл | Строк | Размер, МБ |
|---|---:|---:|
| `data/raw/catalog/compact.csv` | 629 868 | 176.74 |
| `data/raw/catalog/cases_deaths.csv` | 617 520 | 180.21 |
| `data/raw/catalog/vaccinations_global.csv` | 203 057 | 62.69 |
| `data/raw/catalog/vaccinations_age.csv` | 74 142 | 2.91 |
| `data/raw/catalog/vaccinations_manufacturer.csv` | 888 360 | 29.44 |
| `data/raw/catalog/vaccinations_us.csv` | 54 628 | 4.36 |
| `data/raw/catalog/excess_mortality.csv` | 15 143 | 4.35 |
| `data/raw/catalog/excess_mortality_economist.csv` | 55 458 | 12.79 |
| `data/raw/catalog/hospital.csv` | 46 777 | 2.41 |
| `data/raw/catalog/testing.csv` | 106 788 | 5.29 |
| `data/raw/catalog/tracking_r.csv` | 185 683 | 9.97 |
| `data/raw/catalog/google_mobility.csv` | 784 944 | 31.19 |
| `data/raw/catalog/oxcgrt_policy.csv` | 202 760 | 20.81 |
| `data/raw/catalog/yougov_composite.csv` | 172 | 0.01 |
| `data/raw/catalog/covax.csv` | 29 | 0.01 |

Итого каталог: **3 865 329 строк**, **543.18 МБ**.

Основной файл каталога `compact.csv`: **629 868 строк**, **176.74 МБ**, **262 страны/территории**, период **2020-01-01 — 2026-10-18**.

Для каждого CSV также загружается `.meta.json` с метаданными.

### 1.2. Legacy GitHub, fallback

| Файл | Строк | Размер, МБ |
|---|---:|---:|
| `data/raw/owid-covid-data.csv` | 429 435 | 93.83 |
| `data/raw/vaccinations.csv` | 196 246 | 13.72 |
| `data/raw/vaccinations-by-age-group.csv` | 73 291 | 2.89 |
| `data/raw/vaccinations-by-manufacturer.csv` | 68 509 | 2.71 |
| `data/raw/excess_mortality.csv` | 18 855 | 2.61 |
| `data/raw/covid-testing-all-observations.csv` | 106 788 | 16.87 |
| `data/raw/covid-hospitalizations.csv` | 230 524 | 13.53 |
| `data/raw/who-covid-cases-deaths.csv` | 413 146 | 71.77 |

Итого legacy: **1 536 794 строки**, **217.93 МБ**.

### 1.3. Общий объём

| Набор | Файлов | Строк | МБ |
|---|---:|---:|---:|
| ETL catalog | 15 | 3 865 329 | 543.18 |
| Legacy GitHub | 8 | 1 536 794 | 217.93 |
| **Всего данных** | **23** | **5 402 123** | **761.11** |
| Метаданные каталога | 15 | — | 2.98 |

Требование «не менее 500 тыс. строк или 200 МБ» выполнено: основной файл каталога содержит более 500 тыс. строк, а совокупный набор — более 200 МБ.

Все сырые файлы не коммитятся. Загрузка:

```bash
python scripts/download_data.py
```

Только legacy:

```bash
python scripts/download_data.py --legacy-only
```

Только каталог:

```bash
python scripts/download_data.py --catalog-only
```

### 1.4. Приоритет и объединение

- Primary: ETL catalog.
- Fallback: legacy GitHub.
- Ключ объединения: `iso_code` + `date`.
- Тип объединения: outer merge.
- Значения каталога имеют приоритет.
- Если значение в каталоге отсутствует, используется legacy.
- Колонки, которые есть только в legacy, сохраняются.
- Колонки, которые есть только в каталоге, добавляются.
- Нормализация каталога: `code` → `iso_code`, `country` → `location`.

Реализация: `src/data_pipeline.py::merge_new_and_legacy`.

## 2. Sample для разработки

| Параметр | Catalog sample | Legacy sample |
|---|---|---|
| Путь | `data/sample/owid-catalog-sample.csv` | `data/sample/owid-covid-sample.csv` |
| Источник | `data/raw/catalog/compact.csv` | `data/raw/owid-covid-data.csv` |
| Правило | Каждый 8-й ряд | Каждый 8-й ряд |
| Строк | 78 734 | 53 680 |
| Колонок | 61 | 67 |
| Стран/территорий | 261 | 255 |
| Период | 2020-01-01 — 2026-10-18 | 2020-01-03 — 2024-08-13 |
| Роль | Основной sample | Fallback sample |

Catalog sample использует нормализованные имена `iso_code` и `location`. Оба sample коммитятся в Git и используются для параллельной разработки.

## 3. Канонические поля

| Поле | Тип | Описание |
|---|---|---|
| `iso_code` | string | Код страны/территории; ключ соединения |
| `continent` | string | Континент; основа для `region` |
| `location` | string | Название страны/территории |
| `date` | datetime / ISO date | Дата наблюдения |
| `total_cases` | float | Всего случаев |
| `new_cases` | float | Новые случаи |
| `new_cases_smoothed` | float | Сглаженные новые случаи |
| `total_deaths` | float | Всего смертей |
| `new_deaths` | float | Новые смерти |
| `new_deaths_smoothed` | float | Сглаженные новые смерти |
| `people_vaccinated` | float | Вакцинировано хотя бы одной дозой |
| `people_fully_vaccinated` | float | Полностью вакцинировано |
| `people_vaccinated_per_hundred` | float | Вакцинировано на 100 человек |
| `people_fully_vaccinated_per_hundred` | float | Полностью вакцинировано на 100 человек |
| `total_boosters` | float | Бустерные дозы |
| `population` | float | Население |
| `gdp_per_capita` | float | ВВП на душу населения |
| `human_development_index` | float | Индекс человеческого развития |

Ключ основного датасета: `iso_code` + `date`.

## 4. Производные поля

| Поле | Правило | Назначение |
|---|---|---|
| `year` | Год из `date` | Фильтр дашборда |
| `region` | `continent`, пустые значения → `Unknown` | Фильтр дашборда |
| `category` | Группа по `people_vaccinated_per_hundred`: `None`, `Low`, `Medium`, `High` | Фильтр дашборда |

Границы `category`:

| Категория | Условие |
|---|---|
| `None` | 0 или пропуск |
| `Low` | (0, 40) |
| `Medium` | [40, 70) |
| `High` | 70 и выше |

Если позже будет выбрана другая категоризация, изменить `src/analytics.py` и этот документ.

## 5. Правила анализа

- Для странового анализа исключать агрегаты: `iso_code`, начинающиеся с `OWID_`, а также `World`, континенты и группы доходов.
- Для глобального анализа использовать `location = 'World'` или агрегировать только страны.
- Даты хранить в ISO-формате `YYYY-MM-DD`.
- Числовые поля приводить к `float`/`int`, ошибки преобразования → `NaN`.
- Пропуски не заполнять автоматически без обоснования; решение фиксировать в отчёте.
- Отрицательные значения `new_cases`/`new_deaths` проверить и обработать отдельно.
- Дубликаты по `iso_code` + `date` удалять.
- Для прогноза использовать только time-based split: train — прошлое, test — будущее.

## 6. Схема SQLite

Файл схемы: `sql/schema.sql`.

| Таблица | Ключ | Назначение |
|---|---|---|
| `countries` | `iso_code` | Справочник стран и статических признаков |
| `covid_metrics` | `iso_code`, `date` | Случаи и смерти |
| `vaccinations` | `iso_code`, `date` | Вакцинация |
| `excess_mortality` | `iso_code`, `date` | Избыточная смертность |
| `waves` | `id` | Результаты обнаружения волн |

Связи:

- `countries.iso_code` → `covid_metrics.iso_code`;
- `countries.iso_code` → `vaccinations.iso_code`;
- `countries.iso_code` → `excess_mortality.iso_code`;
- `countries.iso_code` → `waves.iso_code`.

## 7. Выходные файлы

| Файл | Содержимое | Владелец |
|---|---|---|
| `outputs/eda_summary.json` | Описательная статистика, пропуски, типы | B |
| `outputs/outliers.csv` | Выбросы по IQR | B |
| `outputs/correlation.csv` | Корреляционная матрица | B |
| `outputs/timeseries.csv` | Resample и скользящие средние | B |
| `outputs/waves.csv` | Волны: страна, начало, конец, пик | B |
| `outputs/forecast_metrics.csv` | MAE, время, память по моделям | C |
| `outputs/forecast_predictions.csv` | Факт и прогноз: `split=test` на holdout и `split=future` после конца данных | C |
| `outputs/forecast_future.csv` | Только будущие прогнозы после последней даты датасета до 2027-01-01 | C |
| `outputs/forecast_recent_metrics.csv` | MAE/RMSE на недавнем holdout (последние 90 дней) | C |
| `outputs/forecast_recent_predictions.csv` | Предсказания на недавнем holdout | C |
| `data/processed/covid_merged.parquet` | Объединённые данные каталога и legacy | A |
| `data/processed/covid_clean.parquet` | Очищенные данные | A |
| `data/covid.db` | SQLite | A |

## 8. API модулей

| Модуль | Функции | Владелец |
|---|---|---|
| `src/data_pipeline.py` | `load_raw`, `load_catalog`, `normalize_catalog_compact`, `merge_new_and_legacy`, `load_merged_data`, `clean_data`, `optimize_dtypes`, `save_parquet`, `save_merged_parquet`, `chunked_summary` | A |
| `src/db.py` | `get_connection`, `init_db`, `load_dataframe`, `run_query` | A |
| `src/analytics.py` | `add_derived_fields`, `descriptive_stats`, `missing_report`, `detect_outliers_iqr`, `correlation_matrix` | B |
| `src/timeseries.py` | `resample_series`, `rolling_average`, `seasonal_decompose`, `detect_waves` | B |
| `src/forecasting.py` | `naive_forecast`, `seasonal_naive_forecast`, `moving_average_forecast`, `linear_regression_forecast`, `HoltWintersForecastModel`, `LSTMForecastModel`, `future_forecast`, `evaluate_mae`, `benchmark` | C |
| `src/visuals.py` | `line_chart`, `heatmap`, `boxplot` | B, C |
| `src/app.py` | `load_dashboard_data`, `build_app`, `main` | C |
| `src/main.py` | `show_status`, `main` | A |

## 9. Контракт прогноза

| Роль | Метод |
|---|---|
| Baseline 1 | Naive |
| Baseline 2 | Seasonal naive, лаг 7 дней |
| Подход 1 | Moving average, окно 7/14/28 |
| Подход 2 | Linear Regression |
| Готовая модель из библиотеки | Holt-Winters / Exponential Smoothing (`statsmodels`) |
| Обучаемая модель | PyTorch LSTM на скользящих окнах |

Обязательные метрики:

- MAE;
- время выполнения;
- потребление памяти.

Дополнительно: RMSE, график «факт vs прогноз» на полном периоде после отреза **2023-12-31** до конца датасета (2026-10-18), сравнение моделей на недавнем holdout (последние 90 дней) и future-прогноз лучшей recent-модели **до 2027-01-01**. Top-5 стран выбираются среди стран с достаточным ненулевым target после 2023 года. Future-строки имеют `split=future` и пустой `actual`; recent-строки — `split=recent`.

## 10. Контракт дашборда

- Технология: Dash + Plotly.
- Фильтры: `year`, `region`, `category`; при возможности `country`.
- Минимум 4–5 визуализаций, минимум 1 интерактивная Plotly.
- Данные для Phase 0: `data/sample/owid-catalog-sample.csv`; fallback — `data/sample/owid-covid-sample.csv`.
- Данные для финала: `data/covid.db`, `data/processed/covid_merged.parquet` или `data/processed/covid_clean.parquet`.

## 11. Ответственность и синхронизация

| Участник | Зона | Ветка |
|---|---|---|
| A | Data/DB | `feature/data` |
| B | EDA/Time Series | `feature/analytics` |
| C | Forecast/Dashboard | `feature/forecast-dashboard` |

Правила:

- merge в `main` не реже раза в 2 дня;
- перекрёстное ревью;
- изменения контракта — только после согласования и обновления этого файла.
