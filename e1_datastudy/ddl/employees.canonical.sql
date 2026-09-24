CREATE TABLE departments (
    dept_no char(4) NOT NULL,
    dept_name varchar(40) NOT NULL,
    UNIQUE (dept_name),
    PRIMARY KEY (dept_no)
);

CREATE TABLE employees (
    emp_no integer NOT NULL,
    birth_date date NOT NULL,
    first_name varchar(14) NOT NULL,
    last_name varchar(16) NOT NULL,
    gender char(1) NOT NULL,
    hire_date date NOT NULL,
    PRIMARY KEY (emp_no),
    CHECK (gender IN ('M', 'F'))
);

CREATE TABLE dept_emp (
    emp_no integer NOT NULL,
    dept_no char(4) NOT NULL,
    from_date date NOT NULL,
    to_date date NOT NULL,
    PRIMARY KEY (emp_no, dept_no),
    FOREIGN KEY (dept_no) REFERENCES departments(dept_no),
    FOREIGN KEY (emp_no) REFERENCES employees(emp_no)
);

CREATE TABLE dept_manager (
    emp_no integer NOT NULL,
    dept_no char(4) NOT NULL,
    from_date date NOT NULL,
    to_date date NOT NULL,
    PRIMARY KEY (emp_no, dept_no),
    FOREIGN KEY (dept_no) REFERENCES departments(dept_no),
    FOREIGN KEY (emp_no) REFERENCES employees(emp_no)
);

CREATE TABLE salaries (
    emp_no integer NOT NULL,
    salary integer NOT NULL,
    from_date date NOT NULL,
    to_date date NOT NULL,
    PRIMARY KEY (emp_no, from_date),
    FOREIGN KEY (emp_no) REFERENCES employees(emp_no)
);

CREATE TABLE titles (
    emp_no integer NOT NULL,
    title varchar(50) NOT NULL,
    from_date date NOT NULL,
    to_date date,
    PRIMARY KEY (emp_no, title, from_date),
    FOREIGN KEY (emp_no) REFERENCES employees(emp_no)
);
