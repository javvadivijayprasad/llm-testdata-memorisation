CREATE TABLE user (
    id integer NOT NULL,
    username varchar(80) NOT NULL,
    password varchar(80) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (username)
);

CREATE TABLE post (
    id integer NOT NULL,
    author_id integer NOT NULL,
    created timestamp NOT NULL,
    title varchar(120) NOT NULL,
    body text NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (author_id) REFERENCES user(id)
);
