-- 1. JOIN: latest country snapshot
SELECT
    c.location,
    c.continent,
    m.date,
    m.total_cases,
    m.total_deaths
FROM countries AS c
JOIN covid_metrics AS m
    ON c.iso_code = m.iso_code
WHERE m.date = (SELECT MAX(date) FROM covid_metrics)
ORDER BY m.total_cases DESC;

-- 2. GROUP BY / HAVING: monthly global totals
SELECT
    substr(m.date, 1, 7) AS month,
    SUM(m.new_cases) AS new_cases,
    SUM(m.new_deaths) AS new_deaths
FROM covid_metrics AS m
JOIN countries AS c
    ON c.iso_code = m.iso_code
WHERE c.continent IS NOT NULL
GROUP BY month
HAVING SUM(m.new_cases) > 0
ORDER BY month;

-- 3. CTE + subquery: countries above the latest global average vaccination
WITH latest AS (
    SELECT iso_code, MAX(date) AS date
    FROM vaccinations
    GROUP BY iso_code
),
average_vaccination AS (
    SELECT AVG(v.people_vaccinated_per_hundred) AS average_value
    FROM vaccinations AS v
    JOIN latest AS l
        ON v.iso_code = l.iso_code
       AND v.date = l.date
)
SELECT
    c.location,
    v.people_vaccinated_per_hundred
FROM vaccinations AS v
JOIN latest AS l
    ON v.iso_code = l.iso_code
   AND v.date = l.date
JOIN countries AS c
    ON c.iso_code = v.iso_code
WHERE v.people_vaccinated_per_hundred > (SELECT average_value FROM average_vaccination)
ORDER BY v.people_vaccinated_per_hundred DESC;

-- 4. CTE: peak month by country
WITH monthly AS (
    SELECT
        m.iso_code,
        substr(m.date, 1, 7) AS month,
        SUM(m.new_cases) AS cases
    FROM covid_metrics AS m
    GROUP BY m.iso_code, month
)
SELECT
    c.location,
    monthly.month,
    monthly.cases
FROM monthly
JOIN countries AS c
    ON c.iso_code = monthly.iso_code
WHERE monthly.cases = (
    SELECT MAX(monthly_2.cases)
    FROM monthly AS monthly_2
    WHERE monthly_2.iso_code = monthly.iso_code
)
ORDER BY monthly.cases DESC
LIMIT 50;

-- 5. Window function: vaccination rank by date
SELECT
    c.location,
    v.date,
    v.people_fully_vaccinated_per_hundred,
    RANK() OVER (
        PARTITION BY v.date
        ORDER BY v.people_fully_vaccinated_per_hundred DESC
    ) AS vaccination_rank
FROM vaccinations AS v
JOIN countries AS c
    ON c.iso_code = v.iso_code
WHERE v.people_fully_vaccinated_per_hundred IS NOT NULL
ORDER BY v.date DESC, vaccination_rank
LIMIT 100;

-- 6. Window function: 7-day rolling average in SQL
SELECT
    c.location,
    m.date,
    m.new_cases,
    AVG(m.new_cases) OVER (
        PARTITION BY m.iso_code
        ORDER BY m.date
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) AS rolling_7
FROM covid_metrics AS m
JOIN countries AS c
    ON c.iso_code = m.iso_code
WHERE c.location = 'United States'
ORDER BY m.date;

-- 7. JOIN + aggregation: vaccination and mortality by continent
WITH vaccination_max AS (
    SELECT
        iso_code,
        MAX(people_fully_vaccinated_per_hundred) AS fully_vaccinated
    FROM vaccinations
    GROUP BY iso_code
),
deaths_total AS (
    SELECT
        iso_code,
        SUM(new_deaths) AS deaths
    FROM covid_metrics
    GROUP BY iso_code
)
SELECT
    c.continent,
    AVG(vaccination_max.fully_vaccinated) AS average_fully_vaccinated,
    SUM(deaths_total.deaths) AS total_deaths
FROM countries AS c
LEFT JOIN vaccination_max
    ON c.iso_code = vaccination_max.iso_code
LEFT JOIN deaths_total
    ON c.iso_code = deaths_total.iso_code
WHERE c.continent IS NOT NULL
GROUP BY c.continent
ORDER BY total_deaths DESC;

-- 8. CTE + window function: top three peaks per country
WITH daily AS (
    SELECT
        iso_code,
        date,
        new_cases_smoothed,
        ROW_NUMBER() OVER (
            PARTITION BY iso_code
            ORDER BY new_cases_smoothed DESC
        ) AS row_number
    FROM covid_metrics
    WHERE new_cases_smoothed IS NOT NULL
)
SELECT
    c.location,
    daily.date AS peak_date,
    daily.new_cases_smoothed AS peak_value
FROM daily
JOIN countries AS c
    ON c.iso_code = daily.iso_code
WHERE daily.row_number <= 3
ORDER BY c.location, daily.row_number;

-- 9. Dashboard filter query
SELECT
    c.location,
    c.continent,
    m.date,
    m.new_cases,
    m.new_deaths,
    v.people_vaccinated_per_hundred
FROM covid_metrics AS m
JOIN countries AS c
    ON c.iso_code = m.iso_code
LEFT JOIN vaccinations AS v
    ON v.iso_code = m.iso_code
   AND v.date = m.date
WHERE strftime('%Y', m.date) = :year
  AND (:region IS NULL OR c.continent = :region)
  AND (
      :category IS NULL
      OR (:category = 'High' AND v.people_vaccinated_per_hundred >= 70)
      OR (:category = 'Medium' AND v.people_vaccinated_per_hundred >= 40 AND v.people_vaccinated_per_hundred < 70)
      OR (:category = 'Low' AND v.people_vaccinated_per_hundred >= 0 AND v.people_vaccinated_per_hundred < 40)
      OR (:category = 'None' AND (v.people_vaccinated_per_hundred IS NULL OR v.people_vaccinated_per_hundred = 0))
  )
ORDER BY m.date, c.location;
