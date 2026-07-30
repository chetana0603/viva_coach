# Architecture Guide

## Overview
The Viva Platform is a Flask web application for adaptive academic assessment. It is organized into blueprints for public access, authentication, student workflows, teacher workflows, and project-based viva workflows.

## Main Components

### Application Factory
The application is created by [app/__init__.py](../app/__init__.py). This central entry point wires the database, login manager, CSRF protection, and all blueprints.

### Blueprints
- [app/auth](../app/auth) — authentication, account approval, and route protection.
- [app/student](../app/student) — dashboards, exam registration, attempts, feedback, and results.
- [app/teacher](../app/teacher) — teacher administration, exam management, approvals, and reporting.
- [app/project](../app/project) — report upload, analysis, study cards, and project question generation.
- [app/public.py](../app/public.py) — home page and health endpoint.

### Core Logic
- [app/exam_engine](../app/exam_engine) — attempt lifecycle, adaptive question selection, scoring, and access control.
- [app/core](../app/core) — shared academic evaluation logic reused from the original prototype.
- [app/question_authoring](../app/question_authoring) — validation and duplicate detection for generated questions.
- [app/integrity_svc](../app/integrity_svc) — review indicators for suspected misconduct.

### Data Model
The database layer is defined through SQLAlchemy models in [app/models](../app/models):
- `User` and `EligibleStudent`
- `Exam`, `ExamRegistration`, and `ExamConcept`
- `Attempt`, `AssignedQuestion`, and `Response`
- `ProjectSubmission` and `StudyCard`

## Request Flow
1. A student logs in and accesses the dashboard.
2. The student registers for an exam and starts an attempt.
3. The attempt engine assigns questions adaptively.
4. Answers are stored and scored server-side.
5. The system finalizes the attempt and returns feedback or results.

## Security Approach
- Role-based route protection.
- Teacher-only workflows are guarded by decorators.
- Student access is restricted to their own attempts and submissions.
- Integrity events are logged as review signals rather than automatic penalties.
