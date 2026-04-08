ALTER TABLE holiday_periods ADD COLUMN earning_start DATE NULL;
ALTER TABLE holiday_periods ADD COLUMN earning_end DATE NULL;
UPDATE holiday_periods SET earning_start = start_date, earning_end = end_date WHERE earning_start IS NULL;
