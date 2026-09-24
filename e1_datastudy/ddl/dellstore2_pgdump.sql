--
-- PostgreSQL database dump
--

\restrict vCWJV3RtykPlDlsXzpFsag9qwZF4kS3BESgeQExf0yTkGkNTxZIFyGbknXXsHmo

-- Dumped from database version 16.13 (Ubuntu 16.13-0ubuntu0.24.04.1)
-- Dumped by pg_dump version 16.13 (Ubuntu 16.13-0ubuntu0.24.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: public; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA public;


--
-- Name: SCHEMA public; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA public IS 'standard public schema';


--
-- Name: new_customer(character varying, character varying, character varying, character varying, character varying, character varying, integer, character varying, integer, character varying, character varying, integer, character varying, character varying, character varying, character varying, integer, integer, character varying); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.new_customer(firstname_in character varying, lastname_in character varying, address1_in character varying, address2_in character varying, city_in character varying, state_in character varying, zip_in integer, country_in character varying, region_in integer, email_in character varying, phone_in character varying, creditcardtype_in integer, creditcard_in character varying, creditcardexpiration_in character varying, username_in character varying, password_in character varying, age_in integer, income_in integer, gender_in character varying, OUT customerid_out integer) RETURNS integer
    LANGUAGE plpgsql
    AS $$
  DECLARE
    rows_returned INT;
  BEGIN
    SELECT COUNT(*) INTO rows_returned FROM CUSTOMERS WHERE USERNAME = username_in;
    IF rows_returned = 0 THEN
	    INSERT INTO CUSTOMERS
	      (
	      FIRSTNAME,
	      LASTNAME,
	      EMAIL,
	      PHONE,
	      USERNAME,
	      PASSWORD,
	      ADDRESS1,
	      ADDRESS2,
	      CITY,
	      STATE,
	      ZIP,
	      COUNTRY,
	      REGION,
	      CREDITCARDTYPE,
	      CREDITCARD,
	      CREDITCARDEXPIRATION,
	      AGE,
	      INCOME,
	      GENDER
	      )
	    VALUES
	      (
	      firstname_in,
	      lastname_in,
	      email_in,
	      phone_in,
	      username_in,
	      password_in,
	      address1_in,
	      address2_in,
	      city_in,
	      state_in,
	      zip_in,
	      country_in,
	      region_in,
	      creditcardtype_in,
	      creditcard_in,
	      creditcardexpiration_in,
	      age_in,
	      income_in,
	      gender_in
	      )
	     ;
    select currval(pg_get_serial_sequence('customers', 'customerid')) into customerid_out;
  ELSE 
  	customerid_out := 0;
  END IF;
END
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: categories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.categories (
    category integer NOT NULL,
    categoryname character varying(50) NOT NULL
);


--
-- Name: categories_category_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.categories_category_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: categories_category_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.categories_category_seq OWNED BY public.categories.category;


--
-- Name: cust_hist; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cust_hist (
    customerid integer NOT NULL,
    orderid integer NOT NULL,
    prod_id integer NOT NULL
);


--
-- Name: customers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.customers (
    customerid integer NOT NULL,
    firstname character varying(50) NOT NULL,
    lastname character varying(50) NOT NULL,
    address1 character varying(50) NOT NULL,
    address2 character varying(50),
    city character varying(50) NOT NULL,
    state character varying(50),
    zip integer,
    country character varying(50) NOT NULL,
    region smallint NOT NULL,
    email character varying(50),
    phone character varying(50),
    creditcardtype integer NOT NULL,
    creditcard character varying(50) NOT NULL,
    creditcardexpiration character varying(50) NOT NULL,
    username character varying(50) NOT NULL,
    password character varying(50) NOT NULL,
    age smallint,
    income integer,
    gender character varying(1)
);


--
-- Name: customers_customerid_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.customers_customerid_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: customers_customerid_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.customers_customerid_seq OWNED BY public.customers.customerid;


--
-- Name: inventory; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.inventory (
    prod_id integer NOT NULL,
    quan_in_stock integer NOT NULL,
    sales integer NOT NULL
);


--
-- Name: orderlines; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.orderlines (
    orderlineid integer NOT NULL,
    orderid integer NOT NULL,
    prod_id integer NOT NULL,
    quantity smallint NOT NULL,
    orderdate date NOT NULL
);


--
-- Name: orders; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.orders (
    orderid integer NOT NULL,
    orderdate date NOT NULL,
    customerid integer,
    netamount numeric(12,2) NOT NULL,
    tax numeric(12,2) NOT NULL,
    totalamount numeric(12,2) NOT NULL
);


--
-- Name: orders_orderid_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.orders_orderid_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: orders_orderid_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.orders_orderid_seq OWNED BY public.orders.orderid;


--
-- Name: products; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.products (
    prod_id integer NOT NULL,
    category integer NOT NULL,
    title character varying(50) NOT NULL,
    actor character varying(50) NOT NULL,
    price numeric(12,2) NOT NULL,
    special smallint,
    common_prod_id integer NOT NULL
);


--
-- Name: products_prod_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.products_prod_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: products_prod_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.products_prod_id_seq OWNED BY public.products.prod_id;


--
-- Name: reorder; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.reorder (
    prod_id integer NOT NULL,
    date_low date NOT NULL,
    quan_low integer NOT NULL,
    date_reordered date,
    quan_reordered integer,
    date_expected date
);


--
-- Name: categories category; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categories ALTER COLUMN category SET DEFAULT nextval('public.categories_category_seq'::regclass);


--
-- Name: customers customerid; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.customers ALTER COLUMN customerid SET DEFAULT nextval('public.customers_customerid_seq'::regclass);


--
-- Name: orders orderid; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.orders ALTER COLUMN orderid SET DEFAULT nextval('public.orders_orderid_seq'::regclass);


--
-- Name: products prod_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.products ALTER COLUMN prod_id SET DEFAULT nextval('public.products_prod_id_seq'::regclass);


--
-- Name: categories categories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_pkey PRIMARY KEY (category);


--
-- Name: customers customers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.customers
    ADD CONSTRAINT customers_pkey PRIMARY KEY (customerid);


--
-- Name: inventory inventory_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventory
    ADD CONSTRAINT inventory_pkey PRIMARY KEY (prod_id);


--
-- Name: orders orders_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_pkey PRIMARY KEY (orderid);


--
-- Name: products products_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.products
    ADD CONSTRAINT products_pkey PRIMARY KEY (prod_id);


--
-- Name: ix_cust_hist_customerid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_cust_hist_customerid ON public.cust_hist USING btree (customerid);


--
-- Name: ix_cust_username; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_cust_username ON public.customers USING btree (username);


--
-- Name: ix_order_custid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_order_custid ON public.orders USING btree (customerid);


--
-- Name: ix_orderlines_orderid; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_orderlines_orderid ON public.orderlines USING btree (orderid, orderlineid);


--
-- Name: ix_prod_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_prod_category ON public.products USING btree (category);


--
-- Name: ix_prod_special; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_prod_special ON public.products USING btree (special);


--
-- Name: cust_hist fk_cust_hist_customerid; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cust_hist
    ADD CONSTRAINT fk_cust_hist_customerid FOREIGN KEY (customerid) REFERENCES public.customers(customerid) ON DELETE CASCADE;


--
-- Name: orders fk_customerid; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT fk_customerid FOREIGN KEY (customerid) REFERENCES public.customers(customerid) ON DELETE SET NULL;


--
-- Name: orderlines fk_orderid; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.orderlines
    ADD CONSTRAINT fk_orderid FOREIGN KEY (orderid) REFERENCES public.orders(orderid) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict vCWJV3RtykPlDlsXzpFsag9qwZF4kS3BESgeQExf0yTkGkNTxZIFyGbknXXsHmo

