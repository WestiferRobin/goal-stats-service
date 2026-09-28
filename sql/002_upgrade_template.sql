BEGIN;

DO $$ BEGIN
IF (SELECT count(*) FROM alembic_version) <> 1 OR NOT EXISTS (
    SELECT 1 FROM alembic_version WHERE version_num = 'b7f42e9c1a60'
) THEN RAISE EXCEPTION 'Expected template revision b7f42e9c1a60'; END IF;
END $$;


-- Running upgrade b7f42e9c1a60 -> d94f81ab2301

CREATE TABLE football_teams (
    name VARCHAR(100) NOT NULL, 
    ratings JSON NOT NULL, 
    CONSTRAINT pk_football_teams PRIMARY KEY (name)
);

CREATE TABLE football_history (
    id VARCHAR(64) NOT NULL, 
    source VARCHAR(100) NOT NULL, 
    source_row INTEGER NOT NULL, 
    team1 VARCHAR(100) NOT NULL, 
    team2 VARCHAR(100) NOT NULL, 
    data JSON NOT NULL, 
    CONSTRAINT pk_football_history PRIMARY KEY (id), 
    CONSTRAINT uq_football_history_source UNIQUE (source, source_row), 
    CONSTRAINT ck_football_history_distinct_teams CHECK (team1 <> team2), 
    CONSTRAINT fk_football_history_team1_football_teams FOREIGN KEY(team1) REFERENCES football_teams (name), 
    CONSTRAINT fk_football_history_team2_football_teams FOREIGN KEY(team2) REFERENCES football_teams (name)
);

CREATE TABLE football_snapshots (
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    team1 VARCHAR(100) NOT NULL, 
    team2 VARCHAR(100) NOT NULL, 
    state JSON NOT NULL, 
    prediction JSON NOT NULL, 
    CONSTRAINT pk_football_snapshots PRIMARY KEY (id), 
    CONSTRAINT ck_football_snapshots_distinct_teams CHECK (team1 <> team2), 
    CONSTRAINT fk_football_snapshots_team1_football_teams FOREIGN KEY(team1) REFERENCES football_teams (name), 
    CONSTRAINT fk_football_snapshots_team2_football_teams FOREIGN KEY(team2) REFERENCES football_teams (name)
);

CREATE INDEX ix_football_snapshots_team1 ON football_snapshots (team1);

CREATE INDEX ix_football_snapshots_team2 ON football_snapshots (team2);

UPDATE alembic_version SET version_num='d94f81ab2301' WHERE alembic_version.version_num = 'b7f42e9c1a60';

COMMIT;

