-- Remove all department-specific holiday copies; only keep the shared defaults (department_id IS NULL)
DELETE FROM period_holidays WHERE department_id IS NOT NULL;
