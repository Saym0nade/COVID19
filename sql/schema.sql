PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS countries (
    iso_code TEXT PRIMARY KEY,
    location TEXT NOT NULL,
    continent TEXT,
    population REAL,
    gdp_per_capita REAL,
    human_development_index REAL
);

CREATE TABLE IF NOT EXISTS covid_metrics (
    iso_code TEXT NOT NULL,
    date TEXT NOT NULL,
    new_cases REAL,
    total_cases REAL,
    new_deaths REAL,
    total_deaths REAL,
    new_cases_smoothed REAL,
    new_deaths_smoothed REAL,
    PRIMARY KEY (iso_code, date),
    FOREIGN KEY (iso_code) REFERENCES countries (iso_code)
);

CREATE TABLE IF NOT EXISTS vaccinations (
    iso_code TEXT NOT NULL,
    date TEXT NOT NULL,
    people_vaccinated REAL,
    people_fully_vaccinated REAL,
    total_boosters REAL,
    people_vaccinated_per_hundred REAL,
    people_fully_vaccinated_per_hundred REAL,
    PRIMARY KEY (iso_code, date),
    FOREIGN KEY (iso_code) REFERENCES countries (iso_code)
);

CREATE TABLE IF NOT EXISTS excess_mortality (
    iso_code TEXT NOT NULL,
    date TEXT NOT NULL,
    excess_mortality REAL,
    excess_mortality_cumulative REAL,
    PRIMARY KEY (iso_code, date),
    FOREIGN KEY (iso_code) REFERENCES countries (iso_code)
);

CREATE TABLE IF NOT EXISTS waves (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    iso_code TEXT NOT NULL,
    wave_number INTEGER NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    peak_date TEXT,
    peak_value REAL,
    FOREIGN KEY (iso_code) REFERENCES countries (iso_code)
);

CREATE INDEX IF NOT EXISTS idx_covid_metrics_date ON covid_metrics (date);
CREATE INDEX IF NOT EXISTS idx_covid_metrics_iso_date ON covid_metrics (iso_code, date);
CREATE INDEX IF NOT EXISTS idx_vaccinations_date ON vaccinations (date);
CREATE INDEX IF NOT EXISTS idx_vaccinations_iso_date ON vaccinations (iso_code, date);
CREATE INDEX IF NOT EXISTS idx_excess_mortality_iso_date ON excess_mortality (iso_code, date);
CREATE INDEX IF NOT EXISTS idx_waves_iso ON waves (iso_code);
