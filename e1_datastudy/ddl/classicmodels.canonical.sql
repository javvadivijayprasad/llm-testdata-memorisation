CREATE TABLE offices (
    officecode varchar(10) NOT NULL,
    city varchar(50) NOT NULL,
    phone varchar(50) NOT NULL,
    addressline1 varchar(50) NOT NULL,
    addressline2 varchar(50),
    state varchar(50),
    country varchar(50) NOT NULL,
    postalcode varchar(15) NOT NULL,
    territory varchar(10) NOT NULL,
    PRIMARY KEY (officecode)
);

CREATE TABLE employees (
    employeenumber integer NOT NULL,
    lastname varchar(50) NOT NULL,
    firstname varchar(50) NOT NULL,
    extension varchar(10) NOT NULL,
    email varchar(100) NOT NULL,
    officecode varchar(10) NOT NULL,
    reportsto integer,
    jobtitle varchar(50) NOT NULL,
    PRIMARY KEY (employeenumber),
    FOREIGN KEY (officecode) REFERENCES offices(officecode),
    FOREIGN KEY (reportsto) REFERENCES employees(employeenumber)
);

CREATE TABLE customers (
    customernumber integer NOT NULL,
    customername varchar(50) NOT NULL,
    contactlastname varchar(50) NOT NULL,
    contactfirstname varchar(50) NOT NULL,
    phone varchar(50) NOT NULL,
    addressline1 varchar(50) NOT NULL,
    addressline2 varchar(50),
    city varchar(50) NOT NULL,
    state varchar(50),
    postalcode varchar(15),
    country varchar(50) NOT NULL,
    salesrepemployeenumber integer,
    creditlimit numeric(10,2),
    PRIMARY KEY (customernumber),
    FOREIGN KEY (salesrepemployeenumber) REFERENCES employees(employeenumber)
);

CREATE TABLE orders (
    ordernumber integer NOT NULL,
    orderdate date NOT NULL,
    requireddate date NOT NULL,
    shippeddate date,
    status varchar(15) NOT NULL,
    comments text,
    customernumber integer NOT NULL,
    PRIMARY KEY (ordernumber),
    FOREIGN KEY (customernumber) REFERENCES customers(customernumber)
);

CREATE TABLE productlines (
    productline varchar(50) NOT NULL,
    textdescription varchar(4000),
    htmldescription text,
    image bytea,
    PRIMARY KEY (productline)
);

CREATE TABLE products (
    productcode varchar(50) NOT NULL,
    productname varchar(70) NOT NULL,
    productline varchar(50) NOT NULL,
    productscale varchar(10) NOT NULL,
    productvendor varchar(50) NOT NULL,
    productdescription text NOT NULL,
    quantityinstock smallint NOT NULL,
    buyprice numeric(10,2) NOT NULL,
    msrp numeric(10,2) NOT NULL,
    PRIMARY KEY (productcode),
    FOREIGN KEY (productline) REFERENCES productlines(productline)
);

CREATE TABLE orderdetails (
    ordernumber integer NOT NULL,
    productcode varchar(15) NOT NULL,
    quantityordered integer NOT NULL,
    priceeach numeric(10,2) NOT NULL,
    orderlinenumber smallint NOT NULL,
    PRIMARY KEY (ordernumber, productcode),
    FOREIGN KEY (ordernumber) REFERENCES orders(ordernumber),
    FOREIGN KEY (productcode) REFERENCES products(productcode)
);

CREATE TABLE payments (
    customernumber integer NOT NULL,
    checknumber varchar(50) NOT NULL,
    paymentdate date NOT NULL,
    amount numeric(10,2) NOT NULL,
    PRIMARY KEY (customernumber, checknumber),
    FOREIGN KEY (customernumber) REFERENCES customers(customernumber)
);
