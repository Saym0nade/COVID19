# COVID-19 Global Dynamics

## Титульный лист

- Дисциплина: Programming for Data Analysis and Database
- Программа: Applied Artificial Intelligence, магистратура
- Кластер: Cluster 1: Exploratory Analytics, Time Series & Dashboards
- Тема: 3. COVID-19 Global Dynamics
- Команда: Alen Smailov, Yermukhamet Akbet, Sayan Aukatov
- Дата: TBD

## 1. Вклад участников

| Роль | Вклад |
|---|---|
| A: Data/DB | Данные OWID, merge catalog + legacy, Parquet, SQLite, ER, 9 SQL-запросов, benchmark |
| B: EDA/Time Series | EDA, пропуски, выбросы, корреляции, resample, rolling, сезонная декомпозиция, волны, static figures |
| C: Forecast/Dashboard | Прогнозы, baseline, Holt-Winters, LSTM, MAE/время/память, Dash-дашборд, World Map, README |
| Все | Интеграция, smoke-тесты, review, отчёт, презентация |

Перед сдачей заменить роли A/B/C на имена участников в соответствии с фактическим вкладом.

## 2. Постановка задачи

Цель проекта — проанализировать динамику COVID-19 по странам: волны заболеваемости, вакцинацию, смертность, корреляции и краткосрочный/среднесрочный прогноз. Результаты оформлены в виде EDA, SQL-выборок, статических визуализаций и интерактивного Dash-дашборда.

## 3. Данные

Используются два источника OWID:

1. **ETL catalog** — основной, актуальный источник;
2. **legacy GitHub** — fallback, сохранён без удаления.

Источники и объём:

| Набор | Файлов | Строк | МБ |
|---|---:|---:|---:|
| ETL catalog | 15 | 3 865 329 | 543.18 |
| Legacy GitHub | 8 | 1 536 794 | 217.93 |
| **Всего** | **23** | **5 402 123** | **761.11** |

Основной каталог: `data/raw/catalog/compact.csv`, период до `2026-10-18`. Legacy: `data/raw/owid-covid-data.csv`, период до `2024-08-14`.

Merge:

- outer merge по `iso_code` + `date`;
- значения каталога приоритетны;
- legacy заполняет пропуски и сохраняет old-only колонки;
- `code` → `iso_code`, `country` → `location`.

Итоговый merged Parquet:

- **624 273 строки × 67 колонок**;
- период `2020-01-01 — 2026-10-18`;
- 211.73 МБ в памяти после оптимизации.

## 4. Аудит качества данных и очистка

- приведение `date` к datetime;
- приведение числовых колонок к numeric;
- удаление дубликатов по `iso_code` + `date` с сохранением последней записи;
- сохранение строк без `iso_code` при merge;
- исключение агрегатов `OWID_*`, `World`, континентов и групп доходов из странового анализа;
- forward-fill для cumulative/coverage метрик на карте;
- для flow-метрик fill не применяется.

Data profile: `outputs/data_profile.json`.

## 5. Архитектура и модули

| Модуль | Назначение |
|---|---|
| `src/data_pipeline.py` | загрузка, merge, очистка, оптимизация типов, Parquet |
| `src/db.py` | SQLite connection, schema init, load, query |
| `src/analytics.py` | производные поля, EDA, пропуски, выбросы, корреляции |
| `src/timeseries.py` | resample, rolling, seasonal decomposition, waves |
| `src/forecasting.py` | baseline, moving average, Linear Regression, Holt-Winters, LSTM |
| `src/visuals.py` | статические графики |
| `src/app.py` | Dash-дашборд, карта, вкладки, callbacks |
| `scripts/*` | воспроизводимые пайплайны и runners |

## 6. Схема базы данных и ER-диаграмма

SQLite таблицы:

- `countries`;
- `covid_metrics`;
- `vaccinations`;
- `excess_mortality`;
- `waves`.

ER-диаграмма: `docs/er_diagram.md`.

Заполнение:

| Таблица | Строк |
|---|---:|
| `countries` | 257 |
| `covid_metrics` | 610 948 |
| `vaccinations` | 85 830 |
| `excess_mortality` | 13 926 |
| `waves` | 882 |

## 7. EDA

- описательная статистика;
- отчёт по пропускам;
- типы признаков;
- IQR-выбросы (750 информативных строк после ограничения);
- корреляционная матрица (14 признаков, 91 пара);
- 5 статических визуализаций в `figures/`.

Ключевые графики:

