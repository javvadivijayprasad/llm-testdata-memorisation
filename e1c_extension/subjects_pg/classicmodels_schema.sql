-- classicmodels (mysqltutorial.org sample database, dump mirrored at github.com/bklogic/example-data-access-service db/mysqlsampledatabase.sql)
-- converted to PostgreSQL: identifiers folded to lower case, int(n)->integer, decimal->numeric, mediumtext->text, mediumblob->bytea; PK/FK/NOT NULL preserved, indexes dropped.
CREATE TABLE productlines (
  productline varchar(50) NOT NULL,
  textdescription varchar(4000),
  htmldescription text,
  image bytea,
  PRIMARY KEY (productLine)
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
  PRIMARY KEY (productCode),
  FOREIGN KEY (productLine) REFERENCES productlines (productLine)
);

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
  PRIMARY KEY (officeCode)
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
  PRIMARY KEY (employeeNumber),
  FOREIGN KEY (reportsTo) REFERENCES employees (employeeNumber),
  FOREIGN KEY (officeCode) REFERENCES offices (officeCode)
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
  PRIMARY KEY (customerNumber),
  FOREIGN KEY (salesRepEmployeeNumber) REFERENCES employees (employeeNumber)
);

CREATE TABLE orders (
  ordernumber integer NOT NULL,
  orderdate date NOT NULL,
  requireddate date NOT NULL,
  shippeddate date,
  status varchar(15) NOT NULL,
  comments text,
  customernumber integer NOT NULL,
  PRIMARY KEY (orderNumber),
  FOREIGN KEY (customerNumber) REFERENCES customers (customerNumber)
);

CREATE TABLE orderdetails (
  ordernumber integer NOT NULL,
  productcode varchar(15) NOT NULL,
  quantityordered integer NOT NULL,
  priceeach numeric(10,2) NOT NULL,
  orderlinenumber smallint NOT NULL,
  PRIMARY KEY (orderNumber,productCode),
  FOREIGN KEY (orderNumber) REFERENCES orders (orderNumber),
  FOREIGN KEY (productCode) REFERENCES products (productCode)
);

CREATE TABLE payments (
  customernumber integer NOT NULL,
  checknumber varchar(50) NOT NULL,
  paymentdate date NOT NULL,
  amount numeric(10,2) NOT NULL,
  PRIMARY KEY (customerNumber,checkNumber),
  FOREIGN KEY (customerNumber) REFERENCES customers (customerNumber)
);
