from flask import Flask
from extensions import db, login_manager
from models import User
import os

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-this-in-production-gcse-quiz-2024')
    db_url = os.environ.get('DATABASE_URL', 'sqlite:///gcse_quiz.db')
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
    app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from routes.auth import auth_bp
    from routes.student import student_bp
    from routes.teacher import teacher_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp, url_prefix='/student')
    app.register_blueprint(teacher_bp, url_prefix='/teacher')

    with app.app_context():
        db.create_all()
        seed_data()

    return app

def seed_data():
    from models import User, Week, Question, Option
    from werkzeug.security import generate_password_hash

    # Create teacher account
    if not User.query.filter_by(email='yogeshrowjee@gmail.com').first():
        teacher = User(
            username='YogeshRowjee',
            email='yogeshrowjee@gmail.com',
            password_hash=generate_password_hash('Yovin123'),
            role='teacher',
            full_name='Yogesh Rowjee',
        )
        db.session.add(teacher)

    # Create intro week
    if not Week.query.filter_by(slug='intro').first():
        intro = Week(
            slug='intro',
            title='Introductory Quiz',
            description='Core fundamentals across both papers — a warm-up before weekly topics.',
            week_number=0,
            is_enabled=True,
            is_intro=True
        )
        db.session.add(intro)
        db.session.flush()

        intro_questions = [
            # Paper 1
            ("How many bits are in a nibble?", ["4","8","16","2"], 0, "Data representation", "A nibble is 4 bits. A byte is 8 bits.", "Paper 1 — Principles"),
            ("What is the denary value of the binary number 1011?", ["9","10","11","13"], 2, "Data representation", "1×8 + 0×4 + 1×2 + 1×1 = 11.", "Paper 1 — Principles"),
            ("Which number base does hexadecimal use?", ["2","8","10","16"], 3, "Data representation", "Hexadecimal uses base 16, with digits 0–9 and A–F.", "Paper 1 — Principles"),
            ("What is the hexadecimal representation of denary 255?", ["EE","FE","FF","F0"], 2, "Data representation", "255 = 15×16 + 15 = FF in hexadecimal.", "Paper 1 — Principles"),
            ("Which encoding standard can represent over 1 million characters including emoji?", ["ASCII","Unicode (UTF-8)","EBCDIC","ISO-8859-1"], 1, "Data representation", "Unicode (UTF-8) supports over 1 million code points.", "Paper 1 — Principles"),
            ("A pixel is stored using 24-bit colour. How many colours can it represent?", ["256","65 536","16 777 216","4 294 967 296"], 2, "Data representation", "2²⁴ = 16,777,216 possible colour combinations.", "Paper 1 — Principles"),
            ("What does the term 'sample rate' refer to in audio?", ["The bit depth of each sample","Number of samples taken per second","Size of the audio file","The frequency range"], 1, "Data representation", "Sample rate (Hz) is how many audio samples are captured each second.", "Paper 1 — Principles"),
            ("Which component fetches and executes program instructions?", ["RAM","GPU","CPU","HDD"], 2, "Computer systems", "The CPU uses the fetch-decode-execute cycle to process instructions.", "Paper 1 — Principles"),
            ("What does ALU stand for?", ["Arithmetic Logic Unit","Allocated Load Unit","Advanced Logic Unit","Arithmetic Load Utility"], 0, "Computer systems", "ALU = Arithmetic Logic Unit — performs calculations and logical operations.", "Paper 1 — Principles"),
            ("Which type of memory is volatile?", ["ROM","Flash storage","RAM","SSD"], 2, "Computer systems", "RAM is volatile — its contents are lost when power is removed.", "Paper 1 — Principles"),
            ("What does 'clock speed' measure in a CPU?", ["Number of cores","Instructions per cycle","Cycles per second (Hz)","Cache size"], 2, "Computer systems", "Clock speed (Hz/GHz) measures cycles the CPU performs per second.", "Paper 1 — Principles"),
            ("What is the purpose of cache memory?", ["Permanent OS storage","Storing frequently accessed data for fast retrieval","Increasing screen resolution","Sending data over a network"], 1, "Computer systems", "Cache is fast memory close to the CPU that stores frequently used data.", "Paper 1 — Principles"),
            ("What is an operating system responsible for?", ["Compiling source code","Managing hardware resources and providing a user interface","Encrypting files","Sorting data in RAM"], 1, "Computer systems", "The OS manages hardware resources, file systems, processes, and provides a UI.", "Paper 1 — Principles"),
            ("What does 'LAN' stand for?", ["Large Area Network","Local Area Network","Layered Access Node","Linked Application Network"], 1, "Networks", "LAN = Local Area Network — covers a small geographic area.", "Paper 1 — Principles"),
            ("Which device uses MAC addresses to forward data only to the intended device on a LAN?", ["Hub","Router","Switch","Repeater"], 2, "Networks", "A switch uses MAC address tables to forward frames to the correct port.", "Paper 1 — Principles"),
            ("What is the role of a router?", ["Convert analogue signals to digital","Connect networks and direct data packets between them","Store website files","Manage print queues"], 1, "Networks", "A router connects different networks and routes IP packets between them.", "Paper 1 — Principles"),
            ("Which protocol is used to send emails?", ["HTTP","FTP","SMTP","IMAP"], 2, "Networks", "SMTP (Simple Mail Transfer Protocol) sends emails between servers.", "Paper 1 — Principles"),
            ("What does 'IP' stand for in networking?", ["Internal Protocol","Internet Protocol","Integrated Packet","Interface Port"], 1, "Networks", "IP = Internet Protocol — handles addressing and routing of packets.", "Paper 1 — Principles"),
            ("What type of attack floods a server with requests to make it unavailable?", ["Phishing","SQL injection","Denial of Service (DoS)","Brute force"], 2, "Cyber security", "A DoS attack overwhelms a server with traffic, preventing legitimate access.", "Paper 1 — Principles"),
            ("What is phishing?", ["Installing malware via USB","Intercepting Wi-Fi traffic","Tricking users into revealing credentials via fake communications","Guessing passwords systematically"], 2, "Cyber security", "Phishing uses deceptive emails/websites to steal sensitive information.", "Paper 1 — Principles"),
            ("What does 'malware' refer to?", ["A type of network protocol","Any software designed to harm or exploit systems","A secure encryption algorithm","A type of firewall"], 1, "Cyber security", "Malware is any malicious software: viruses, ransomware, spyware, trojans.", "Paper 1 — Principles"),
            ("Which best describes a firewall?", ["A program that compresses files","Hardware or software that monitors and controls network traffic","A virus detection algorithm","A method of encrypting data"], 1, "Cyber security", "A firewall filters network traffic based on defined security rules.", "Paper 1 — Principles"),
            ("Which UK law protects personal data stored by organisations?", ["Computer Misuse Act 1990","Freedom of Information Act 2000","Data Protection Act 2018","Copyright Designs and Patents Act 1988"], 2, "Legal & ethical", "The Data Protection Act 2018 (incorporating GDPR) regulates use of personal data.", "Paper 1 — Principles"),
            ("The Computer Misuse Act 1990 makes which of the following illegal?", ["Sharing open-source software","Accessing a computer system without authorisation","Using public Wi-Fi","Installing free software"], 1, "Legal & ethical", "The Computer Misuse Act criminalises unauthorised access to computer systems.", "Paper 1 — Principles"),
            ("Which disposal method ensures data on an old hard drive cannot be recovered?", ["Emptying the recycle bin","Formatting the drive","Physical destruction or degaussing","Moving files to another drive"], 2, "Legal & ethical", "Physical destruction or degaussing permanently destroys the magnetic media.", "Paper 1 — Principles"),
            # Paper 2
            ("What is the worst-case time complexity of a binary search?", ["O(n)","O(n²)","O(log n)","O(1)"], 2, "Algorithms", "Binary search halves the search space each step — O(log n).", "Paper 2 — Application"),
            ("Which sorting algorithm repeatedly swaps adjacent elements if they are in the wrong order?", ["Merge sort","Insertion sort","Bubble sort","Quick sort"], 2, "Algorithms", "Bubble sort compares and swaps adjacent elements on each pass.", "Paper 2 — Application"),
            ("What is an algorithm?", ["A type of programming language","A set of step-by-step instructions to solve a problem","A diagram of a network","A type of data structure"], 1, "Algorithms", "An algorithm is a finite, unambiguous sequence of instructions.", "Paper 2 — Application"),
            ("In a linear search of 100 items, what is the maximum number of comparisons?", ["1","10","50","100"], 3, "Algorithms", "Worst case: linear search checks every element — 100 comparisons.", "Paper 2 — Application"),
            ("Which data structure operates on a Last-In, First-Out (LIFO) basis?", ["Queue","Stack","Array","Linked list"], 1, "Algorithms", "A stack uses LIFO — the last item pushed is the first one popped.", "Paper 2 — Application"),
            ("What does a flowchart diamond symbol represent?", ["A process step","A decision/condition","Start or end","Input or output"], 1, "Algorithms", "Diamond shapes represent decision points with two or more branches.", "Paper 2 — Application"),
            ("What is a 'trace table' used for?", ["Drawing network diagrams","Manually tracking variable values through an algorithm","Measuring CPU speed","Listing data types"], 1, "Algorithms", "A trace table records variable values at each step to test an algorithm.", "Paper 2 — Application"),
            ("What is the output of: x = 10; x = x + 5; print(x)?", ["10","5","15","x + 5"], 2, "Programming", "x starts at 10, x + 5 = 15 is assigned back, so print(x) outputs 15.", "Paper 2 — Application"),
            ("Which keyword defines a function in Python?", ["function","define","proc","def"], 3, "Programming", "In Python, functions are defined using the 'def' keyword.", "Paper 2 — Application"),
            ("What is a 'parameter' in a subroutine?", ["The result returned","A local constant","A variable that receives a value passed into the subroutine","The name of the subroutine"], 2, "Programming", "Parameters receive argument values when a subroutine is called.", "Paper 2 — Application"),
            ("What does the modulo operator (MOD or %) return?", ["The quotient","The square root","The remainder after integer division","The absolute value"], 2, "Programming", "Modulo returns the remainder after integer division, e.g. 10 MOD 3 = 1.", "Paper 2 — Application"),
            ("Which is an example of an iteration construct?", ["IF…THEN…ELSE","CASE…OF","FOR…NEXT","FUNCTION…ENDFUNCTION"], 2, "Programming", "FOR…NEXT (and WHILE, REPEAT) are loop/iteration constructs.", "Paper 2 — Application"),
            ("In a 1D array of 10 elements, what is the index of the last element (zero-based)?", ["10","9","1","0"], 1, "Data structures", "Zero-based indexing: elements are 0–9, so the last is index 9.", "Paper 2 — Application"),
            ("Which data structure uses First-In, First-Out (FIFO)?", ["Stack","Binary tree","Queue","Hash table"], 2, "Data structures", "A queue uses FIFO — first item added is first removed.", "Paper 2 — Application"),
            ("What is the difference between an integer and a real/float?", ["Integers can be negative; floats cannot","Integers are whole numbers; floats include decimal points","Floats use less memory","Integers store text"], 1, "Programming concepts", "Integers are whole numbers; real/float types include fractional parts.", "Paper 2 — Application"),
            ("What is meant by 'casting' in programming?", ["Throwing an exception","Converting a value from one data type to another","Declaring a variable","Calling a subroutine"], 1, "Programming concepts", "Casting converts a value from one data type to another, e.g. int('5').", "Paper 2 — Application"),
            ("What is a global variable?", ["Accessible only inside one function","Accessible throughout the entire program","A constant that cannot change","A variable stored on the hard drive"], 1, "Programming concepts", "A global variable is declared outside functions and accessible anywhere.", "Paper 2 — Application"),
            ("What is the output of: NOT (TRUE AND FALSE)?", ["TRUE","FALSE","ERROR","0"], 0, "Logic", "TRUE AND FALSE = FALSE; NOT FALSE = TRUE.", "Paper 2 — Application"),
            ("Which logic gate produces HIGH output only when both inputs are HIGH?", ["OR","NOT","AND","XOR"], 2, "Logic", "An AND gate outputs 1 only when both inputs are 1.", "Paper 2 — Application"),
            ("What does the XOR gate output when both inputs are the same?", ["1","0","Depends on inputs","Always 1"], 1, "Logic", "XOR outputs 0 when both inputs are the same (0,0→0; 1,1→0).", "Paper 2 — Application"),
            ("What is input validation?", ["Checking code compiles","Ensuring user input meets expected criteria before processing","Encrypting user data","Commenting code"], 1, "Defensive design", "Input validation checks data is acceptable (type, range, format) before use.", "Paper 2 — Application"),
            ("What is the purpose of 'authentication' in a program?", ["Speed up the program","Verify that a user is who they claim to be","Sort data alphabetically","Compress file sizes"], 1, "Defensive design", "Authentication confirms a user's identity via username/password or biometrics.", "Paper 2 — Application"),
            ("What is 'normal data' in software testing?", ["Data outside the expected range","Data at the boundary","Typical data the program should accept and process correctly","Invalid data that should be rejected"], 2, "Testing", "Normal (valid) test data is typical input the program should handle correctly.", "Paper 2 — Application"),
            ("What type of test data checks values at the edge of acceptable ranges?", ["Normal data","Invalid data","Boundary data","Erroneous data"], 2, "Testing", "Boundary test data checks values at or just inside/outside acceptable limits.", "Paper 2 — Application"),
            ("What is the difference between a compiler and an interpreter?", ["Compiler runs line by line; interpreter translates whole program first","Compiler translates whole program at once; interpreter executes line by line","Both do the same job","Interpreter only works with machine code"], 1, "Translation", "A compiler translates the entire source at once; an interpreter executes line by line.", "Paper 2 — Application"),
        ]

        for i, (q_text, opts, correct_idx, topic, explanation, section) in enumerate(intro_questions):
            q = Question(
                week_id=intro.id,
                text=q_text,
                topic=topic,
                explanation=explanation,
                section=section,
                order=i
            )
            db.session.add(q)
            db.session.flush()
            for j, opt_text in enumerate(opts):
                opt = Option(question_id=q.id, text=opt_text, is_correct=(j == correct_idx), order=j)
                db.session.add(opt)

    # Create week placeholders 1–12
    week_meta = [
        (1, "week1", "Week 1", "Coming soon — your teacher will unlock this when ready."),
        (2, "week2", "Week 2", "Coming soon — your teacher will unlock this when ready."),
        (3, "week3", "Week 3", "Coming soon — your teacher will unlock this when ready."),
        (4, "week4", "Week 4", "Coming soon — your teacher will unlock this when ready."),
        (5, "week5", "Week 5", "Coming soon — your teacher will unlock this when ready."),
        (6, "week6", "Week 6", "Coming soon — your teacher will unlock this when ready."),
        (7, "week7", "Week 7", "Coming soon — your teacher will unlock this when ready."),
        (8, "week8", "Week 8", "Coming soon — your teacher will unlock this when ready."),
        (9, "week9", "Week 9", "Coming soon — your teacher will unlock this when ready."),
        (10, "week10", "Week 10", "Coming soon — your teacher will unlock this when ready."),
        (11, "week11", "Week 11", "Coming soon — your teacher will unlock this when ready."),
        (12, "week12", "Week 12 — Revision", "Coming soon — your teacher will unlock this when ready."),
    ]
    for week_num, slug, title, desc in week_meta:
        if not Week.query.filter_by(slug=slug).first():
            w = Week(slug=slug, title=title, description=desc,
                     week_number=week_num, is_enabled=False, is_intro=False)
            db.session.add(w)

    db.session.commit()

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
