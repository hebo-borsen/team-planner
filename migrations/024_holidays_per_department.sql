-- Add department_id to period_holidays (NULL = default/template holidays)
ALTER TABLE period_holidays ADD COLUMN department_id INT NULL;

-- Add index on period_id so the FK has a backing index before we drop the unique key
ALTER TABLE period_holidays ADD INDEX idx_period_id (period_id);

-- Drop old unique constraint that only covered (period_id, holiday_date)
ALTER TABLE period_holidays DROP INDEX uq_period_date;

-- Copy existing (default) holidays into each existing department
INSERT INTO period_holidays (period_id, name, holiday_date, enabled, department_id)
SELECT ph.period_id, ph.name, ph.holiday_date, ph.enabled, d.id
FROM period_holidays ph
CROSS JOIN departments d
WHERE ph.department_id IS NULL;
