--
-- PostgreSQL database dump
--

\restrict 1DuTFVauGGURGEsJdLE1b2gz0CZeYJPU4N3Z4P1bBcBCt5Lxf81Qthyf3Kokh0L

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


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: dept_emp; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dept_emp (
    emp_no integer NOT NULL,
    dept_no character(4) NOT NULL,
    from_date date NOT NULL,
    to_date date NOT NULL
);


--
-- Name: dept_emp_latest_date; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.dept_emp_latest_date AS
 SELECT emp_no,
    max(from_date) AS from_date,
    max(to_date) AS to_date
   FROM public.dept_emp
  GROUP BY emp_no;


--
-- Name: current_dept_emp; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.current_dept_emp AS
 SELECT l.emp_no,
    d.dept_no,
    l.from_date,
    l.to_date
   FROM (public.dept_emp d
     JOIN public.dept_emp_latest_date l ON (((d.emp_no = l.emp_no) AND (d.from_date = l.from_date) AND (l.to_date = d.to_date))));


--
-- Name: departments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.departments (
    dept_no character(4) NOT NULL,
    dept_name character varying(40) NOT NULL
);


--
-- Name: dept_manager; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dept_manager (
    emp_no integer NOT NULL,
    dept_no character(4) NOT NULL,
    from_date date NOT NULL,
    to_date date NOT NULL
);


--
-- Name: employees; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.employees (
    emp_no integer NOT NULL,
    birth_date date NOT NULL,
    first_name character varying(14) NOT NULL,
    last_name character varying(16) NOT NULL,
    gender character(1) NOT NULL,
    hire_date date NOT NULL,
    CONSTRAINT employees_gender_check CHECK ((gender = ANY (ARRAY['M'::bpchar, 'F'::bpchar])))
);


--
-- Name: salaries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.salaries (
    emp_no integer NOT NULL,
    salary integer NOT NULL,
    from_date date NOT NULL,
    to_date date NOT NULL
);


--
-- Name: titles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.titles (
    emp_no integer NOT NULL,
    title character varying(50) NOT NULL,
    from_date date NOT NULL,
    to_date date
);


--
-- Name: departments departments_dept_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departments
    ADD CONSTRAINT departments_dept_name_key UNIQUE (dept_name);


--
-- Name: departments departments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departments
    ADD CONSTRAINT departments_pkey PRIMARY KEY (dept_no);


--
-- Name: dept_emp dept_emp_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dept_emp
    ADD CONSTRAINT dept_emp_pkey PRIMARY KEY (emp_no, dept_no);


--
-- Name: dept_manager dept_manager_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dept_manager
    ADD CONSTRAINT dept_manager_pkey PRIMARY KEY (emp_no, dept_no);


--
-- Name: employees employees_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employees
    ADD CONSTRAINT employees_pkey PRIMARY KEY (emp_no);


--
-- Name: salaries salaries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.salaries
    ADD CONSTRAINT salaries_pkey PRIMARY KEY (emp_no, from_date);


--
-- Name: titles titles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.titles
    ADD CONSTRAINT titles_pkey PRIMARY KEY (emp_no, title, from_date);


--
-- Name: dept_emp dept_emp_dept_no_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dept_emp
    ADD CONSTRAINT dept_emp_dept_no_fkey FOREIGN KEY (dept_no) REFERENCES public.departments(dept_no) ON DELETE CASCADE;


--
-- Name: dept_emp dept_emp_emp_no_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dept_emp
    ADD CONSTRAINT dept_emp_emp_no_fkey FOREIGN KEY (emp_no) REFERENCES public.employees(emp_no) ON DELETE CASCADE;


--
-- Name: dept_manager dept_manager_dept_no_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dept_manager
    ADD CONSTRAINT dept_manager_dept_no_fkey FOREIGN KEY (dept_no) REFERENCES public.departments(dept_no) ON DELETE CASCADE;


--
-- Name: dept_manager dept_manager_emp_no_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dept_manager
    ADD CONSTRAINT dept_manager_emp_no_fkey FOREIGN KEY (emp_no) REFERENCES public.employees(emp_no) ON DELETE CASCADE;


--
-- Name: salaries salaries_emp_no_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.salaries
    ADD CONSTRAINT salaries_emp_no_fkey FOREIGN KEY (emp_no) REFERENCES public.employees(emp_no) ON DELETE CASCADE;


--
-- Name: titles titles_emp_no_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.titles
    ADD CONSTRAINT titles_emp_no_fkey FOREIGN KEY (emp_no) REFERENCES public.employees(emp_no) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict 1DuTFVauGGURGEsJdLE1b2gz0CZeYJPU4N3Z4P1bBcBCt5Lxf81Qthyf3Kokh0L

