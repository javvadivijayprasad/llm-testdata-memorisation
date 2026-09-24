CREATE TABLE categories (
    category integer NOT NULL,
    categoryname varchar(50) NOT NULL,
    PRIMARY KEY (category)
);

CREATE TABLE customers (
    customerid integer NOT NULL,
    firstname varchar(50) NOT NULL,
    lastname varchar(50) NOT NULL,
    address1 varchar(50) NOT NULL,
    address2 varchar(50),
    city varchar(50) NOT NULL,
    state varchar(50),
    zip integer,
    country varchar(50) NOT NULL,
    region smallint NOT NULL,
    email varchar(50),
    phone varchar(50),
    creditcardtype integer NOT NULL,
    creditcard varchar(50) NOT NULL,
    creditcardexpiration varchar(50) NOT NULL,
    username varchar(50) NOT NULL,
    password varchar(50) NOT NULL,
    age smallint,
    income integer,
    gender varchar(1),
    PRIMARY KEY (customerid)
);

CREATE TABLE cust_hist (
    customerid integer NOT NULL,
    orderid integer NOT NULL,
    prod_id integer NOT NULL,
    FOREIGN KEY (customerid) REFERENCES customers(customerid)
);

CREATE TABLE inventory (
    prod_id integer NOT NULL,
    quan_in_stock integer NOT NULL,
    sales integer NOT NULL,
    PRIMARY KEY (prod_id)
);

CREATE TABLE orders (
    orderid integer NOT NULL,
    orderdate date NOT NULL,
    customerid integer,
    netamount numeric(12,2) NOT NULL,
    tax numeric(12,2) NOT NULL,
    totalamount numeric(12,2) NOT NULL,
    PRIMARY KEY (orderid),
    FOREIGN KEY (customerid) REFERENCES customers(customerid)
);

CREATE TABLE orderlines (
    orderlineid integer NOT NULL,
    orderid integer NOT NULL,
    prod_id integer NOT NULL,
    quantity smallint NOT NULL,
    orderdate date NOT NULL,
    FOREIGN KEY (orderid) REFERENCES orders(orderid)
);

CREATE TABLE products (
    prod_id integer NOT NULL,
    category integer NOT NULL,
    title varchar(50) NOT NULL,
    actor varchar(50) NOT NULL,
    price numeric(12,2) NOT NULL,
    special smallint,
    common_prod_id integer NOT NULL,
    PRIMARY KEY (prod_id)
);

CREATE TABLE reorder (
    prod_id integer NOT NULL,
    date_low date NOT NULL,
    quan_low integer NOT NULL,
    date_reordered date,
    quan_reordered integer,
    date_expected date
);
