-- SQLite
CREATE TABLE
    IF NOT EXISTS channels (
        id INT PRIMARY KEY,
        type TEXT CHECK (type IN ('lobby', 'register')) NOT NULL DEFAULT 'lobby'
    );

CREATE TABLE
    IF NOT EXISTS users (
        id INT PRIMARY KEY,
        name TEXT NOT NULL,
        elo INT NOT NULL DEFAULT 0
    );

CREATE TABLE
    IF NOT EXISTS teams (
        id INT,
        game INT,
        player REFERENCES users (id),
        PRIMARY KEY (id, game)
    );

CREATE TABLE
    IF NOT EXISTS games (
        id INT PRIMARY KEY AUTOINCREMENT,
        state TEXT CHECK (state IN ('playing', 'voided', 'finished')) NOT NULL DEFAULT 'playing',
        won INT CHECK (won IN (1, 2)),
        score TEXT,
        teamleader1 REFERENCES users (id),
        teamleader2 REFERENCES users (id)
    );

CREATE TABLE
    IF NOT EXISTS registerRole(
        id INT,
        guild INT
    );