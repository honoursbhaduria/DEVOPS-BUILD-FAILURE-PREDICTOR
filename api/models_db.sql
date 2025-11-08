CREATE TABLE IF NOT EXISTS builds (
  id SERIAL PRIMARY KEY,
  build_number INTEGER UNIQUE NOT NULL,
  result VARCHAR(50),
  duration BIGINT,
  timestamp TIMESTAMP,
  raw_log_path TEXT,
  raw_log TEXT,
  commit_message TEXT,
  error_count INTEGER,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

