-- Create team_members table
CREATE TABLE IF NOT EXISTS team_members (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    emoji VARCHAR(10) DEFAULT '👤',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create vacation_days table
CREATE TABLE IF NOT EXISTS vacation_days (
    id INT AUTO_INCREMENT PRIMARY KEY,
    member_id INT NOT NULL,
    vacation_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (member_id) REFERENCES team_members(id) ON DELETE CASCADE,
    UNIQUE KEY unique_member_date (member_id, vacation_date)
);

-- Create holidays table
CREATE TABLE IF NOT EXISTS holidays (
    id INT AUTO_INCREMENT PRIMARY KEY,
    holiday_date DATE NOT NULL UNIQUE,
    holiday_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert some default team members (you can modify these)
INSERT INTO team_members (name, emoji) VALUES
    ('Alice Johnson', '👩'),
    ('Bob Smith', '👨'),
    ('Carol Williams', '👩‍💼'),
    ('David Brown', '👨‍💻'),
    ('Emma Davis', '👩‍🎨')
ON DUPLICATE KEY UPDATE name=name;
