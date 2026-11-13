"""Seed the three production roadmaps (idempotent)."""
from django.core.management.base import BaseCommand
from django.db import transaction

from quizzes.models import Choice, Question, Quiz
from roadmaps.models import Category, Node, Roadmap, Video

PASS_MARK = 60

# Each question: (text, correct answer, [3 wrong answers])
ROADMAPS = [
    {
        "title": "Python Developer",
        "slug": "python-developer",
        "category": ("Programming Languages", "programming-languages"),
        "attribution": "Curriculum aligned with roadmap.sh; Video lectures by Krish Naik (YouTube)",
        "description": "Learn Python from setup to packaging, following the roadmap.sh Python path.",
        "channel": "Krish Naik",
        "youtube_id": "bPrmA1SEN2k",
        "nodes": [
            ("Python Basics & Environment Setup", "python-basics-setup", 1800, [
                ("Which function prints text to the console in Python?", "print()", ["echo()", "console.log()", "printf()"]),
                ("Which of these is a valid Python variable name?", "my_var", ["2var", "my-var", "my var"]),
                ("What does the type of 3.14 evaluate to?", "float", ["int", "str", "decimal"]),
            ]),
            ("Core Data Structures: Lists, Tuples, Dictionaries & Sets", "python-data-structures", 2400, [
                ("Which data structure is immutable?", "tuple", ["list", "dict", "set"]),
                ("How do you access the value for key 'a' in dictionary d?", "d['a']", ["d.a", "d(a)", "d{a}"]),
                ("Which structure stores only unique elements?", "set", ["list", "tuple", "dict values"]),
            ]),
            ("Control Flow, Functions & Lambda Expressions", "python-control-flow-functions", 2100, [
                ("Which keyword defines a function in Python?", "def", ["func", "function", "lambda def"]),
                ("What does `lambda x: x * 2` create?", "An anonymous function", ["A list", "A class", "A loop"]),
                ("Which statement exits a loop immediately?", "break", ["continue", "pass", "exit"]),
            ]),
            ("Object-Oriented Programming (OOP) in Python", "python-oop", 2700, [
                ("Which method is the constructor in a Python class?", "__init__", ["__new_object__", "__start__", "constructor"]),
                ("What does `self` refer to inside a method?", "The current instance", ["The class itself", "The parent class", "A global variable"]),
                ("Which OOP concept lets a class reuse another class's behaviour?", "Inheritance", ["Encapsulation only", "Serialization", "Iteration"]),
            ]),
            ("Exception Handling & File I/O", "python-exceptions-file-io", 1900, [
                ("Which block runs code that may raise an exception?", "try", ["catch", "except", "finally only"]),
                ("Which mode opens a file for reading text?", "'r'", ["'w'", "'a'", "'x'"]),
                ("Which statement ensures a file is closed automatically?", "with open(...) as f", ["for open(...)", "if open(...)", "while open(...)"]),
            ]),
            ("Modules, Virtual Environments & Package Management", "python-modules-venv-pip", 1500, [
                ("Which command installs a package from PyPI?", "pip install", ["python get", "npm install", "venv install"]),
                ("What is a virtual environment for?", "Isolating project dependencies", ["Speeding up Python", "Compiling Python to C", "Encrypting code"]),
                ("Which keyword brings a module into your code?", "import", ["include", "require", "using"]),
            ]),
        ],
    },
    {
        "title": "Machine Learning Engineer",
        "slug": "machine-learning-engineer",
        "category": ("Artificial Intelligence & Data", "artificial-intelligence-data"),
        "attribution": "Curriculum aligned with roadmap.sh; Video lectures by CampusX / Nitish Singh (YouTube)",
        "description": "Core machine learning skills from fundamentals to model evaluation.",
        "channel": "CampusX",
        "youtube_id": "ZftI2fEz0Fw",
        "nodes": [
            ("Introduction to ML, Types of Learning & ML Lifecycle", "ml-intro-lifecycle", 1800, [
                ("Which type of learning uses labelled data?", "Supervised learning", ["Unsupervised learning", "Reinforcement learning", "Self-organising learning"]),
                ("Clustering customers without labels is an example of:", "Unsupervised learning", ["Supervised learning", "Regression", "Classification"]),
                ("Which step comes first in the ML lifecycle?", "Problem framing and data collection", ["Model deployment", "Hyperparameter tuning", "Monitoring"]),
            ]),
            ("Exploratory Data Analysis & Data Preprocessing", "ml-eda-preprocessing", 2400, [
                ("What is the main purpose of EDA?", "Understand patterns and quality of the data", ["Deploy the model", "Train the final model", "Encrypt the data"]),
                ("Which plot best shows the distribution of one numeric variable?", "Histogram", ["Pie chart of IDs", "Network graph", "Gantt chart"]),
                ("Why scale features before using distance-based algorithms?", "So no feature dominates due to its range", ["To add more rows", "To remove labels", "To reduce the file size"]),
            ]),
            ("Feature Engineering: Imputation & Categorical Encoding", "ml-feature-engineering", 2100, [
                ("Replacing missing values with the column mean is called:", "Mean imputation", ["One-hot encoding", "Normalisation", "Binning"]),
                ("One-hot encoding converts categories into:", "Binary indicator columns", ["A single integer", "Text embeddings", "Image pixels"]),
                ("Which encoding suits an ordered category such as Low/Medium/High?", "Ordinal encoding", ["Random encoding", "Hash of the row", "Label shuffling"]),
            ]),
            ("Supervised Learning: Linear & Logistic Regression", "ml-linear-logistic-regression", 2700, [
                ("Logistic regression is mainly used for:", "Classification", ["Clustering", "Dimensionality reduction", "Image generation"]),
                ("Linear regression typically minimises:", "Mean squared error", ["Accuracy", "Entropy of labels", "Number of features"]),
                ("The sigmoid function outputs values between:", "0 and 1", ["-1 and 1", "0 and 100", "-infinity and infinity"]),
            ]),
            ("Tree-Based Models: Decision Trees & Random Forests", "ml-trees-random-forests", 2400, [
                ("A random forest is an ensemble of:", "Decision trees", ["Linear models", "Neural networks", "K-means clusters"]),
                ("Which measure is commonly used to choose a split in a decision tree?", "Gini impurity or entropy", ["Mean squared deviation of labels only", "Learning rate", "Batch size"]),
                ("Deep unpruned decision trees tend to:", "Overfit the training data", ["Underfit badly", "Ignore all features", "Run faster than linear models"]),
            ]),
            ("Model Evaluation Metrics & Cross-Validation", "ml-evaluation-cross-validation", 1800, [
                ("Which metric is the harmonic mean of precision and recall?", "F1-score", ["R-squared", "Log loss", "Specificity"]),
                ("What does k-fold cross-validation do?", "Trains and validates on k different splits", ["Trains k times on the same split", "Removes k features", "Doubles the dataset"]),
                ("Accuracy can be misleading when:", "Classes are heavily imbalanced", ["The dataset is small and balanced", "There are two features", "The model is linear"]),
            ]),
        ],
    },
    {
        "title": "Full Stack Web Developer",
        "slug": "full-stack-web-developer",
        "category": ("Web Development", "web-development"),
        "attribution": "Curriculum aligned with roadmap.sh; Video lectures by Love Babbar / CodeHelp (YouTube)",
        "description": "From the web basics to a Node.js and Express backend (MERN path).",
        "channel": "Love Babbar",
        "youtube_id": "Vi9bxu-M-ag",
        "nodes": [
            ("How the Internet Works & HTML5 Semantic Structure", "web-internet-html5", 1800, [
                ("Which protocol is used to load web pages?", "HTTP/HTTPS", ["FTP only", "SMTP", "SSH"]),
                ("Which element is a semantic HTML5 container for the page's main navigation?", "<nav>", ["<div id='nav'>", "<span>", "<navigation-bar>"]),
                ("What does DNS do?", "Translates domain names to IP addresses", ["Encrypts web traffic", "Stores web pages", "Compiles HTML"]),
            ]),
            ("CSS3 Fundamentals, Box Model & Responsive Flexbox", "web-css-flexbox", 2400, [
                ("From inside to outside, the CSS box model is:", "Content, padding, border, margin", ["Content, margin, border, padding", "Padding, content, margin, border", "Border, content, padding, margin"]),
                ("Which property turns an element into a flex container?", "display: flex", ["flex: container", "position: flex", "float: flex"]),
                ("Which flexbox property aligns items along the main axis?", "justify-content", ["align-text", "flex-wrap-axis", "item-main"]),
            ]),
            ("JavaScript Basics: Variables, Loops & Functions", "web-js-basics", 2100, [
                ("Which keyword declares a block-scoped variable that can be reassigned?", "let", ["const", "var only for constants", "static"]),
                ("What does `===` check in JavaScript?", "Equal value and equal type", ["Equal value only", "Same memory address always", "Assignment"]),
                ("Which loop is best when you know the number of iterations?", "for", ["do-nothing", "try", "switch"]),
            ]),
            ("DOM Manipulation & Browser Events", "web-dom-events", 2400, [
                ("Which method selects an element by its id?", "document.getElementById()", ["document.selectId()", "window.findId()", "dom.getId()"]),
                ("Which method attaches an event handler to an element?", "addEventListener()", ["attachEvent only in Node", "onEventAdd()", "bindEvent()"]),
                ("What does `event.preventDefault()` do?", "Stops the browser's default action", ["Removes the element", "Stops all JavaScript", "Reloads the page"]),
            ]),
            ("Asynchronous JavaScript: Promises & Fetch API", "web-async-promises-fetch", 2100, [
                ("What does `fetch()` return?", "A Promise", ["A string", "A JSON object directly", "An array"]),
                ("Which keyword pauses an async function until a Promise settles?", "await", ["pause", "yield only", "wait"]),
                ("Which Promise method handles a rejected Promise?", ".catch()", [".then() only", ".finally() only", ".reject()"]),
            ]),
            ("Backend Introduction with Node.js & Express", "web-nodejs-express", 2700, [
                ("Node.js executes JavaScript using which engine?", "V8", ["SpiderMonkey", "Chakra", "JVM"]),
                ("Which Express method defines a handler for GET requests?", "app.get()", ["app.fetch()", "app.read()", "app.request()"]),
                ("What is Express middleware?", "A function with access to req, res and next", ["A database driver", "A CSS framework", "A browser extension"]),
            ]),
        ],
    },
]


