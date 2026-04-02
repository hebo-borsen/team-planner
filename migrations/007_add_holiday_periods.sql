-- Holiday periods and Danish public holidays (søgnehelligdage)

CREATE TABLE IF NOT EXISTS holiday_periods (
    id INT AUTO_INCREMENT PRIMARY KEY,
    label VARCHAR(20) NOT NULL UNIQUE,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS period_holidays (
    id INT AUTO_INCREMENT PRIMARY KEY,
    period_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    holiday_date DATE NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    FOREIGN KEY (period_id) REFERENCES holiday_periods(id) ON DELETE CASCADE,
    UNIQUE KEY uq_period_date (period_id, holiday_date)
);

-- Period 2025/2026
INSERT INTO holiday_periods (label, start_date, end_date) VALUES ('2025/2026', '2025-09-01', '2026-08-31');
SET @p = LAST_INSERT_ID();
INSERT INTO period_holidays (period_id, name, holiday_date, enabled) VALUES
(@p, 'Juleaftensdag', '2025-12-24', TRUE),
(@p, '1. Juledag', '2025-12-25', TRUE),
(@p, '2. Juledag', '2025-12-26', TRUE),
(@p, 'Nytårsdag', '2026-01-01', TRUE),
(@p, 'Skærtorsdag', '2026-04-02', TRUE),
(@p, 'Langfredag', '2026-04-03', TRUE),
(@p, '2. Påskedag', '2026-04-06', TRUE),
(@p, 'Kristi Himmelfartsdag', '2026-05-14', TRUE),
(@p, '2. Pinsedag', '2026-05-25', TRUE),
(@p, 'Grundlovsdag', '2026-06-05', TRUE);

-- Period 2026/2027 (Easter 2027 = March 28)
INSERT INTO holiday_periods (label, start_date, end_date) VALUES ('2026/2027', '2026-09-01', '2027-08-31');
SET @p = LAST_INSERT_ID();
INSERT INTO period_holidays (period_id, name, holiday_date, enabled) VALUES
(@p, 'Juleaftensdag', '2026-12-24', TRUE),
(@p, '1. Juledag', '2026-12-25', TRUE),
(@p, '2. Juledag', '2026-12-26', TRUE),
(@p, 'Nytårsdag', '2027-01-01', TRUE),
(@p, 'Skærtorsdag', '2027-03-25', TRUE),
(@p, 'Langfredag', '2027-03-26', TRUE),
(@p, '2. Påskedag', '2027-03-29', TRUE),
(@p, 'Kristi Himmelfartsdag', '2027-05-06', TRUE),
(@p, '2. Pinsedag', '2027-05-17', TRUE),
(@p, 'Grundlovsdag', '2027-06-05', TRUE);

-- Period 2027/2028 (Easter 2028 = April 16)
INSERT INTO holiday_periods (label, start_date, end_date) VALUES ('2027/2028', '2027-09-01', '2028-08-31');
SET @p = LAST_INSERT_ID();
INSERT INTO period_holidays (period_id, name, holiday_date, enabled) VALUES
(@p, 'Juleaftensdag', '2027-12-24', TRUE),
(@p, '1. Juledag', '2027-12-25', TRUE),
(@p, '2. Juledag', '2027-12-26', TRUE),
(@p, 'Nytårsdag', '2028-01-01', TRUE),
(@p, 'Skærtorsdag', '2028-04-13', TRUE),
(@p, 'Langfredag', '2028-04-14', TRUE),
(@p, '2. Påskedag', '2028-04-17', TRUE),
(@p, 'Kristi Himmelfartsdag', '2028-05-25', TRUE),
(@p, '2. Pinsedag / Grundlovsdag', '2028-06-05', TRUE);

-- Period 2028/2029 (Easter 2029 = April 1)
INSERT INTO holiday_periods (label, start_date, end_date) VALUES ('2028/2029', '2028-09-01', '2029-08-31');
SET @p = LAST_INSERT_ID();
INSERT INTO period_holidays (period_id, name, holiday_date, enabled) VALUES
(@p, 'Juleaftensdag', '2028-12-24', TRUE),
(@p, '1. Juledag', '2028-12-25', TRUE),
(@p, '2. Juledag', '2028-12-26', TRUE),
(@p, 'Nytårsdag', '2029-01-01', TRUE),
(@p, 'Skærtorsdag', '2029-03-29', TRUE),
(@p, 'Langfredag', '2029-03-30', TRUE),
(@p, '2. Påskedag', '2029-04-02', TRUE),
(@p, 'Kristi Himmelfartsdag', '2029-05-10', TRUE),
(@p, '2. Pinsedag', '2029-05-21', TRUE),
(@p, 'Grundlovsdag', '2029-06-05', TRUE);

-- Period 2029/2030 (Easter 2030 = April 21)
INSERT INTO holiday_periods (label, start_date, end_date) VALUES ('2029/2030', '2029-09-01', '2030-08-31');
SET @p = LAST_INSERT_ID();
INSERT INTO period_holidays (period_id, name, holiday_date, enabled) VALUES
(@p, 'Juleaftensdag', '2029-12-24', TRUE),
(@p, '1. Juledag', '2029-12-25', TRUE),
(@p, '2. Juledag', '2029-12-26', TRUE),
(@p, 'Nytårsdag', '2030-01-01', TRUE),
(@p, 'Skærtorsdag', '2030-04-18', TRUE),
(@p, 'Langfredag', '2030-04-19', TRUE),
(@p, '2. Påskedag', '2030-04-22', TRUE),
(@p, 'Kristi Himmelfartsdag', '2030-05-30', TRUE),
(@p, '2. Pinsedag', '2030-06-10', TRUE),
(@p, 'Grundlovsdag', '2030-06-05', TRUE);
