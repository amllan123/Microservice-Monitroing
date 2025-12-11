-- Users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(20) NOT NULL,
    rating DECIMAL(3,2) DEFAULT 5.00,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Drivers table
CREATE TABLE IF NOT EXISTS drivers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(20) NOT NULL,
    license_number VARCHAR(50) UNIQUE NOT NULL,
    vehicle_type VARCHAR(50) NOT NULL,
    vehicle_number VARCHAR(20) NOT NULL,
    rating DECIMAL(3,2) DEFAULT 5.00,
    status VARCHAR(20) DEFAULT 'offline',
    current_lat DECIMAL(10,8),
    current_lng DECIMAL(11,8),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Rides table
CREATE TABLE IF NOT EXISTS rides (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    driver_id INTEGER REFERENCES drivers(id),
    pickup_lat DECIMAL(10,8) NOT NULL,
    pickup_lng DECIMAL(11,8) NOT NULL,
    dropoff_lat DECIMAL(10,8) NOT NULL,
    dropoff_lng DECIMAL(11,8) NOT NULL,
    pickup_address TEXT,
    dropoff_address TEXT,
    status VARCHAR(20) DEFAULT 'requested',
    fare DECIMAL(10,2),
    distance_km DECIMAL(10,2),
    duration_minutes INTEGER,
    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    accepted_at TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    cancelled_at TIMESTAMP
);

-- Payments table
CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY,
    ride_id INTEGER REFERENCES rides(id),
    user_id INTEGER REFERENCES users(id),
    amount DECIMAL(10,2) NOT NULL,
    payment_method VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    transaction_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_drivers_status ON drivers(status);
CREATE INDEX IF NOT EXISTS idx_rides_user_id ON rides(user_id);
CREATE INDEX IF NOT EXISTS idx_rides_driver_id ON rides(driver_id);
CREATE INDEX IF NOT EXISTS idx_rides_status ON rides(status);
CREATE INDEX IF NOT EXISTS idx_payments_ride_id ON payments(ride_id);

-- Insert sample data
INSERT INTO users (name, email, phone, rating) VALUES
    ('John Doe', 'john@example.com', '+1234567890', 4.8),
    ('Jane Smith', 'jane@example.com', '+1234567891', 4.9),
    ('Bob Wilson', 'bob@example.com', '+1234567892', 4.7),
    ('Alice Brown', 'alice@example.com', '+1234567893', 4.6),
    ('Charlie Davis', 'charlie@example.com', '+1234567894', 4.9)
ON CONFLICT (email) DO NOTHING;

INSERT INTO drivers (name, email, phone, license_number, vehicle_type, vehicle_number, rating, status, current_lat, current_lng) VALUES
    ('Driver One', 'driver1@example.com', '+1234567895', 'DL001', 'sedan', 'ABC123', 4.7, 'available', 12.9716, 77.5946),
    ('Driver Two', 'driver2@example.com', '+1234567896', 'DL002', 'suv', 'XYZ456', 4.8, 'available', 12.9756, 77.5986),
    ('Driver Three', 'driver3@example.com', '+1234567897', 'DL003', 'sedan', 'DEF789', 4.9, 'available', 12.9696, 77.5906),
    ('Driver Four', 'driver4@example.com', '+1234567898', 'DL004', 'luxury', 'GHI012', 4.6, 'available', 12.9776, 77.6026),
    ('Driver Five', 'driver5@example.com', '+1234567899', 'DL005', 'sedan', 'JKL345', 4.8, 'available', 12.9656, 77.5866)
ON CONFLICT (email) DO NOTHING;