class Command(BaseCommand):
    help = "Seed the 3 production roadmaps (Python, ML, Full Stack). Idempotent."

    @transaction.atomic
    def handle(self, *args, **options):
        counts = {"roadmaps": 0, "nodes": 0, "videos": 0, "questions": 0}
        for spec in ROADMAPS:
            name, slug = spec["category"]
            category, _ = Category.objects.get_or_create(slug=slug, defaults={"name": name})
            if category.name != name:
                category.name = name
                category.save(update_fields=["name"])

            roadmap, _ = Roadmap.objects.update_or_create(
                slug=spec["slug"],
                defaults={
                    "title": spec["title"],
                    "description": spec["description"],
                    "category": category,
                    "is_published": True,
                    "source_attribution": spec["attribution"],
                },
            )
            counts["roadmaps"] += 1

            for order, (title, node_slug, duration, questions) in enumerate(spec["nodes"], start=1):
                node, _ = Node.objects.update_or_create(
                    roadmap=roadmap,
                    slug=node_slug,
                    defaults={
                        "title": title,
                        "order": order,
                        "quiz_pass_mark": PASS_MARK,
                        "description": f"Part {order} of the {spec['title']} roadmap.",
                    },
                )
                counts["nodes"] += 1

                Video.objects.update_or_create(
                    node=node,
                    order=1,
                    defaults={
                        "youtube_id": spec["youtube_id"],
                        "title": title,
                        "channel_name": spec["channel"],
                        "duration_seconds": duration,
                        "is_embeddable": True,
                    },
                )
                counts["videos"] += 1

                quiz, _ = Quiz.objects.update_or_create(
                    node=node, defaults={"title": f"{title} Quiz"}
                )
                for q_order, (text, correct, wrong) in enumerate(questions, start=1):
                    question, _ = Question.objects.update_or_create(
                        quiz=quiz, order=q_order, defaults={"text": text}
                    )
                    # Vary the position of the correct answer deterministically.
                    answers = list(wrong)
                    answers.insert((order + q_order) % 4, correct)
                    wanted = [(a, a == correct) for a in answers]
                    existing = list(question.choices.order_by("pk").values_list("text", "is_correct"))
                    if existing != wanted:
                        question.choices.all().delete()
                        Choice.objects.bulk_create(
                            Choice(question=question, text=a, is_correct=ok) for a, ok in wanted
                        )
                    counts["questions"] += 1

        self.stdout.write(self.style.SUCCESS(
            "Seeded {roadmaps} roadmaps, {nodes} nodes, {videos} videos, {questions} questions.".format(**counts)
        ))
