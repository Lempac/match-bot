-- SQLite

CREATE TABLE
    IF NOT EXISTS config (
        id INTEGER PRIMARY KEY,
        max_player INT DEFAULT 10,
        points_per_game INT DEFAULT 25,
        free_multiplier FLOAT DEFAULT 1,
        premium_multiplier FLOAT DEFAULT 1,
    );

CREATE TABLE
    IF NOT EXISTS channels (
        id INTEGER PRIMARY KEY,
        type TEXT CHECK (type IN ('lobby', 'register', 'score')) NOT NULL DEFAULT 'lobby'
    );

CREATE TABLE
    IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        elo INTEGER NOT NULL DEFAULT 0
    );

CREATE TABLE
    IF NOT EXISTS ranks (
        id INTEGER PRIMARY KEY,
        guild INTEGERNOT NULL,
        below INTEGER NOT NULL DEFAULT 0,
        above INTEGER NOT NULL 
    );

CREATE TABLE
    IF NOT EXISTS teams (
        id INTEGER,
        game INTEGER,
        player REFERENCES users (id),
        PRIMARY KEY (id, game, player)
    );

CREATE TABLE
    IF NOT EXISTS games (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        state TEXT CHECK (state IN ('playing', 'voided', 'finished')) NOT NULL DEFAULT 'playing',
        won INTEGER CHECK (won IN (1, 2)),
        score TEXT,
        teamleader1 REFERENCES users (id),
        teamleader2 REFERENCES users (id)
    );

CREATE TABLE
    IF NOT EXISTS registerRole(
        id INTEGER,
        guild INTEGER
    );