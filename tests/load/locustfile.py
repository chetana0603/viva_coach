"""
Load test for the assessment path. Run against a staging database seeded with
load-test accounts — never against real student data.

    locust -f tests/load/locustfile.py --host https://viva.college.edu

Stages from the plan: 5 → 10 → 25 → 50 → 75 users.
"""
import re

from locust import HttpUser, between, task

CSRF = re.compile(r'name="csrf_token"[^>]*value="([^"]+)"')


class StudentUser(HttpUser):
    wait_time = between(10, 30)
    exam_id = 1

    def on_start(self):
        self.attempt_id = None
        self.login()
        self.start_exam()

    def _csrf(self, path):
        page = self.client.get(path).text
        match = CSRF.search(page)
        return match.group(1) if match else ""

    def login(self):
        token = self._csrf("/login")
        # Each virtual user needs its own seeded account; index off the runner.
        self.client.post("/login", data={
            "csrf_token": token,
            "email": f"load{self.environment.runner.user_count:03d}@college.edu",
            "password": "LoadTest123",
        })

    def start_exam(self):
        token = self._csrf(f"/student/exams/{self.exam_id}")
        with self.client.post(f"/student/exams/{self.exam_id}/start",
                              data={"csrf_token": token},
                              allow_redirects=True, catch_response=True) as resp:
            match = re.search(r"/student/attempts/(\d+)", resp.url)
            if match:
                self.attempt_id = int(match.group(1))
                resp.success()
            else:
                resp.failure("Could not start attempt")

    @task(4)
    def answer_question(self):
        if not self.attempt_id:
            return
        page = self.client.get(f"/student/attempts/{self.attempt_id}",
                               name="/student/attempts/[id]").text
        token_match = CSRF.search(page)
        aq_match = re.search(r'name="assigned_question_id" value="(\d+)"', page)
        if not (token_match and aq_match):
            return   # attempt finished or expired

        self.client.post(f"/student/attempts/{self.attempt_id}/answer",
                         name="/student/attempts/[id]/answer",
                         data={"csrf_token": token_match.group(1),
                               "assigned_question_id": aq_match.group(1),
                               "selected_option": "0",
                               "client_response_time": "12.0"})

    @task(1)
    def poll_state(self):
        if self.attempt_id:
            self.client.get(f"/student/api/attempts/{self.attempt_id}/state",
                            name="/student/api/attempts/[id]/state")