- `figures/global_cases_deaths.png`;
- `figures/vaccination_rollout_by_region.png`;
- `figures/waves_chart.png`;
- `figures/outliers_boxplot.png`;
- `figures/correlation_heatmap.png`.

## 8. Временные ряды и волны

- недельный resample;
- rolling averages 7/14/28;
- сезонная декомпозиция (additive, period=7);
- волны: rolling average + `scipy.signal.find_peaks`;
- параметры: окно 7 дней, distance 30 дней, prominence 5%, onset 10%;
- результат: **882 волны** по **231 стране** (`outputs/waves.csv`).

## 9. Корреляционный анализ

Матрица корреляций построена по 14 признакам, включая случаи/смерти на миллион, вакцинацию, GDP, HDI, плотность населения, возраст, stringency, reproduction rate и hospital beds. Результаты: `outputs/correlation.csv`, `figures/correlation_heatmap.png`.

## 10. Прогнозирование и сравнение с baseline

Серии:

- `global`;
- top-5 стран с данными после 2023: `CHN`, `IND`, `BRA`, `ITA`, `GBR`.

Модели:

- naive;
- seasonal naive;
- moving average;
- Linear Regression;
- Holt-Winters/ETS (библиотечная модель `statsmodels`);
- LSTM (PyTorch, обучается с нуля).

Оценка:

- обучение до `2023-12-31`;
- полный backtest `2024-01-01 — 2026-10-18` (1 022 дня);
- recent holdout: последние 90 дней;
- future forecast: `2026-10-19 — 2027-01-01`.

Метрики:

- MAE;
- RMSE;
- fit time;
- predict time;
- peak memory.

Глобальный ряд:

| Модель | MAE |
|---|---:|
| LSTM | 17 203 |
| Holt-Winters | 24 894 |
| Naive | 32 571 |
| Seasonal naive | 33 184 |
| Moving average | 33 184 |
| Linear Regression | 602 245 |

Лучшая модель на recent holdout для `global` — Holt-Winters, MAE ≈ 579. Future-прогноз строится по лучшей recent-модели каждой серии.

## 11. Дашборд

Dash-вкладки:

- Overview;
- World Map;
- Waves;
- Vaccination vs Mortality;
- Forecast;
- Data/SQL.

World Map:

- недельный choropleth;
- метрики per-million, вакцинация, stringency;
- slider + Play/Pause;
- 355 недель, около 83k country-week строк.

Forecast:

- таблица полной post-2023 оценки;
- график forecast vs actual;
- recent holdout comparison;
- future forecast до 2027-01-01.

## 12. Результаты и обсуждение

- Каталог OWID даёт более свежие данные, чем legacy GitHub;
- merge с fallback сохраняет старые поля и покрытие;
- SQLite и 9 SQL-запросов демонстрируют JOIN, GROUP BY/HAVING, CTE и window functions;
- временные ряды показывают волны и различия по странам;
- Holt-Winters и LSTM улучшают naive на глобальном ряду, но LSTM нестабилен на части стран;
- recent holdout даёт более практичный выбор модели для future-прогноза, чем длинный backtest;
- Parquet быстрее CSV в **6.53x** и занимает значительно меньше места.

## 13. Ограничения

- пропуски в части стран и метрик;
- top-5 ограничен странами с данными после 2023;
- LSTM не tuning и может сильно уступать статистическим моделям;
- long-horizon backtest имеет большие ошибки;
- вакцинация и stringency покрыты хуже, чем случаи/смерти;
- World Map использует недельную агрегацию и forward-fill для cumulative/coverage метрик.

## 14. Выводы

Проект демонстрирует полный цикл работы с данными: загрузка и merge источников, очистка, SQL, EDA, временные ряды, обнаружение волн, сравнение нескольких прогнозных моделей и интерактивный дашборд. Основные требования кластера и технические требования 1–11 покрыты.

## 15. Ссылки

- OWID COVID-19 data: https://github.com/owid/covid-19-data
- OWID ETL catalog: https://docs.owid.io/projects/etl/api/covid/#download-data
- Plotly: https://plotly.com/python/
- Dash: https://dash.plotly.com/
- statsmodels: https://www.statsmodels.org/
- PyTorch: https://pytorch.org/

## Приложение A. SQL-запросы

См. `sql/queries.sql`, `docs/sql_notes.md`, `outputs/sql/*.csv`.

## Приложение B. Таблицы метрик

См. `outputs/forecast_metrics.csv`, `outputs/forecast_recent_metrics.csv`, `outputs/benchmark_data.json`.

## Приложение C. Скриншоты

TBD на днях 8–9.
