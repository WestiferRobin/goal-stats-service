BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> b7f42e9c1a60

CREATE TABLE items (
    name VARCHAR(200) NOT NULL, 
    status VARCHAR(8) NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_items PRIMARY KEY (id), 
    CONSTRAINT ck_items_name_not_blank CHECK (name ~ '[^[:space:]]'), 
    CONSTRAINT ck_items_item_status CHECK (status IN ('active', 'archived'))
);

CREATE TABLE actions (
    item_id UUID NOT NULL, 
    name VARCHAR(200) NOT NULL, 
    action_type VARCHAR(6) NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_actions PRIMARY KEY (id), 
    CONSTRAINT ck_actions_name_not_blank CHECK (name ~ '[^[:space:]]'), 
    CONSTRAINT fk_actions_item_id_items FOREIGN KEY(item_id) REFERENCES items (id) ON DELETE CASCADE, 
    CONSTRAINT ck_actions_action_type CHECK (action_type IN ('create', 'update', 'delete'))
);

CREATE INDEX ix_actions_item_id ON actions (item_id);

INSERT INTO alembic_version (version_num) VALUES ('b7f42e9c1a60') RETURNING alembic_version.version_num;

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

