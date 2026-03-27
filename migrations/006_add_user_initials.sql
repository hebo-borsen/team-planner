-- Add initials column to users table
ALTER TABLE users ADD COLUMN initials VARCHAR(10) DEFAULT NULL;

-- Default initials to username for existing users
UPDATE users SET initials = username WHERE initials IS NULL;
