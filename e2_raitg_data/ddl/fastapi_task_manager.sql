CREATE TABLE tasks (
    id integer NOT NULL,
    title varchar(120) NOT NULL,
    description varchar(500),
    completed boolean NOT NULL,
    created_at timestamp,
    updated_at timestamp,
    PRIMARY KEY (id)
);
