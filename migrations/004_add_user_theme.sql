-- Add theme preference to users table
ALTER TABLE users ADD COLUMN theme VARCHAR(10) DEFAULT 'light';
