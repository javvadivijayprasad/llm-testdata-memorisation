CREATE TABLE divisions (
    div_no char(4) NOT NULL,
    div_name varchar(40) NOT NULL,
    UNIQUE (div_name),
    PRIMARY KEY (div_no)
);

CREATE TABLE workers (
    wkr_no integer NOT NULL,
    born_date date NOT NULL,
    given_name varchar(14) NOT NULL,
    family_name varchar(16) NOT NULL,
    sex_code char(1) NOT NULL,
    joined_date date NOT NULL,
    PRIMARY KEY (wkr_no),
    CHECK (sex_code IN ('M', 'F'))
);

CREATE TABLE div_wkr (
    wkr_no integer NOT NULL,
    div_no char(4) NOT NULL,
    start_date date NOT NULL,
    end_date date NOT NULL,
    PRIMARY KEY (wkr_no, div_no),
    FOREIGN KEY (div_no) REFERENCES divisions(div_no),
    FOREIGN KEY (wkr_no) REFERENCES workers(wkr_no)
);

CREATE TABLE div_lead (
    wkr_no integer NOT NULL,
    div_no char(4) NOT NULL,
    start_date date NOT NULL,
    end_date date NOT NULL,
    PRIMARY KEY (wkr_no, div_no),
    FOREIGN KEY (div_no) REFERENCES divisions(div_no),
    FOREIGN KEY (wkr_no) REFERENCES workers(wkr_no)
);

CREATE TABLE pay_history (
    wkr_no integer NOT NULL,
    pay_amount integer NOT NULL,
    start_date date NOT NULL,
    end_date date NOT NULL,
    PRIMARY KEY (wkr_no, start_date),
    FOREIGN KEY (wkr_no) REFERENCES workers(wkr_no)
);

CREATE TABLE designations (
    wkr_no integer NOT NULL,
    designation varchar(50) NOT NULL,
    start_date date NOT NULL,
    end_date date,
    PRIMARY KEY (wkr_no, designation, start_date),
    FOREIGN KEY (wkr_no) REFERENCES workers(wkr_no)
);
