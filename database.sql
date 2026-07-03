-- Create Database
CREATE DATABASE IF NOT EXISTS hotel_booking_db;
USE hotel_booking_db;

-- Table 1: Rooms
CREATE TABLE rooms (
    room_id INT PRIMARY KEY AUTO_INCREMENT,
    room_number VARCHAR(10) UNIQUE NOT NULL,
    room_type ENUM('Single', 'Double', 'Deluxe') NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    availability ENUM('Available', 'Booked') DEFAULT 'Available',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table 2: Customers
CREATE TABLE customers (
    customer_id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100),
    phone VARCHAR(15) NOT NULL,
    id_proof VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table 3: Bookings
CREATE TABLE bookings (
    booking_id INT PRIMARY KEY AUTO_INCREMENT,
    customer_id INT NOT NULL,
    room_id INT NOT NULL,
    check_in DATE NOT NULL,
    check_out DATE NOT NULL,
    total_amount DECIMAL(10, 2) NOT NULL,
    status ENUM('Confirmed', 'Cancelled') DEFAULT 'Confirmed',
    booking_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (room_id) REFERENCES rooms(room_id)
);

-- Table 4: Payments
CREATE TABLE payments (
    payment_id INT PRIMARY KEY AUTO_INCREMENT,
    booking_id INT NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    payment_status ENUM('Pending', 'Completed') DEFAULT 'Pending',
    payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (booking_id) REFERENCES bookings(booking_id)
);

-- Insert Sample Data

-- Sample Rooms
INSERT INTO rooms (room_number, room_type, price, availability) VALUES
('101', 'Single', 1500.00, 'Available'),
('102', 'Single', 1500.00, 'Available'),
('201', 'Double', 2500.00, 'Available'),
('202', 'Double', 2500.00, 'Available'),
('301', 'Deluxe', 4000.00, 'Available'),
('302', 'Deluxe', 4000.00, 'Available'),
('103', 'Single', 1500.00, 'Available'),
('203', 'Double', 2500.00, 'Available');

-- Sample Customers
INSERT INTO customers (name, email, phone, id_proof) VALUES
('Rahul Kumar', 'rahul@email.com', '9876543210', 'AADHAR123456'),
('Priya Sharma', 'priya@email.com', '9876543211', 'AADHAR123457');

-- Sample Bookings
INSERT INTO bookings (customer_id, room_id, check_in, check_out, total_amount, status) VALUES
(1, 1, '2025-01-15', '2025-01-17', 3000.00, 'Confirmed');

-- Update room availability for booked room
UPDATE rooms SET availability = 'Booked' WHERE room_id = 1;

-- Sample Payments
INSERT INTO payments (booking_id, amount, payment_status) VALUES
(1, 3000.00, 'Completed');

-- Create View for Booking Details
CREATE VIEW booking_details AS
SELECT 
    b.booking_id,
    c.name AS customer_name,
    c.email,
    c.phone,
    r.room_number,
    r.room_type,
    r.price,
    b.check_in,
    b.check_out,
    b.total_amount,
    b.status,
    p.payment_status,
    b.booking_date
FROM bookings b
JOIN customers c ON b.customer_id = c.customer_id
JOIN rooms r ON b.room_id = r.room_id
JOIN payments p ON b.booking_id = p.booking_id;

-- Create Stored Procedure for Revenue Report
DELIMITER //
CREATE PROCEDURE GetRevenueReport()
BEGIN
    SELECT 
        DATE(booking_date) as booking_day,
        COUNT(*) as total_bookings,
        SUM(total_amount) as daily_revenue
    FROM bookings
    WHERE status = 'Confirmed'
    GROUP BY DATE(booking_date)
    ORDER BY booking_day DESC;
END //
DELIMITER ;

-- Create Trigger to prevent double booking
DELIMITER //
CREATE TRIGGER check_room_availability
BEFORE INSERT ON bookings
FOR EACH ROW
BEGIN
    DECLARE room_status VARCHAR(20);
    SELECT availability INTO room_status FROM rooms WHERE room_id = NEW.room_id;
    IF room_status = 'Booked' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Room is already booked';
    END IF;
END //
DELIMITER ;