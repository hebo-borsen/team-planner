CREATE TABLE IF NOT EXISTS user_secondary_departments (
    user_id INT NOT NULL,
    department_id INT NOT NULL,
    PRIMARY KEY (user_id, department_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE CASCADE
);
