-- SQLite
CREATE TABLE
    IF NOT EXISTS channels (
        id INTEGER PRIMARY KEY,
        type TEXT CHECK (type IN ('lobby', 'register')) NOT NULL DEFAULT 'lobby'
    );

CREATE TABLE
    IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        elo INTEGER NOT NULL DEFAULT 0
    );

CREATE TABLE
    IF NOT EXISTS teams (
        id INTEGER,
        game INTEGER,
        player REFERENCES users (id),
        PRIMARY KEY (id, game)
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