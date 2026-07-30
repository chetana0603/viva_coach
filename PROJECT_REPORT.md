# Project Report: Viva Platform

## 1. Executive Summary

The Viva Platform is a Flask-based web application for conducting adaptive academic assessments, study-based evaluations, and project viva workflows. It is designed for educational environments where teachers can create exams, manage student accounts, approve registrations, review question banks, and evaluate learning outcomes over time.

The system combines:
- a role-based student and teacher experience,
- an adaptive exam engine,
- a question approval and validation pipeline,
- a project-report-based viva mode,
- and integrity monitoring features for assessment security.

## 2. Project Objective

The platform aims to support:
1. Secure student authentication and account management.
2. Teacher-led exam creation and administration.
3. Adaptive assessment with real-time scoring and remediation.
4. Comparison of pre-test and post-test learning gains.
5. Project-based viva evaluation using uploaded student reports.

## 3. System Overview

The application uses the Flask application factory pattern in [app/__init__.py](app/__init__.py), with modular blueprints for public, authentication, student, teacher, and project workflows.

### Main modules
- [app/auth](app/auth) handles authentication, route protection, and decorators.
- [app/student](app/student) manages student dashboards, exam registration, exam taking, feedback, and results.
- [app/teacher](app/teacher) manages teacher dashboards, student approval, roster import, exams, blueprint configuration, and registrations.
- [app/exam_engine](app/exam_engine) implements exam access control, attempt lifecycle, adaptive question selection, and scoring.
- [app/project](app/project) supports submission, analysis, study card generation, and project-question pool creation.
- [app/models](app/models) defines the database schema for users, exams, questions, attempts, responses, and integrity events.
- [app/core](app/core) contains the reusable academic logic, including scoring and prompt-based evaluation logic.

## 4. Key Features

### 4.1 Authentication and Access Control
- Role-based access for teachers, students, and admins.
- Account approval and suspension workflow.
- Roster-based eligibility for student registration.
- Protected routes for teacher and student sections.

### 4.2 Exam Management
- Teachers can create and edit exams.
- Exams support registration windows, exam windows, duration, and question counts.
- Pre-test, post-test, and project viva modes are supported.
- Study-group tags can be used to prevent repeated questions across related attempts.

### 4.3 Adaptive Assessment Engine
- Students receive questions dynamically based on prior answers.
- Difficulty adjusts upward or downward according to performance.
- Remedial questions can be assigned after incorrect answers in teaching-oriented exams.
- Server-authoritative attempt handling prevents tampering and supports timer-based expiry.

### 4.4 Question Bank Workflow
- Questions can be generated, validated, and approved.
- Teachers review candidates before they are used in exams.
- Approved questions are the only ones eligible for assessment use.

### 4.5 Project Viva
- Students can upload reports and paste text.
- The system extracts material from uploaded files.
- It analyses the submission, creates study cards, and generates questions from the student’s own content.

### 4.6 Integrity Monitoring
- Browser-based events such as tab switches and copy/paste activity are recorded as review signals.
- These are treated as indicators rather than automatic penalties.

## 5. Core Workflow

### Teacher workflow
1. Create a teacher account.
2. Import eligible students through the roster flow.
3. Create an exam with subject, window, and type.
4. Select concepts and configure the exam blueprint.
5. Approve student registrations.
6. Review results and export evaluation data.

### Student workflow
1. Register using an eligible roster entry.
2. Wait for teacher approval.
3. Register for an exam.
4. Start the attempt and answer adaptive questions.
5. Receive results or learning feedback depending on the exam mode.

## 6. Technical Architecture

### Backend
- Flask application factory
- Flask-SQLAlchemy for ORM persistence
- Flask-Migrate for database migrations
- Flask-Login for session authentication
- Flask-WTF for forms and CSRF protection
- PostgreSQL support via psycopg, with SQLite fallback for local development

### Frontend
- Jinja2 templates under [app/templates](app/templates)
- Custom styling in [app/static/css/app.css](app/static/css/app.css)
- JavaScript enhancements in [app/static/js](app/static/js)

### Data Model
Core entities include:
- [app/models/user.py](app/models/user.py) for users and eligible students
- [app/models/exam.py](app/models/exam.py) for exams, registrations, and concepts
- [app/models/attempt.py](app/models/attempt.py) for attempts and assigned questions
- [app/models/response.py](app/models/response.py) for answers and scoring data
- [app/models/project.py](app/models/project.py) for project submissions and study cards

## 7. Important Implementation Areas

### Attempt lifecycle
The attempt flow in [app/exam_engine/attempt_service.py](app/exam_engine/attempt_service.py) manages:
- starting attempts,
- assigning questions,
- recording answers,
- applying remediation,
- finalising submissions,
- and handling time expiry.

### Teacher routes
The teacher experience in [app/teacher/routes.py](app/teacher/routes.py) covers:
- dashboard statistics,
- account approval,
- student import,
- exam editing,
- blueprint configuration,
- enrolment, and
- registration review.

### Student routes
The student experience in [app/student/routes.py](app/student/routes.py) covers:
- dashboard navigation,
- exam registration,
- starting and resuming attempts,
- answering questions,
- viewing feedback,
- and accessing results.

## 8. Testing and Quality Assurance

The repository includes unit, integration, security, and load tests under [tests](tests):
- [tests/unit](tests/unit)
- [tests/integration](tests/integration)
- [tests/security](tests/security)
- [tests/load](tests/load)

The project is structured for security-focused validation, including checks for:
- unauthorised access to another student’s attempt,
- incorrect answer assignment,
- expired attempt handling,
- account approval restrictions,
- and teacher-route protection.

## 9. Deployment and Operations

The project includes deployment guidance and infrastructure assets in [deployment](deployment), along with configuration files such as [docker-compose.yml](docker-compose.yml), [Dockerfile](Dockerfile), [render.yaml](render.yaml), and [Procfile](Procfile).

It supports:
- local development,
- Docker-based deployment,
- and cloud deployment through Render or similar platforms.

## 10. Strengths

- Strong separation of concerns through Flask blueprints and services.
- Clear assessment lifecycle from registration to evaluation.
- Adaptive exam logic aligned with educational measurement goals.
- Built-in support for study-group comparison and learning-gain evaluation.
- Good security posture for a classroom-based assessment platform.

## 11. Limitations and Risks

- The quality of the assessment depends heavily on the availability of approved questions.
- The project notes that the initial bank may be too small for large-scale studies unless the question pool is expanded.
- Some workflows, especially project-viva question generation, depend on external services and careful configuration.
- The system is intended for supervised academic use and should be managed carefully in production.

## 12. Conclusion

The Viva Platform is a well-structured assessment system that brings together adaptive evaluation, teacher oversight, student workflow management, and project-based viva support. Its architecture is modular, its educational logic is clearly defined, and it is suitable for deployment in academic or training environments when supported by a strong question bank and careful administration.
