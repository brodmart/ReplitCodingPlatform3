--
-- PostgreSQL database dump
--

-- Dumped from database version 16.6
-- Dumped by pg_dump version 16.5

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

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: achievement; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.achievement (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    description character varying(500) NOT NULL,
    criteria character varying(200) NOT NULL,
    badge_icon character varying(200),
    points integer,
    category character varying(50) NOT NULL,
    created_at timestamp without time zone
);


--
-- Name: achievement_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.achievement_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: achievement_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.achievement_id_seq OWNED BY public.achievement.id;


--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: audit_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_log (
    id integer NOT NULL,
    table_name character varying(100) NOT NULL,
    record_id integer NOT NULL,
    action character varying(20) NOT NULL,
    changes json,
    user_id integer,
    created_at timestamp without time zone
);


--
-- Name: audit_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.audit_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: audit_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.audit_log_id_seq OWNED BY public.audit_log.id;


--
-- Name: code_submission; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.code_submission (
    id integer NOT NULL,
    student_id integer NOT NULL,
    language character varying(20) NOT NULL,
    code text NOT NULL,
    success boolean,
    output text,
    error text,
    submitted_at timestamp without time zone
);


--
-- Name: code_submission_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.code_submission_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: code_submission_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.code_submission_id_seq OWNED BY public.code_submission.id;


--
-- Name: coding_activity; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.coding_activity (
    id integer NOT NULL,
    title character varying(200) NOT NULL,
    description text NOT NULL,
    difficulty character varying(20) NOT NULL,
    curriculum character varying(20) NOT NULL,
    language character varying(20) NOT NULL,
    sequence integer NOT NULL,
    instructions text NOT NULL,
    starter_code text,
    solution_code text NOT NULL,
    test_cases json NOT NULL,
    hints json,
    common_errors json,
    incorrect_examples json,
    syntax_help text,
    points integer,
    max_attempts integer,
    created_at timestamp without time zone
);


--
-- Name: coding_activity_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.coding_activity_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: coding_activity_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.coding_activity_id_seq OWNED BY public.coding_activity.id;


--
-- Name: shared_code; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.shared_code (
    id integer NOT NULL,
    student_id integer NOT NULL,
    code text NOT NULL,
    language character varying(20) NOT NULL,
    title character varying(100),
    description text,
    created_at timestamp without time zone,
    is_public boolean,
    views integer
);


--
-- Name: shared_code_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.shared_code_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: shared_code_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.shared_code_id_seq OWNED BY public.shared_code.id;


--
-- Name: student; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.student (
    id integer NOT NULL,
    username character varying(64) NOT NULL,
    email character varying(120),
    password_hash character varying(256) NOT NULL,
    is_admin boolean,
    avatar_path character varying(256),
    failed_login_attempts integer,
    last_failed_login timestamp without time zone,
    account_locked_until timestamp without time zone,
    reset_password_token character varying(100),
    reset_password_token_expiration timestamp without time zone,
    score integer,
    created_at timestamp without time zone
);


--
-- Name: student_achievement; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.student_achievement (
    id integer NOT NULL,
    student_id integer NOT NULL,
    achievement_id integer NOT NULL,
    earned_at timestamp without time zone
);


--
-- Name: student_achievement_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.student_achievement_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: student_achievement_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.student_achievement_id_seq OWNED BY public.student_achievement.id;


--
-- Name: student_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.student_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: student_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.student_id_seq OWNED BY public.student.id;


--
-- Name: student_progress; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.student_progress (
    id integer NOT NULL,
    student_id integer NOT NULL,
    activity_id integer NOT NULL,
    started_at timestamp without time zone,
    completed_at timestamp without time zone,
    completed boolean,
    attempts integer,
    last_submission text
);


--
-- Name: student_progress_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.student_progress_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: student_progress_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.student_progress_id_seq OWNED BY public.student_progress.id;


--
-- Name: tutorial_progress; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tutorial_progress (
    id integer NOT NULL,
    student_id integer NOT NULL,
    step_id integer NOT NULL,
    completed boolean,
    started_at timestamp without time zone,
    completed_at timestamp without time zone,
    attempts integer
);


