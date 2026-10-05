CREATE TABLE brands (
    brand_id integer NOT NULL,
    brand_name varchar(255) NOT NULL,
    PRIMARY KEY (brand_id)
);

CREATE TABLE categories (
    category_id integer NOT NULL,
    category_name varchar(255) NOT NULL,
    PRIMARY KEY (category_id)
);

CREATE TABLE customers (
    customer_id integer NOT NULL,
    first_name varchar(255) NOT NULL,
    last_name varchar(255) NOT NULL,
    phone varchar(25),
    email varchar(255) NOT NULL,
    street varchar(255),
    city varchar(50),
    state varchar(25),
    zip_code varchar(5),
    PRIMARY KEY (customer_id)
);

CREATE TABLE stores (
    store_id integer NOT NULL,
    store_name varchar(255) NOT NULL,
    phone varchar(25),
    email varchar(255),
    street varchar(255),
    city varchar(255),
    state varchar(10),
    zip_code varchar(5),
    PRIMARY KEY (store_id)
);

CREATE TABLE staffs (
    staff_id integer NOT NULL,
    first_name varchar(50) NOT NULL,
    last_name varchar(50) NOT NULL,
    email varchar(255) NOT NULL,
    phone varchar(25),
    active smallint NOT NULL,
    store_id integer NOT NULL,
    manager_id integer,
    UNIQUE (email),
    PRIMARY KEY (staff_id),
    FOREIGN KEY (manager_id) REFERENCES staffs(staff_id),
    FOREIGN KEY (store_id) REFERENCES stores(store_id)
);

CREATE TABLE orders (
    order_id integer NOT NULL,
    customer_id integer,
    order_status smallint NOT NULL,
    order_date date NOT NULL,
    required_date date NOT NULL,
    shipped_date date,
    store_id integer NOT NULL,
    staff_id integer NOT NULL,
    PRIMARY KEY (order_id),
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (staff_id) REFERENCES staffs(staff_id),
    FOREIGN KEY (store_id) REFERENCES stores(store_id)
);

CREATE TABLE products (
    product_id integer NOT NULL,
    product_name varchar(255) NOT NULL,
    brand_id integer NOT NULL,
    category_id integer NOT NULL,
    model_year smallint NOT NULL,
    list_price numeric(10,2) NOT NULL,
    PRIMARY KEY (product_id),
    FOREIGN KEY (brand_id) REFERENCES brands(brand_id),
    FOREIGN KEY (category_id) REFERENCES categories(category_id)
);

CREATE TABLE order_items (
    order_id integer NOT NULL,
    item_id integer NOT NULL,
    product_id integer NOT NULL,
    quantity integer NOT NULL,
    list_price numeric(10,2) NOT NULL,
    discount numeric(4,2) NOT NULL,
    PRIMARY KEY (order_id, item_id),
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

CREATE TABLE stocks (
    store_id integer NOT NULL,
    product_id integer NOT NULL,
    quantity integer,
    PRIMARY KEY (store_id, product_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id),
    FOREIGN KEY (store_id) REFERENCES stores(store_id)
);
