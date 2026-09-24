CREATE TABLE sections (
    section integer NOT NULL,
    section_label varchar(50) NOT NULL,
    PRIMARY KEY (section)
);

CREATE TABLE clients (
    client_id integer NOT NULL,
    given_name varchar(50) NOT NULL,
    family_name varchar(50) NOT NULL,
    location1 varchar(50) NOT NULL,
    location2 varchar(50),
    town varchar(50) NOT NULL,
    province varchar(50),
    postcode integer,
    nation varchar(50) NOT NULL,
    zone smallint NOT NULL,
    mail_addr varchar(50),
    tel varchar(50),
    card_type integer NOT NULL,
    card_no varchar(50) NOT NULL,
    card_expiry varchar(50) NOT NULL,
    login varchar(50) NOT NULL,
    secret varchar(50) NOT NULL,
    years_old smallint,
    earnings integer,
    sex_code varchar(1),
    PRIMARY KEY (client_id)
);

CREATE TABLE cli_history (
    client_id integer NOT NULL,
    purchase_id integer NOT NULL,
    item_id integer NOT NULL,
    FOREIGN KEY (client_id) REFERENCES clients(client_id)
);

CREATE TABLE stock (
    item_id integer NOT NULL,
    qty_in_stock integer NOT NULL,
    sold_count integer NOT NULL,
    PRIMARY KEY (item_id)
);

CREATE TABLE purchases (
    purchase_id integer NOT NULL,
    purchase_date date NOT NULL,
    client_id integer,
    net_value numeric(12,2) NOT NULL,
    levy numeric(12,2) NOT NULL,
    gross_value numeric(12,2) NOT NULL,
    PRIMARY KEY (purchase_id),
    FOREIGN KEY (client_id) REFERENCES clients(client_id)
);

CREATE TABLE purchase_lines (
    purchase_line_id integer NOT NULL,
    purchase_id integer NOT NULL,
    item_id integer NOT NULL,
    qty smallint NOT NULL,
    purchase_date date NOT NULL,
    FOREIGN KEY (purchase_id) REFERENCES purchases(purchase_id)
);

CREATE TABLE items (
    item_id integer NOT NULL,
    section integer NOT NULL,
    designation varchar(50) NOT NULL,
    cast_member varchar(50) NOT NULL,
    cost numeric(12,2) NOT NULL,
    extra smallint,
    related_item_id integer NOT NULL,
    PRIMARY KEY (item_id)
);

CREATE TABLE restock (
    item_id integer NOT NULL,
    date_minimum date NOT NULL,
    qty_minimum integer NOT NULL,
    date_restocked date,
    qty_restocked integer,
    date_anticipated date
);