--
-- Name: tutorial_progress_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.tutorial_progress_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tutorial_progress_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.tutorial_progress_id_seq OWNED BY public.tutorial_progress.id;


--
-- Name: tutorial_step; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tutorial_step (
    id integer NOT NULL,
    activity_id integer NOT NULL,
    step_number integer NOT NULL,
    title character varying(200) NOT NULL,
    content text NOT NULL,
    code_snippet text,
    expected_output text,
    hint text
);


--
-- Name: tutorial_step_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.tutorial_step_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tutorial_step_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.tutorial_step_id_seq OWNED BY public.tutorial_step.id;


--
-- Name: achievement id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.achievement ALTER COLUMN id SET DEFAULT nextval('public.achievement_id_seq'::regclass);


--
-- Name: audit_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log ALTER COLUMN id SET DEFAULT nextval('public.audit_log_id_seq'::regclass);


--
-- Name: code_submission id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.code_submission ALTER COLUMN id SET DEFAULT nextval('public.code_submission_id_seq'::regclass);


--
-- Name: coding_activity id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.coding_activity ALTER COLUMN id SET DEFAULT nextval('public.coding_activity_id_seq'::regclass);


--
-- Name: shared_code id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.shared_code ALTER COLUMN id SET DEFAULT nextval('public.shared_code_id_seq'::regclass);


--
-- Name: student id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student ALTER COLUMN id SET DEFAULT nextval('public.student_id_seq'::regclass);


--
-- Name: student_achievement id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student_achievement ALTER COLUMN id SET DEFAULT nextval('public.student_achievement_id_seq'::regclass);


--
-- Name: student_progress id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student_progress ALTER COLUMN id SET DEFAULT nextval('public.student_progress_id_seq'::regclass);


--
-- Name: tutorial_progress id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tutorial_progress ALTER COLUMN id SET DEFAULT nextval('public.tutorial_progress_id_seq'::regclass);


--
-- Name: tutorial_step id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tutorial_step ALTER COLUMN id SET DEFAULT nextval('public.tutorial_step_id_seq'::regclass);


--
-- Data for Name: achievement; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.achievement (id, name, description, criteria, badge_icon, points, category, created_at) FROM stdin;
\.


--
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.alembic_version (version_num) FROM stdin;
002_add_password_reset_fields
\.


--
-- Data for Name: audit_log; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.audit_log (id, table_name, record_id, action, changes, user_id, created_at) FROM stdin;
\.


--
-- Data for Name: code_submission; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.code_submission (id, student_id, language, code, success, output, error, submitted_at) FROM stdin;
\.


