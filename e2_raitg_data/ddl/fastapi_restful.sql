CREATE TABLE players (
    id varchar(36) NOT NULL,
    firstName varchar(50) NOT NULL,
    middleName varchar(50),
    lastName varchar(50) NOT NULL,
    dateOfBirth varchar(24),
    squadNumber integer NOT NULL,
    position varchar(30) NOT NULL,
    abbrPosition varchar(5),
    team varchar(60),
    league varchar(60),
    starting11 boolean,
    PRIMARY KEY (id),
    UNIQUE (squadNumber)
);
