CREATE DATABASE IF NOT EXISTS telegram_bot;

USE telegram_bot;

CREATE TABLE IF NOT EXISTS Admin (
    id INT AUTO_INCREMENT PRIMARY KEY,
    phone_number VARCHAR(20) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    language VARCHAR(5) NOT NULL DEFAULT 'ru',
    chat_id BIGINT
);

CREATE TABLE IF NOT EXISTS Staff (
    id INT AUTO_INCREMENT PRIMARY KEY,
    phone_number VARCHAR(20) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    chat_id BIGINT,
    language VARCHAR(5) NOT NULL DEFAULT 'ru',
    like_count INT DEFAULT 0,
    dislike_count INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS User (
    id INT AUTO_INCREMENT PRIMARY KEY,
    phone_number VARCHAR(20) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    language VARCHAR(5) NOT NULL DEFAULT 'ru',
    chat_id BIGINT
);

CREATE TABLE IF NOT EXISTS Question (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    question_text TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES User(id)
);

CREATE TABLE IF NOT EXISTS Video (
    id INT AUTO_INCREMENT PRIMARY KEY,
    question_id INT NOT NULL,
    video_link TEXT NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    staff_id INT NOT NULL,
    like_count INT DEFAULT 0,
    dislike_count INT DEFAULT 0,
    FOREIGN KEY (question_id) REFERENCES Question(id),
    FOREIGN KEY (staff_id) REFERENCES Staff(id)
);