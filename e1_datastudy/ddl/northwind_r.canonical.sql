CREATE TABLE sections (
    section_id smallint NOT NULL,
    section_name varchar(15) NOT NULL,
    summary text,
    graphic bytea,
    PRIMARY KEY (section_id)
);

CREATE TABLE client_profiles (
    client_type_id varchar(5) NOT NULL,
    client_text text,
    PRIMARY KEY (client_type_id)
);

CREATE TABLE clients (
    client_id varchar(5) NOT NULL,
    firm_name varchar(40) NOT NULL,
    contact_person varchar(30),
    contact_designation varchar(30),
    location varchar(60),
    town varchar(15),
    zone varchar(15),
    zip_code varchar(10),
    nation varchar(15),
    tel varchar(24),
    fax_no varchar(24),
    PRIMARY KEY (client_id)
);

CREATE TABLE client_client_profile (
    client_id varchar(5) NOT NULL,
    client_type_id varchar(5) NOT NULL,
    PRIMARY KEY (client_id, client_type_id),
    FOREIGN KEY (client_type_id) REFERENCES client_profiles(client_type_id),
    FOREIGN KEY (client_id) REFERENCES clients(client_id)
);

CREATE TABLE workers (
    worker_id smallint NOT NULL,
    family_name varchar(20) NOT NULL,
    given_name varchar(10) NOT NULL,
    designation varchar(30),
    honorific varchar(25),
    born_date date,
    joined_date date,
    location varchar(60),
    town varchar(15),
    zone varchar(15),
    zip_code varchar(10),
    nation varchar(15),
    home_tel varchar(24),
    ext_no varchar(4),
    image bytea,
    remarks text,
    manager_ref smallint,
    image_path varchar(255),
    PRIMARY KEY (worker_id),
    FOREIGN KEY (manager_ref) REFERENCES workers(worker_id)
);

CREATE TABLE zone (
    zone_id smallint NOT NULL,
    zone_text varchar(60) NOT NULL,
    PRIMARY KEY (zone_id)
);

CREATE TABLE areas (
    area_id varchar(20) NOT NULL,
    area_text varchar(60) NOT NULL,
    zone_id smallint NOT NULL,
    PRIMARY KEY (area_id),
    FOREIGN KEY (zone_id) REFERENCES zone(zone_id)
);

CREATE TABLE worker_areas (
    worker_id smallint NOT NULL,
    area_id varchar(20) NOT NULL,
    PRIMARY KEY (worker_id, area_id),
    FOREIGN KEY (worker_id) REFERENCES workers(worker_id),
    FOREIGN KEY (area_id) REFERENCES areas(area_id)
);

CREATE TABLE carriers (
    carrier_id smallint NOT NULL,
    firm_name varchar(40) NOT NULL,
    tel varchar(24),
    PRIMARY KEY (carrier_id)
);

CREATE TABLE purchases (
    purchase_id smallint NOT NULL,
    client_id varchar(5),
    worker_id smallint,
    purchase_date date,
    due_date date,
    dispatched_date date,
    deliver_by smallint,
    shipping_fee real,
    deliver_name varchar(40),
    deliver_location varchar(60),
    deliver_town varchar(15),
    deliver_zone varchar(15),
    deliver_zip_code varchar(10),
    deliver_nation varchar(15),
    PRIMARY KEY (purchase_id),
    FOREIGN KEY (client_id) REFERENCES clients(client_id),
    FOREIGN KEY (worker_id) REFERENCES workers(worker_id),
    FOREIGN KEY (deliver_by) REFERENCES carriers(carrier_id)
);

CREATE TABLE vendors (
    vendor_id smallint NOT NULL,
    firm_name varchar(40) NOT NULL,
    contact_person varchar(30),
    contact_designation varchar(30),
    location varchar(60),
    town varchar(15),
    zone varchar(15),
    zip_code varchar(10),
    nation varchar(15),
    tel varchar(24),
    fax_no varchar(24),
    website text,
    PRIMARY KEY (vendor_id)
);

CREATE TABLE items (
    item_id smallint NOT NULL,
    item_name varchar(40) NOT NULL,
    vendor_id smallint,
    section_id smallint,
    qty_per_each varchar(20),
    each_cost real,
    pieces_in_stock smallint,
    pieces_on_purchase smallint,
    restock_threshold smallint,
    retired integer NOT NULL,
    PRIMARY KEY (item_id),
    FOREIGN KEY (section_id) REFERENCES sections(section_id),
    FOREIGN KEY (vendor_id) REFERENCES vendors(vendor_id)
);

CREATE TABLE purchase_lines (
    purchase_id smallint NOT NULL,
    item_id smallint NOT NULL,
    each_cost real NOT NULL,
    qty smallint NOT NULL,
    rebate real NOT NULL,
    PRIMARY KEY (purchase_id, item_id),
    FOREIGN KEY (purchase_id) REFERENCES purchases(purchase_id),
    FOREIGN KEY (item_id) REFERENCES items(item_id)
);

CREATE TABLE state_codes (
    province_id smallint NOT NULL,
    province_name varchar(100),
    province_code varchar(2),
    province_zone varchar(50),
    PRIMARY KEY (province_id)
);
