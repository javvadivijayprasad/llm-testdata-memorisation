CREATE TABLE performer (
    performer_id integer NOT NULL,
    label varchar(120),
    PRIMARY KEY (performer_id)
);

CREATE TABLE record (
    record_id integer NOT NULL,
    designation varchar(160) NOT NULL,
    performer_id integer NOT NULL,
    PRIMARY KEY (record_id),
    FOREIGN KEY (performer_id) REFERENCES performer(performer_id)
);

CREATE TABLE worker (
    worker_id integer NOT NULL,
    family_name varchar(20) NOT NULL,
    given_name varchar(20) NOT NULL,
    designation varchar(30),
    manager_ref integer,
    born_date timestamp,
    joined_date timestamp,
    location varchar(70),
    town varchar(40),
    province varchar(40),
    nation varchar(40),
    zip_code varchar(10),
    tel varchar(24),
    fax_no varchar(24),
    mail_addr varchar(60),
    PRIMARY KEY (worker_id),
    FOREIGN KEY (manager_ref) REFERENCES worker(worker_id)
);

CREATE TABLE client (
    client_id integer NOT NULL,
    given_name varchar(40) NOT NULL,
    family_name varchar(20) NOT NULL,
    firm varchar(80),
    location varchar(70),
    town varchar(40),
    province varchar(40),
    nation varchar(40),
    zip_code varchar(10),
    tel varchar(24),
    fax_no varchar(24),
    mail_addr varchar(60) NOT NULL,
    agent_id integer,
    PRIMARY KEY (client_id),
    FOREIGN KEY (agent_id) REFERENCES worker(worker_id)
);

CREATE TABLE style (
    style_id integer NOT NULL,
    label varchar(120),
    PRIMARY KEY (style_id)
);

CREATE TABLE bill (
    bill_id integer NOT NULL,
    client_id integer NOT NULL,
    bill_date timestamp NOT NULL,
    charge_location varchar(70),
    charge_town varchar(40),
    charge_province varchar(40),
    charge_nation varchar(40),
    charge_zip_code varchar(10),
    sum_total numeric(10,2) NOT NULL,
    PRIMARY KEY (bill_id),
    FOREIGN KEY (client_id) REFERENCES client(client_id)
);

CREATE TABLE format_type (
    format_type_id integer NOT NULL,
    label varchar(120),
    PRIMARY KEY (format_type_id)
);

CREATE TABLE song (
    song_id integer NOT NULL,
    label varchar(200) NOT NULL,
    record_id integer,
    format_type_id integer NOT NULL,
    style_id integer,
    writer varchar(220),
    duration_ms integer NOT NULL,
    size_bytes integer,
    each_cost numeric(10,2) NOT NULL,
    PRIMARY KEY (song_id),
    FOREIGN KEY (record_id) REFERENCES record(record_id),
    FOREIGN KEY (style_id) REFERENCES style(style_id),
    FOREIGN KEY (format_type_id) REFERENCES format_type(format_type_id)
);

CREATE TABLE bill_line (
    bill_line_id integer NOT NULL,
    bill_id integer NOT NULL,
    song_id integer NOT NULL,
    each_cost numeric(10,2) NOT NULL,
    qty integer NOT NULL,
    PRIMARY KEY (bill_line_id),
    FOREIGN KEY (bill_id) REFERENCES bill(bill_id),
    FOREIGN KEY (song_id) REFERENCES song(song_id)
);

CREATE TABLE collection (
    collection_id integer NOT NULL,
    label varchar(120),
    PRIMARY KEY (collection_id)
);

CREATE TABLE collection_song (
    collection_id integer NOT NULL,
    song_id integer NOT NULL,
    PRIMARY KEY (collection_id, song_id),
    FOREIGN KEY (collection_id) REFERENCES collection(collection_id),
    FOREIGN KEY (song_id) REFERENCES song(song_id)
);
