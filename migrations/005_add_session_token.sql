-- Add session token for persistent login across page refreshes
ALTER TABLE users ADD COLUMN session_token VARCHAR(64) DEFAULT NULL;
