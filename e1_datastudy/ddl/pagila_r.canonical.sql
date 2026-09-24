CREATE TABLE cast_member (
    cast_member_id integer NOT NULL,
    given_name text NOT NULL,
    family_name text NOT NULL,
    modified_on timestamp NOT NULL,
    PRIMARY KEY (cast_member_id)
);

CREATE TABLE nation (
    nation_id integer NOT NULL,
    nation text NOT NULL,
    modified_on timestamp NOT NULL,
    PRIMARY KEY (nation_id)
);

CREATE TABLE town (
    town_id integer NOT NULL,
    town text NOT NULL,
    nation_id integer NOT NULL,
    modified_on timestamp NOT NULL,
    PRIMARY KEY (town_id),
    FOREIGN KEY (nation_id) REFERENCES nation(nation_id)
);

CREATE TABLE location (
    location_id integer NOT NULL,
    location text NOT NULL,
    location2 text,
    county text NOT NULL,
    town_id integer NOT NULL,
    zip_code text,
    tel text NOT NULL,
    modified_on timestamp NOT NULL,
    PRIMARY KEY (location_id),
    FOREIGN KEY (town_id) REFERENCES town(town_id)
);

CREATE TABLE section (
    section_id integer NOT NULL,
    label text NOT NULL,
    modified_on timestamp NOT NULL,
    PRIMARY KEY (section_id)
);

CREATE TABLE branch (
    branch_id integer NOT NULL,
    lead_clerk_id integer NOT NULL,
    location_id integer NOT NULL,
    modified_on timestamp NOT NULL,
    PRIMARY KEY (branch_id),
    FOREIGN KEY (location_id) REFERENCES location(location_id)
);

CREATE TABLE client (
    client_id integer NOT NULL,
    branch_id integer NOT NULL,
    given_name text NOT NULL,
    family_name text NOT NULL,
    mail_addr text,
    location_id integer NOT NULL,
    enabled_flag boolean NOT NULL,
    created_date date NOT NULL,
    modified_on timestamp,
    enabled integer,
    PRIMARY KEY (client_id),
    FOREIGN KEY (location_id) REFERENCES location(location_id),
    FOREIGN KEY (branch_id) REFERENCES branch(branch_id)
);

CREATE TABLE locale (
    locale_id integer NOT NULL,
    label char(20) NOT NULL,
    modified_on timestamp NOT NULL,
    PRIMARY KEY (locale_id)
);

CREATE TABLE movie (
    movie_id integer NOT NULL,
    designation text NOT NULL,
    summary text,
    issued_year integer,
    locale_id integer NOT NULL,
    source_locale_id integer,
    loan_period smallint NOT NULL,
    loan_fee numeric(4,2) NOT NULL,
    runtime smallint,
    replace_cost numeric(5,2) NOT NULL,
    certificate text CHECK (certificate IN ('G', 'PG', 'PG-13', 'R', 'NC-17')),
    modified_on timestamp NOT NULL,
    extra_options text,
    PRIMARY KEY (movie_id),
    FOREIGN KEY (locale_id) REFERENCES locale(locale_id),
    FOREIGN KEY (source_locale_id) REFERENCES locale(locale_id)
);

CREATE TABLE movie_cast_member (
    cast_member_id integer NOT NULL,
    movie_id integer NOT NULL,
    modified_on timestamp NOT NULL,
    PRIMARY KEY (cast_member_id, movie_id),
    FOREIGN KEY (cast_member_id) REFERENCES cast_member(cast_member_id),
    FOREIGN KEY (movie_id) REFERENCES movie(movie_id)
);

CREATE TABLE movie_section (
    movie_id integer NOT NULL,
    section_id integer NOT NULL,
    modified_on timestamp NOT NULL,
    PRIMARY KEY (movie_id, section_id),
    FOREIGN KEY (section_id) REFERENCES section(section_id),
    FOREIGN KEY (movie_id) REFERENCES movie(movie_id)
);

CREATE TABLE stock (
    stock_id integer NOT NULL,
    movie_id integer NOT NULL,
    branch_id integer NOT NULL,
    modified_on timestamp NOT NULL,
    PRIMARY KEY (stock_id),
    FOREIGN KEY (movie_id) REFERENCES movie(movie_id),
    FOREIGN KEY (branch_id) REFERENCES branch(branch_id)
);

CREATE TABLE receipt (
    receipt_id integer NOT NULL,
    client_id integer NOT NULL,
    clerk_id integer NOT NULL,
    loan_id integer NOT NULL,
    value_paid numeric(5,2) NOT NULL,
    receipt_date timestamp NOT NULL,
    PRIMARY KEY (receipt_date, receipt_id)
);

CREATE TABLE clerk (
    clerk_id integer NOT NULL,
    given_name text NOT NULL,
    family_name text NOT NULL,
    location_id integer NOT NULL,
    mail_addr text,
    branch_id integer NOT NULL,
    enabled boolean NOT NULL,
    login text NOT NULL,
    secret text,
    modified_on timestamp NOT NULL,
    graphic bytea,
    PRIMARY KEY (clerk_id),
    FOREIGN KEY (location_id) REFERENCES location(location_id),
    FOREIGN KEY (branch_id) REFERENCES branch(branch_id)
);

CREATE TABLE loan (
    loan_id integer NOT NULL,
    loan_date timestamp NOT NULL,
    stock_id integer NOT NULL,
    client_id integer NOT NULL,
    returned_date timestamp,
    clerk_id integer NOT NULL,
    modified_on timestamp NOT NULL,
    PRIMARY KEY (loan_id),
    FOREIGN KEY (client_id) REFERENCES client(client_id),
    FOREIGN KEY (stock_id) REFERENCES stock(stock_id),
    FOREIGN KEY (clerk_id) REFERENCES clerk(clerk_id)
);
