# Сырые данные

Каталог содержит два набора Our World in Data. Файлы не коммитятся в Git из-за размера.

## Источники

| Источник | Каталог | Роль |
|---|---|---|
| ETL catalog OWID | `data/raw/catalog/` | Основной, актуальный |
| Legacy GitHub OWID | `data/raw/` | Fallback, сохранён без удаления |

Документация каталога: https://docs.owid.io/projects/etl/api/covid/#download-data

GitHub-данные не обновлялись с 2024 года. Они сохранены, потому что могут содержать поля или наблюдения, отсутствующие в каталоге.

## Загрузка

Оба источника:

```bash
python scripts/download_data.py
```

Только legacy GitHub:

```bash
python scripts/download_data.py --legacy-only
```

Только актуальный ETL catalog:

```bash
python scripts/download_data.py --catalog-only
```

Принудительная повторная загрузка:

```bash
python scripts/download_data.py --force
```

## Legacy GitHub

| Файл | Источник |
|---|---|
| `owid-covid-data.csv` | https://raw.githubusercontent.com/owid/covid-19-data/master/public/data/owid-covid-data.csv |
| `vaccinations.csv` | https://raw.githubusercontent.com/owid/covid-19-data/master/public/data/vaccinations/vaccinations.csv |
| `vaccinations-by-age-group.csv` | https://raw.githubusercontent.com/owid/covid-19-data/master/public/data/vaccinations/vaccinations-by-age-group.csv |
| `vaccinations-by-manufacturer.csv` | https://raw.githubusercontent.com/owid/covid-19-data/master/public/data/vaccinations/vaccinations-by-manufacturer.csv |
| `excess_mortality.csv` | https://raw.githubusercontent.com/owid/covid-19-data/master/public/data/excess_mortality/excess_mortality.csv |
| `covid-testing-all-observations.csv` | https://raw.githubusercontent.com/owid/covid-19-data/master/public/data/testing/covid-testing-all-observations.csv |
| `covid-hospitalizations.csv` | https://raw.githubusercontent.com/owid/covid-19-data/master/public/data/hospitalizations/covid-hospitalizations.csv |
| `who-covid-cases-deaths.csv` | https://raw.githubusercontent.com/owid/covid-19-data/master/public/data/cases_deaths/COVID-19%20Cases%20and%20deaths%20-%20WHO.csv |

## ETL catalog

| Файл | Источник |
|---|---|
| `catalog/compact.csv` | https://catalog.ourworldindata.org/garden/covid/latest/compact/compact.csv |
| `catalog/cases_deaths.csv` | https://catalog.ourworldindata.org/garden/covid/latest/cases_deaths/cases_deaths.csv |
| `catalog/excess_mortality.csv` | https://catalog.ourworldindata.org/garden/excess_mortality/latest/excess_mortality/excess_mortality.csv |
| `catalog/excess_mortality_economist.csv` | https://catalog.ourworldindata.org/garden/excess_mortality/latest/excess_mortality_economist/excess_mortality_economist.csv |
| `catalog/hospital.csv` | https://catalog.ourworldindata.org/garden/covid/latest/hospital/hospital.csv |
| `catalog/vaccinations_global.csv` | https://catalog.ourworldindata.org/garden/covid/latest/vaccinations_global/vaccinations_global.csv |
| `catalog/vaccinations_age.csv` | https://catalog.ourworldindata.org/garden/covid/latest/vaccinations_age/vaccinations_age.csv |
| `catalog/vaccinations_manufacturer.csv` | https://catalog.ourworldindata.org/garden/covid/latest/vaccinations_manufacturer/vaccinations_manufacturer.csv |
| `catalog/vaccinations_us.csv` | https://catalog.ourworldindata.org/garden/covid/latest/vaccinations_us/vaccinations_us.csv |
| `catalog/testing.csv` | https://catalog.ourworldindata.org/garden/covid/latest/testing/testing.csv |
| `catalog/tracking_r.csv` | https://catalog.ourworldindata.org/garden/covid/latest/tracking_r/tracking_r.csv |
| `catalog/google_mobility.csv` | https://catalog.ourworldindata.org/garden/covid/latest/google_mobility/google_mobility.csv |
| `catalog/oxcgrt_policy.csv` | https://catalog.ourworldindata.org/garden/covid/latest/oxcgrt_policy/oxcgrt_policy.csv |
| `catalog/yougov_composite.csv` | https://catalog.ourworldindata.org/garden/covid/latest/yougov/yougov_composite.csv |
| `catalog/covax.csv` | https://catalog.ourworldindata.org/garden/covid/latest/covax/covax.csv |

Для каждого CSV также загружается `.meta.json` с метаданными.

## Проверка объёма

```bash
python scripts/prepare_data.py
```

Скрипт создаёт:

- `data/sample/owid-catalog-sample.csv` — sample из актуального каталога;
- `data/sample/owid-covid-sample.csv` — sample из legacy GitHub;
- `data/manifest.json` с размерами, числом строк и источниками.
