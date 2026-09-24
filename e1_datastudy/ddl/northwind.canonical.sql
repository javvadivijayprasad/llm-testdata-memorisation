CREATE TABLE categories (
    category_id smallint NOT NULL,
    category_name varchar(15) NOT NULL,
    description text,
    picture bytea,
    PRIMARY KEY (category_id)
);

CREATE TABLE customer_demographics (
    customer_type_id varchar(5) NOT NULL,
    customer_desc text,
    PRIMARY KEY (customer_type_id)
);

CREATE TABLE customers (
    customer_id varchar(5) NOT NULL,
    company_name varchar(40) NOT NULL,
    contact_name varchar(30),
    contact_title varchar(30),
    address varchar(60),
    city varchar(15),
    region varchar(15),
    postal_code varchar(10),
    country varchar(15),
    phone varchar(24),
    fax varchar(24),
    PRIMARY KEY (customer_id)
);

CREATE TABLE customer_customer_demo (
    customer_id varchar(5) NOT NULL,
    customer_type_id varchar(5) NOT NULL,
    PRIMARY KEY (customer_id, customer_type_id),
    FOREIGN KEY (customer_type_id) REFERENCES customer_demographics(customer_type_id),
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE employees (
    employee_id smallint NOT NULL,
    last_name varchar(20) NOT NULL,
    first_name varchar(10) NOT NULL,
    title varchar(30),
    title_of_courtesy varchar(25),
    birth_date date,
    hire_date date,
    address varchar(60),
    city varchar(15),
    region varchar(15),
    postal_code varchar(10),
    country varchar(15),
    home_phone varchar(24),
    extension varchar(4),
    photo bytea,
    notes text,
    reports_to smallint,
    photo_path varchar(255),
    PRIMARY KEY (employee_id),
    FOREIGN KEY (reports_to) REFERENCES employees(employee_id)
);

CREATE TABLE region (
    region_id smallint NOT NULL,
    region_description varchar(60) NOT NULL,
    PRIMARY KEY (region_id)
);

CREATE TABLE territories (
    territory_id varchar(20) NOT NULL,
    territory_description varchar(60) NOT NULL,
    region_id smallint NOT NULL,
    PRIMARY KEY (territory_id),
    FOREIGN KEY (region_id) REFERENCES region(region_id)
);

CREATE TABLE employee_territories (
    employee_id smallint NOT NULL,
    territory_id varchar(20) NOT NULL,
    PRIMARY KEY (employee_id, territory_id),
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id),
    FOREIGN KEY (territory_id) REFERENCES territories(territory_id)
);

CREATE TABLE shippers (
    shipper_id smallint NOT NULL,
    company_name varchar(40) NOT NULL,
    phone varchar(24),
    PRIMARY KEY (shipper_id)
);

CREATE TABLE orders (
    order_id smallint NOT NULL,
    customer_id varchar(5),
    employee_id smallint,
    order_date date,
    required_date date,
    shipped_date date,
    ship_via smallint,
    freight real,
    ship_name varchar(40),
    ship_address varchar(60),
    ship_city varchar(15),
    ship_region varchar(15),
    ship_postal_code varchar(10),
    ship_country varchar(15),
    PRIMARY KEY (order_id),
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id),
    FOREIGN KEY (ship_via) REFERENCES shippers(shipper_id)
);

CREATE TABLE suppliers (
    supplier_id smallint NOT NULL,
    company_name varchar(40) NOT NULL,
    contact_name varchar(30),
    contact_title varchar(30),
    address varchar(60),
    city varchar(15),
    region varchar(15),
    postal_code varchar(10),
    country varchar(15),
    phone varchar(24),
    fax varchar(24),
    homepage text,
    PRIMARY KEY (supplier_id)
);

CREATE TABLE products (
    product_id smallint NOT NULL,
    product_name varchar(40) NOT NULL,
    supplier_id smallint,
    category_id smallint,
    quantity_per_unit varchar(20),
    unit_price real,
    units_in_stock smallint,
    units_on_order smallint,
    reorder_level smallint,
    discontinued integer NOT NULL,
    PRIMARY KEY (product_id),
    FOREIGN KEY (category_id) REFERENCES categories(category_id),
    FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
);

CREATE TABLE order_details (
    order_id smallint NOT NULL,
    product_id smallint NOT NULL,
    unit_price real NOT NULL,
    quantity smallint NOT NULL,
    discount real NOT NULL,
    PRIMARY KEY (order_id, product_id),
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

CREATE TABLE us_states (
    state_id smallint NOT NULL,
    state_name varchar(100),
    state_abbr varchar(2),
    state_region varchar(50),
    PRIMARY KEY (state_id)
);
