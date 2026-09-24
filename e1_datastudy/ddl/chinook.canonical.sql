CREATE TABLE artist (
    artist_id integer NOT NULL,
    name varchar(120),
    PRIMARY KEY (artist_id)
);

CREATE TABLE album (
    album_id integer NOT NULL,
    title varchar(160) NOT NULL,
    artist_id integer NOT NULL,
    PRIMARY KEY (album_id),
    FOREIGN KEY (artist_id) REFERENCES artist(artist_id)
);

CREATE TABLE employee (
    employee_id integer NOT NULL,
    last_name varchar(20) NOT NULL,
    first_name varchar(20) NOT NULL,
    title varchar(30),
    reports_to integer,
    birth_date timestamp,
    hire_date timestamp,
    address varchar(70),
    city varchar(40),
    state varchar(40),
    country varchar(40),
    postal_code varchar(10),
    phone varchar(24),
    fax varchar(24),
    email varchar(60),
    PRIMARY KEY (employee_id),
    FOREIGN KEY (reports_to) REFERENCES employee(employee_id)
);

CREATE TABLE customer (
    customer_id integer NOT NULL,
    first_name varchar(40) NOT NULL,
    last_name varchar(20) NOT NULL,
    company varchar(80),
    address varchar(70),
    city varchar(40),
    state varchar(40),
    country varchar(40),
    postal_code varchar(10),
    phone varchar(24),
    fax varchar(24),
    email varchar(60) NOT NULL,
    support_rep_id integer,
    PRIMARY KEY (customer_id),
    FOREIGN KEY (support_rep_id) REFERENCES employee(employee_id)
);

CREATE TABLE genre (
    genre_id integer NOT NULL,
    name varchar(120),
    PRIMARY KEY (genre_id)
);

CREATE TABLE invoice (
    invoice_id integer NOT NULL,
    customer_id integer NOT NULL,
    invoice_date timestamp NOT NULL,
    billing_address varchar(70),
    billing_city varchar(40),
    billing_state varchar(40),
    billing_country varchar(40),
    billing_postal_code varchar(10),
    total numeric(10,2) NOT NULL,
    PRIMARY KEY (invoice_id),
    FOREIGN KEY (customer_id) REFERENCES customer(customer_id)
);

CREATE TABLE media_type (
    media_type_id integer NOT NULL,
    name varchar(120),
    PRIMARY KEY (media_type_id)
);

CREATE TABLE track (
    track_id integer NOT NULL,
    name varchar(200) NOT NULL,
    album_id integer,
    media_type_id integer NOT NULL,
    genre_id integer,
    composer varchar(220),
    milliseconds integer NOT NULL,
    bytes integer,
    unit_price numeric(10,2) NOT NULL,
    PRIMARY KEY (track_id),
    FOREIGN KEY (album_id) REFERENCES album(album_id),
    FOREIGN KEY (genre_id) REFERENCES genre(genre_id),
    FOREIGN KEY (media_type_id) REFERENCES media_type(media_type_id)
);

CREATE TABLE invoice_line (
    invoice_line_id integer NOT NULL,
    invoice_id integer NOT NULL,
    track_id integer NOT NULL,
    unit_price numeric(10,2) NOT NULL,
    quantity integer NOT NULL,
    PRIMARY KEY (invoice_line_id),
    FOREIGN KEY (invoice_id) REFERENCES invoice(invoice_id),
    FOREIGN KEY (track_id) REFERENCES track(track_id)
);

CREATE TABLE playlist (
    playlist_id integer NOT NULL,
    name varchar(120),
    PRIMARY KEY (playlist_id)
);

CREATE TABLE playlist_track (
    playlist_id integer NOT NULL,
    track_id integer NOT NULL,
    PRIMARY KEY (playlist_id, track_id),
    FOREIGN KEY (playlist_id) REFERENCES playlist(playlist_id),
    FOREIGN KEY (track_id) REFERENCES track(track_id)
);
