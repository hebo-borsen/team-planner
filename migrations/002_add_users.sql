-- Create users table for authentication
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(256) NOT NULL,
    must_change_password BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert default user "hebo" (password: "hebo")
-- SHA-256 hash of "hebo", forced to change password on first login
INSERT INTO users (username, password_hash, must_change_password) VALUES
    ('hebo', '85360716c9027b1d489fe7bc4d6d0609c2e0f8fb25061de6f6e4fb0a5decfec3', TRUE)
ON DUPLICATE KEY UPDATE username=username;
