
CREATE DATABASE IF NOT EXISTS service_marketplace;
USE service_marketplace;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    phone VARCHAR(15),
    password VARCHAR(255) NOT NULL,
    profile_image VARCHAR(255) DEFAULT 'default_user.png',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS workers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    phone VARCHAR(15),
    password VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    skills TEXT,
    hourly_rate DECIMAL(10,2) DEFAULT 0.00,
    bio TEXT,
    location VARCHAR(150),
    pincode VARCHAR(10),
    profile_image VARCHAR(255) DEFAULT 'default_worker.png',
    is_available TINYINT(1) DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS bookings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    worker_id INT NOT NULL,
    service_date DATE NOT NULL,
    service_time TIME NOT NULL,
    duration DECIMAL(4,1) DEFAULT 1.0,
    address TEXT NOT NULL,
    notes TEXT,
    total_amount DECIMAL(10,2) DEFAULT 0.00,
    status ENUM(
        'pending',
        'confirmed',
        'in_progress',
        'completed',
        'cancelled'
    ) DEFAULT 'pending',
    otp CHAR(4),
    rating TINYINT,
    review TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (worker_id) REFERENCES workers(id) ON DELETE CASCADE
) ENGINE=InnoDB;