--
-- Data for Name: coding_activity; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.coding_activity (id, title, description, difficulty, curriculum, language, sequence, instructions, starter_code, solution_code, test_cases, hints, common_errors, incorrect_examples, syntax_help, points, max_attempts, created_at) FROM stdin;
1	Introduction to C++	Learn the basics of C++ programming with a simple Hello World program	beginner	TEJ2O	cpp	1	Write a program that prints "Hello, World!" to the console.	#include <iostream>\nusing namespace std;\n\nint main() {\n    // Your code here\n    return 0;\n}	#include <iostream>\nusing namespace std;\n\nint main() {\n    cout << "Hello, World!" << endl;\n    return 0;\n}	{"inputs": [], "expected_outputs": ["Hello, World!"]}	\N	\N	\N	\N	10	\N	2025-01-16 03:58:18.219274
2	Variables and Input	Learn how to use variables and get input from users	beginner	TEJ2O	cpp	2	Create a program that asks for the user's name and age, then prints a greeting.	#include <iostream>\nusing namespace std;\n\nint main() {\n    string name;\n    int age;\n    // Your code here\n    return 0;\n}	#include <iostream>\nusing namespace std;\n\nint main() {\n    string name;\n    int age;\n    cout << "Enter your name: ";\n    cin >> name;\n    cout << "Enter your age: ";\n    cin >> age;\n    cout << "Hello, " << name << "! You are " << age << " years old." << endl;\n    return 0;\n}	{"inputs": ["John", "25"], "expected_outputs": ["Enter your name: ", "Enter your age: ", "Hello, John! You are 25 years old."]}	\N	\N	\N	\N	15	\N	2025-01-16 03:58:18.219274
3	Basic Calculations	Practice arithmetic operations in C++	beginner	TEJ2O	cpp	3	Write a program that calculates the area and perimeter of a rectangle.	#include <iostream>\nusing namespace std;\n\nint main() {\n    int length, width;\n    // Your code here\n    return 0;\n}	#include <iostream>\nusing namespace std;\n\nint main() {\n    int length, width;\n    cout << "Enter length: ";\n    cin >> length;\n    cout << "Enter width: ";\n    cin >> width;\n    cout << "Area: " << length * width << endl;\n    cout << "Perimeter: " << 2 * (length + width) << endl;\n    return 0;\n}	{"inputs": ["5", "3"], "expected_outputs": ["Enter length: ", "Enter width: ", "Area: 15", "Perimeter: 16"]}	\N	\N	\N	\N	20	\N	2025-01-16 03:58:18.219274
4	Getting Started with C#	Learn the basics of C# programming	beginner	ICS3U	csharp	1	Write your first C# program that displays a welcome message.	using System;\n\nclass Program {\n    static void Main() {\n        // Your code here\n    }\n}	using System;\n\nclass Program {\n    static void Main() {\n        Console.WriteLine("Welcome to C# Programming!");\n    }\n}	{"inputs": [], "expected_outputs": ["Welcome to C# Programming!"]}	\N	\N	\N	\N	10	\N	2025-01-16 03:58:18.219274
5	Working with Strings	Learn string manipulation in C#	beginner	ICS3U	csharp	2	Create a program that reverses a string entered by the user.	using System;\n\nclass Program {\n    static void Main() {\n        string input;\n        // Your code here\n    }\n}	using System;\n\nclass Program {\n    static void Main() {\n        Console.Write("Enter a word: ");\n        string input = Console.ReadLine();\n        char[] chars = input.ToCharArray();\n        Array.Reverse(chars);\n        Console.WriteLine($"Reversed: {new string(chars)}");\n    }\n}	{"inputs": ["hello"], "expected_outputs": ["Enter a word: ", "Reversed: olleh"]}	\N	\N	\N	\N	15	\N	2025-01-16 03:58:18.219274
6	Number Operations	Practice basic arithmetic and number manipulation in C#	beginner	ICS3U	csharp	3	Write a program that finds the sum and average of three numbers.	using System;\n\nclass Program {\n    static void Main() {\n        // Your code here\n    }\n}	using System;\n\nclass Program {\n    static void Main() {\n        Console.WriteLine("Enter three numbers:");\n        double num1 = Convert.ToDouble(Console.ReadLine());\n        double num2 = Convert.ToDouble(Console.ReadLine());\n        double num3 = Convert.ToDouble(Console.ReadLine());\n        double sum = num1 + num2 + num3;\n        double avg = sum / 3;\n        Console.WriteLine($"Sum: {sum}");\n        Console.WriteLine($"Average: {avg:F2}");\n    }\n}	{"inputs": ["10", "20", "30"], "expected_outputs": ["Enter three numbers:", "Sum: 60", "Average: 20.00"]}	\N	\N	\N	\N	20	\N	2025-01-16 03:58:18.219274
7	Conditional Statements	Learn how to use if-else statements in C++	beginner	TEJ2O	cpp	4	Write a program that determines if a number is positive, negative, or zero.	#include <iostream>\nusing namespace std;\n\nint main() {\n    int number;\n    cout << "Enter a number: ";\n    cin >> number;\n    // Your code here\n    return 0;\n}	#include <iostream>\nusing namespace std;\n\nint main() {\n    int number;\n    cout << "Enter a number: ";\n    cin >> number;\n    if (number > 0) {\n        cout << "Positive" << endl;\n    } else if (number < 0) {\n        cout << "Negative" << endl;\n    } else {\n        cout << "Zero" << endl;\n    }\n    return 0;\n}	{"inputs": ["5", "-3", "0"], "expected_outputs": ["Positive", "Negative", "Zero"]}	\N	\N	\N	\N	25	\N	2025-01-16 04:00:36.933784
8	Loops in C++	Master different types of loops in C++	intermediate	TEJ2O	cpp	5	Create a program that prints a multiplication table for a given number.	#include <iostream>\nusing namespace std;\n\nint main() {\n    int number;\n    // Your code here\n    return 0;\n}	#include <iostream>\nusing namespace std;\n\nint main() {\n    int number;\n    cout << "Enter a number: ";\n    cin >> number;\n    for(int i = 1; i <= 10; i++) {\n        cout << number << " x " << i << " = " << (number * i) << endl;\n    }\n    return 0;\n}	{"inputs": ["5"], "expected_outputs": ["5 x 1 = 5", "5 x 2 = 10", "5 x 3 = 15"]}	\N	\N	\N	\N	30	\N	2025-01-16 04:00:36.933784
9	Arrays and Vectors	Learn to work with arrays and vectors in C++	intermediate	TEJ2O	cpp	6	Create a program that finds the largest element in an array.	#include <iostream>\nusing namespace std;\n\nint main() {\n    int arr[5];\n    // Your code here\n    return 0;\n}	#include <iostream>\nusing namespace std;\n\nint main() {\n    int arr[5];\n    cout << "Enter 5 numbers:\\n";\n    for(int i = 0; i < 5; i++) {\n        cin >> arr[i];\n    }\n    int max = arr[0];\n    for(int i = 1; i < 5; i++) {\n        if(arr[i] > max) max = arr[i];\n    }\n    cout << "Largest number: " << max << endl;\n    return 0;\n}	{"inputs": ["1", "3", "5", "2", "4"], "expected_outputs": ["Largest number: 5"]}	\N	\N	\N	\N	35	\N	2025-01-16 04:00:36.933784
10	Functions	Understanding functions and modular programming	intermediate	TEJ2O	cpp	7	Write functions to calculate the area of different shapes.	#include <iostream>\nusing namespace std;\n\n// Your functions here\n\nint main() {\n    return 0;\n}	#include <iostream>\nusing namespace std;\n\nfloat circleArea(float r) {\n    return 3.14159 * r * r;\n}\n\nfloat rectangleArea(float l, float w) {\n    return l * w;\n}\n\nint main() {\n    cout << "Circle area (r=5): " << circleArea(5) << endl;\n    cout << "Rectangle area (l=4, w=6): " << rectangleArea(4, 6) << endl;\n    return 0;\n}	{"inputs": [], "expected_outputs": ["Circle area (r=5): 78.5398", "Rectangle area (l=4, w=6): 24"]}	\N	\N	\N	\N	40	\N	2025-01-16 04:00:36.933784
11	String Manipulation	Learn to work with strings in C++	intermediate	TEJ2O	cpp	8	Create a program that counts vowels in a string.	#include <iostream>\n#include <string>\nusing namespace std;\n\nint main() {\n    string text;\n    // Your code here\n    return 0;\n}	#include <iostream>\n#include <string>\nusing namespace std;\n\nint main() {\n    string text;\n    cout << "Enter text: ";\n    getline(cin, text);\n    int vowels = 0;\n    for(char c : text) {\n        if(tolower(c) == 'a' || tolower(c) == 'e' || \n           tolower(c) == 'i' || tolower(c) == 'o' || \n           tolower(c) == 'u') {\n            vowels++;\n        }\n    }\n    cout << "Vowel count: " << vowels << endl;\n    return 0;\n}	{"inputs": ["Hello World"], "expected_outputs": ["Vowel count: 3"]}	\N	\N	\N	\N	45	\N	2025-01-16 04:00:36.933784
12	File Operations	Learn to read and write files in C++	advanced	TEJ2O	cpp	9	Create a program that reads numbers from a file and calculates their average.	#include <iostream>\n#include <fstream>\nusing namespace std;\n\nint main() {\n    // Your code here\n    return 0;\n}	#include <iostream>\n#include <fstream>\nusing namespace std;\n\nint main() {\n    ofstream outFile("numbers.txt");\n    outFile << "10\\n20\\n30\\n40\\n50";\n    outFile.close();\n    \n    ifstream inFile("numbers.txt");\n    int sum = 0, count = 0, number;\n    while(inFile >> number) {\n        sum += number;\n        count++;\n    }\n    cout << "Average: " << (float)sum/count << endl;\n    return 0;\n}	{"inputs": [], "expected_outputs": ["Average: 30"]}	\N	\N	\N	\N	50	\N	2025-01-16 04:00:36.933784
13	Structures and Classes	Introduction to Object-Oriented Programming in C++	advanced	TEJ2O	cpp	10	Create a simple Student class to store and display student information.	#include <iostream>\n#include <string>\nusing namespace std;\n\n// Your class definition here\n\nint main() {\n    return 0;\n}	#include <iostream>\n#include <string>\nusing namespace std;\n\nclass Student {\n    string name;\n    int age;\n    float gpa;\npublic:\n    Student(string n, int a, float g) {\n        name = n; age = a; gpa = g;\n    }\n    void display() {\n        cout << "Name: " << name << "\\nAge: " << age\n             << "\\nGPA: " << gpa << endl;\n    }\n};\n\nint main() {\n    Student s1("John Doe", 15, 3.8);\n    s1.display();\n    return 0;\n}	{"inputs": [], "expected_outputs": ["Name: John Doe", "Age: 15", "GPA: 3.8"]}	\N	\N	\N	\N	55	\N	2025-01-16 04:00:36.933784
14	Control Flow	Master control flow statements in C#	beginner	ICS3U	csharp	4	Create a program that implements a simple calculator with basic operations.	using System;\n\nclass Program {\n    static void Main() {\n        // Your code here\n    }\n}	using System;\n\nclass Program {\n    static void Main() {\n        Console.Write("Enter first number: ");\n        double num1 = Convert.ToDouble(Console.ReadLine());\n        Console.Write("Enter operation (+,-,*,/): ");\n        char op = Convert.ToChar(Console.ReadLine());\n        Console.Write("Enter second number: ");\n        double num2 = Convert.ToDouble(Console.ReadLine());\n        \n        switch(op) {\n            case '+':\n                Console.WriteLine($"Result: {num1 + num2}");\n                break;\n            case '-':\n                Console.WriteLine($"Result: {num1 - num2}");\n                break;\n            case '*':\n                Console.WriteLine($"Result: {num1 * num2}");\n                break;\n            case '/':\n                if(num2 != 0)\n                    Console.WriteLine($"Result: {num1 / num2}");\n                else\n                    Console.WriteLine("Cannot divide by zero");\n                break;\n            default:\n                Console.WriteLine("Invalid operation");\n                break;\n        }\n    }\n}	{"inputs": ["5", "+", "3"], "expected_outputs": ["Result: 8"]}	\N	\N	\N	\N	25	\N	2025-01-16 04:00:36.933784
15	Arrays and Lists	Working with collections in C#	intermediate	ICS3U	csharp	5	Create a program that manages a simple todo list using List<string>.	using System;\nusing System.Collections.Generic;\n\nclass Program {\n    static void Main() {\n        // Your code here\n    }\n}	using System;\nusing System.Collections.Generic;\n\nclass Program {\n    static void Main() {\n        List<string> todos = new List<string>();\n        while(true) {\n            Console.WriteLine("\\n1. Add todo\\n2. View todos\\n3. Exit");\n            string choice = Console.ReadLine();\n            if(choice == "1") {\n                Console.Write("Enter todo: ");\n                todos.Add(Console.ReadLine());\n            } else if(choice == "2") {\n                for(int i = 0; i < todos.Count; i++) {\n                    Console.WriteLine($"{i+1}. {todos[i]}");\n                }\n            } else if(choice == "3") {\n                break;\n            }\n        }\n    }\n}	{"inputs": ["1", "Buy groceries", "2", "3"], "expected_outputs": ["1. Buy groceries"]}	\N	\N	\N	\N	30	\N	2025-01-16 04:00:36.933784
16	Methods and Parameters	Understanding methods and parameter passing in C#	intermediate	ICS3U	csharp	6	Create methods to perform various string operations.	using System;\n\nclass Program {\n    // Your methods here\n    static void Main() {\n    }\n}	using System;\n\nclass Program {\n    static string Reverse(string text) {\n        char[] chars = text.ToCharArray();\n        Array.Reverse(chars);\n        return new string(chars);\n    }\n    \n    static int CountVowels(string text) {\n        int count = 0;\n        foreach(char c in text.ToLower()) {\n            if("aeiou".Contains(c)) count++;\n        }\n        return count;\n    }\n    \n    static void Main() {\n        Console.Write("Enter text: ");\n        string text = Console.ReadLine();\n        Console.WriteLine($"Reversed: {Reverse(text)}");\n        Console.WriteLine($"Vowel count: {CountVowels(text)}");\n    }\n}	{"inputs": ["Hello"], "expected_outputs": ["Reversed: olleH", "Vowel count: 2"]}	\N	\N	\N	\N	35	\N	2025-01-16 04:00:36.933784
17	Object-Oriented Programming	Learn classes and objects in C#	intermediate	ICS3U	csharp	7	Create a BankAccount class with deposit and withdraw functionality.	using System;\n\nclass Program {\n    // Your class definition here\n    static void Main() {\n    }\n}	using System;\n\nclass BankAccount {\n    private decimal balance;\n    public string AccountHolder { get; }\n    \n    public BankAccount(string holder, decimal initial) {\n        AccountHolder = holder;\n        balance = initial;\n    }\n    \n    public void Deposit(decimal amount) {\n        if(amount > 0) {\n            balance += amount;\n            Console.WriteLine($"Deposited: {amount:C}");\n        }\n    }\n    \n    public bool Withdraw(decimal amount) {\n        if(amount <= balance) {\n            balance -= amount;\n            Console.WriteLine($"Withdrawn: {amount:C}");\n            return true;\n        }\n        Console.WriteLine("Insufficient funds");\n        return false;\n    }\n    \n    public void CheckBalance() {\n        Console.WriteLine($"Balance: {balance:C}");\n    }\n}\n\nclass Program {\n    static void Main() {\n        BankAccount account = new BankAccount("John", 1000);\n        account.CheckBalance();\n        account.Deposit(500);\n        account.Withdraw(200);\n        account.CheckBalance();\n    }\n}	{"inputs": [], "expected_outputs": ["Balance: $1,000.00", "Deposited: $500.00", "Withdrawn: $200.00", "Balance: $1,300.00"]}	\N	\N	\N	\N	40	\N	2025-01-16 04:00:36.933784
18	File Handling	Learn to work with files in C#	advanced	ICS3U	csharp	8	Create a program that maintains a simple address book using file I/O.	using System;\nusing System.IO;\n\nclass Program {\n    static void Main() {\n        // Your code here\n    }\n}	using System;\nusing System.IO;\n\nclass Program {\n    static void Main() {\n        string file = "addresses.txt";\n        while(true) {\n            Console.WriteLine("\\n1. Add Contact\\n2. View Contacts\\n3. Exit");\n            string choice = Console.ReadLine();\n            if(choice == "1") {\n                Console.Write("Name: ");\n                string name = Console.ReadLine();\n                Console.Write("Email: ");\n                string email = Console.ReadLine();\n                File.AppendAllText(file, $"{name},{email}\\n");\n            } else if(choice == "2") {\n                if(File.Exists(file)) {\n                    string[] lines = File.ReadAllLines(file);\n                    foreach(string line in lines) {\n                        string[] parts = line.Split(',');\n                        Console.WriteLine($"{parts[0]} - {parts[1]}");\n                    }\n                }\n            } else if(choice == "3") break;\n        }\n    }\n}	{"inputs": ["1", "John", "john@email.com", "2", "3"], "expected_outputs": ["John - john@email.com"]}	\N	\N	\N	\N	45	\N	2025-01-16 04:00:36.933784
19	Exception Handling	Learn to handle errors and exceptions in C#	advanced	ICS3U	csharp	9	Create a program that demonstrates various exception handling scenarios.	using System;\n\nclass Program {\n    static void Main() {\n        // Your code here\n    }\n}	using System;\n\nclass Program {\n    static double Divide(double a, double b) {\n        if(b == 0) throw new DivideByZeroException();\n        return a / b;\n    }\n    \n    static void Main() {\n        try {\n            Console.Write("Enter first number: ");\n            double num1 = Convert.ToDouble(Console.ReadLine());\n            Console.Write("Enter second number: ");\n            double num2 = Convert.ToDouble(Console.ReadLine());\n            \n            double result = Divide(num1, num2);\n            Console.WriteLine($"Result: {result}");\n        }\n        catch(FormatException) {\n            Console.WriteLine("Please enter valid numbers");\n        }\n        catch(DivideByZeroException) {\n            Console.WriteLine("Cannot divide by zero");\n        }\n        catch(Exception ex) {\n            Console.WriteLine($"An error occurred: {ex.Message}");\n        }\n    }\n}	{"inputs": ["10", "0"], "expected_outputs": ["Cannot divide by zero"]}	\N	\N	\N	\N	50	\N	2025-01-16 04:00:36.933784
20	LINQ and Collections	Master LINQ queries and advanced collection operations	advanced	ICS3U	csharp	10	Create a program that demonstrates LINQ operations on a collection of objects.	using System;\nusing System.Linq;\nusing System.Collections.Generic;\n\nclass Program {\n    static void Main() {\n        // Your code here\n    }\n}	using System;\nusing System.Linq;\nusing System.Collections.Generic;\n\nclass Student {\n    public string Name { get; set; }\n    public int Age { get; set; }\n    public double Grade { get; set; }\n}\n\nclass Program {\n    static void Main() {\n        List<Student> students = new List<Student> {\n            new Student { Name = "John", Age = 15, Grade = 85.5 },\n            new Student { Name = "Jane", Age = 16, Grade = 92.0 },\n            new Student { Name = "Bob", Age = 15, Grade = 78.5 },\n            new Student { Name = "Alice", Age = 16, Grade = 95.0 }\n        };\n        \n        Console.WriteLine("Students with grade above 90:");\n        var highGrades = students.Where(s => s.Grade > 90)\n                                .OrderBy(s => s.Name);\n        foreach(var student in highGrades) {\n            Console.WriteLine($"{student.Name}: {student.Grade}");\n        }\n        \n        double avgGrade = students.Average(s => s.Grade);\n        Console.WriteLine($"\\nAverage grade: {avgGrade:F2}");\n    }\n}	{"inputs": [], "expected_outputs": ["Students with grade above 90:", "Alice: 95", "Jane: 92", "Average grade: 87.75"]}	\N	\N	\N	\N	55	\N	2025-01-16 04:00:36.933784
\.


--
-- Data for Name: shared_code; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.shared_code (id, student_id, code, language, title, description, created_at, is_public, views) FROM stdin;
\.


--
-- Data for Name: student; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.student (id, username, email, password_hash, is_admin, avatar_path, failed_login_attempts, last_failed_login, account_locked_until, reset_password_token, reset_password_token_expiration, score, created_at) FROM stdin;
1	moi	\N	scrypt:32768:8:1$jUXl9qu8izS6XxuM$09bb99362175974686e3c264100cb6b3cc2aa80a757083017a79776ee4f703120e77cc49164cfa32fdf898ce029c0e4b629116af4af586bcb524d1cc650bdddf	f	\N	0	\N	\N	\N	\N	0	2025-01-16 03:47:05.360796
7	admin	\N	scrypt:32768:8:1$TLnoXNWQGRlw9ZnK$fb0ce70b8c38b04960f7494b9581c489ac0e10b3508e813395076b1ef331b94a63e254fa7788eb8cb7fcdd341f926026df4544e65d499d307dee17d195deb9b9	t	\N	0	\N	\N	\N	\N	\N	2025-01-16 03:54:40.455095
\.


--
-- Data for Name: student_achievement; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.student_achievement (id, student_id, achievement_id, earned_at) FROM stdin;
\.


--
-- Data for Name: student_progress; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.student_progress (id, student_id, activity_id, started_at, completed_at, completed, attempts, last_submission) FROM stdin;
\.


--
-- Data for Name: tutorial_progress; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.tutorial_progress (id, student_id, step_id, completed, started_at, completed_at, attempts) FROM stdin;
\.


--
-- Data for Name: tutorial_step; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.tutorial_step (id, activity_id, step_number, title, content, code_snippet, expected_output, hint) FROM stdin;
\.


--
-- Name: achievement_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.achievement_id_seq', 1, false);


--
-- Name: audit_log_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.audit_log_id_seq', 1, false);


--
-- Name: code_submission_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.code_submission_id_seq', 1, false);


--
-- Name: coding_activity_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.coding_activity_id_seq', 20, true);


--
-- Name: shared_code_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.shared_code_id_seq', 1, false);


--
-- Name: student_achievement_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.student_achievement_id_seq', 1, false);


--
-- Name: student_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.student_id_seq', 7, true);


--
-- Name: student_progress_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.student_progress_id_seq', 1, false);


--
-- Name: tutorial_progress_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.tutorial_progress_id_seq', 1, false);


--
-- Name: tutorial_step_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.tutorial_step_id_seq', 857, true);


--
-- Name: achievement achievement_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.achievement
    ADD CONSTRAINT achievement_pkey PRIMARY KEY (id);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: audit_log audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_pkey PRIMARY KEY (id);


--
-- Name: code_submission code_submission_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.code_submission
    ADD CONSTRAINT code_submission_pkey PRIMARY KEY (id);


--
-- Name: coding_activity coding_activity_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.coding_activity
    ADD CONSTRAINT coding_activity_pkey PRIMARY KEY (id);


--
-- Name: shared_code shared_code_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.shared_code
    ADD CONSTRAINT shared_code_pkey PRIMARY KEY (id);


--
-- Name: student_achievement student_achievement_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student_achievement
    ADD CONSTRAINT student_achievement_pkey PRIMARY KEY (id);


--
-- Name: student student_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student
    ADD CONSTRAINT student_email_key UNIQUE (email);


--
-- Name: student student_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student
    ADD CONSTRAINT student_pkey PRIMARY KEY (id);


--
-- Name: student_progress student_progress_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student_progress
    ADD CONSTRAINT student_progress_pkey PRIMARY KEY (id);


--
-- Name: student student_reset_password_token_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student
    ADD CONSTRAINT student_reset_password_token_key UNIQUE (reset_password_token);


--
-- Name: tutorial_progress tutorial_progress_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tutorial_progress
    ADD CONSTRAINT tutorial_progress_pkey PRIMARY KEY (id);


--
-- Name: tutorial_step tutorial_step_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tutorial_step
    ADD CONSTRAINT tutorial_step_pkey PRIMARY KEY (id);


--
-- Name: idx_student_username; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_student_username ON public.student USING btree (username);


--
-- Name: ix_student_username; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_student_username ON public.student USING btree (username);


--
-- Name: audit_log audit_log_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.student(id);


--
-- Name: code_submission code_submission_student_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.code_submission
    ADD CONSTRAINT code_submission_student_id_fkey FOREIGN KEY (student_id) REFERENCES public.student(id);


--
-- Name: shared_code shared_code_student_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.shared_code
    ADD CONSTRAINT shared_code_student_id_fkey FOREIGN KEY (student_id) REFERENCES public.student(id);


--
-- Name: student_achievement student_achievement_achievement_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student_achievement
    ADD CONSTRAINT student_achievement_achievement_id_fkey FOREIGN KEY (achievement_id) REFERENCES public.achievement(id);


--
-- Name: student_achievement student_achievement_student_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student_achievement
    ADD CONSTRAINT student_achievement_student_id_fkey FOREIGN KEY (student_id) REFERENCES public.student(id);


--
-- Name: student_progress student_progress_activity_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student_progress
    ADD CONSTRAINT student_progress_activity_id_fkey FOREIGN KEY (activity_id) REFERENCES public.coding_activity(id);


--
-- Name: student_progress student_progress_student_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student_progress
    ADD CONSTRAINT student_progress_student_id_fkey FOREIGN KEY (student_id) REFERENCES public.student(id);


--
-- Name: tutorial_progress tutorial_progress_step_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tutorial_progress
    ADD CONSTRAINT tutorial_progress_step_id_fkey FOREIGN KEY (step_id) REFERENCES public.tutorial_step(id);


--
-- PostgreSQL database dump complete
--

