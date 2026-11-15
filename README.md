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
python scripts/download_data.py
python scripts/prepare_data.py
python scripts/build_merged_dataset.py
python src/main.py
python -m src.app
```

`build_merged_dataset.py` создаёт `data/processed/covid_merged.parquet` — объединённый набор из каталога и legacy с fallback.

Дашборд открывается по адресу, который выведет Dash, обычно `http://127.0.0.1:8050`.

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
│   └── build_merged_dataset.py
├── docs/
│   ├── data_contract.md
│   └── phase0_report.md
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
- [x] собран `data/processed/covid_merged.parquet` из 632 788 строк;
- [x] созданы sample-выборки для каталога и legacy;
- [x] создан манифест данных с двумя источниками;
- [x] зафиксирован контракт данных и модулей;
- [x] создан каркас Dash-приложения;
- [x] созданы SQL-схема и шаблоны запросов;
- [x] подготовлены README и requirements.

Следующий этап — Phase 1: реализация пайплайна, EDA, SQL-запросов, прогноза и дашборда.
