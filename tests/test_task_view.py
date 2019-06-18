# -*- coding: UTF-8 -*-
"""A suite of tests for the TaskView object"""
import unittest
from unittest.mock import patch, MagicMock

import ujson
from flask import Flask
from vlab_api_common.http_auth import generate_v2_test_token

from vlab_inf_common.views import task_view


class MyView(task_view.TaskView):
    route_base = '/test'

    def send_network_task(self, username, machine_name, new_network, txn_id):
        """The base method is an abstractmethod"""
        task = MagicMock()
        task.id = 'aabbcc'
        return task

class TestTaskView(unittest.TestCase):
    """A set of test cases for ``TaskView``"""

    @classmethod
    def setUpClass(cls):
        """Runs once for the whole suite"""
        cls.token = generate_v2_test_token(username='alice')

    @classmethod
    def setUp(cls):
        "Runs before every test case"
        # Setup the app
        app = Flask(__name__)
        MyView.register(app)
        app.config['TESTING'] = True
        app.celery_app = MagicMock()
        cls.app = app.test_client()
        # Mock Celery response
        cls.fake_result = MagicMock()
        cls.fake_result.status = 'SUCCESS'
        cls.fake_result.result = {'error': None}
        app.celery_app.AsyncResult.return_value = cls.fake_result

    def test_no_task_id(self):
        """``TaskView`` - Not supplying a task-id returns HTTP 400"""
        resp = self.app.get('/test/task',
                headers={'X-Auth': self.token})

        self.assertEqual(resp.status_code, 400)

    def test_two_task_ids(self):
        """``TaskView`` - supplying the task-id via URL and param returns HTTP 400"""
        resp = self.app.get('/test/task/asdf-asdf-asdf',
                query_string='task-id=asdf-asdf-asdf',
                headers={'X-Auth': self.token})

        self.assertEqual(resp.status_code, 400)

    def test_by_param(self):
        """``TaskView`` - Supports supplying task-id by query parameter"""
        resp = self.app.get('/test/task',
                query_string='task-id=asdf-asdf-asdf',
                headers={'X-Auth': self.token})

        self.assertEqual(resp.status_code, 200)

    def test_pending(self):
        """``TaskView`` - Returns HTTP 202 when the task is still processing"""
        self.fake_result.status = 'PENDING'
        resp = self.app.get('/test/task/asdf-asdf-asdf',
                headers={'X-Auth': self.token})

        self.assertEqual(resp.status_code, 202)

    def test_failure(self):
        """``TaskView`` - Returns HTTP 500 when the task encounters a system failure"""
        self.fake_result.status = 'FAILURE'
        resp = self.app.get('/test/task/asdf-asdf-asdf',
                headers={'X-Auth': self.token})

        self.assertEqual(resp.status_code, 500)

    def test_error(self):
        """``TaskView`` - Returns HTTP 400 when the task errors due to user input"""
        self.fake_result.result = {'error': 'testing'}
        resp = self.app.get('/test/task/asdf-asdf-asdf',
                headers={'X-Auth': self.token})

        self.assertEqual(resp.status_code, 400)

    def test_modify_network(self):
        """``TaskView`` - PUT on /network returns a task id"""
        payload = {'name': "someVM", 'new_network': "myOtherNetwork"}

        resp = self.app.put('/test/network',
                            headers={'X-Auth': self.token},
                            json=payload)

        expected = {'error': None, 'content': {'task-id': 'aabbcc'}, 'params': {}}

        self.assertEqual(resp.json, expected)


if __name__ == '__main__':
    unittest.main()
