-- Oracle HR sample schema (db-sample-schemas, human_resources/hr_create.sql, schema version 21) ported to PostgreSQL.
-- Types mapped: NUMBER -> numeric/integer, NUMBER(p,s) -> numeric(p,s), VARCHAR2 -> varchar, CHAR(2) -> char(2), DATE -> date.
-- Constraints preserved: PK, FK, UNIQUE(email), CHECK(salary > 0), NOT NULL. Sequences, indexes, comments, views and the trigger omitted.
CREATE TABLE regions (region_id integer NOT NULL, region_name varchar(25), PRIMARY KEY (region_id));
CREATE TABLE countries (country_id char(2) NOT NULL, country_name varchar(60), region_id integer, PRIMARY KEY (country_id),
  FOREIGN KEY (region_id) REFERENCES regions(region_id));
CREATE TABLE locations (location_id numeric(4) NOT NULL, street_address varchar(40), postal_code varchar(12), city varchar(30) NOT NULL,
  state_province varchar(25), country_id char(2), PRIMARY KEY (location_id), FOREIGN KEY (country_id) REFERENCES countries(country_id));
CREATE TABLE departments (department_id numeric(4) NOT NULL, department_name varchar(30) NOT NULL, manager_id numeric(6), location_id numeric(4),
  PRIMARY KEY (department_id), FOREIGN KEY (location_id) REFERENCES locations(location_id));
CREATE TABLE jobs (job_id varchar(10) NOT NULL, job_title varchar(35) NOT NULL, min_salary numeric(6), max_salary numeric(6), PRIMARY KEY (job_id));
CREATE TABLE employees (employee_id numeric(6) NOT NULL, first_name varchar(20), last_name varchar(25) NOT NULL, email varchar(25) NOT NULL,
  phone_number varchar(20), hire_date date NOT NULL, job_id varchar(10) NOT NULL, salary numeric(8,2), commission_pct numeric(2,2),
  manager_id numeric(6), department_id numeric(4), PRIMARY KEY (employee_id), UNIQUE (email), CHECK (salary > 0),
  FOREIGN KEY (department_id) REFERENCES departments(department_id), FOREIGN KEY (job_id) REFERENCES jobs(job_id),
  FOREIGN KEY (manager_id) REFERENCES employees(employee_id) DEFERRABLE INITIALLY IMMEDIATE);
ALTER TABLE departments ADD FOREIGN KEY (manager_id) REFERENCES employees(employee_id) DEFERRABLE INITIALLY IMMEDIATE;
CREATE TABLE job_history (employee_id numeric(6) NOT NULL, start_date date NOT NULL, end_date date NOT NULL, job_id varchar(10) NOT NULL,
  department_id numeric(4), PRIMARY KEY (employee_id, start_date), CHECK (end_date > start_date),
  FOREIGN KEY (job_id) REFERENCES jobs(job_id), FOREIGN KEY (employee_id) REFERENCES employees(employee_id),
  FOREIGN KEY (department_id) REFERENCES departments(department_id));
